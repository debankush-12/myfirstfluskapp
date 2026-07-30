from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False) # admin, staff, user
    contact = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Approved') # Approved, Pending, Blacklisted

class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    location = db.Column(db.String(50))
    difficulty = db.Column(db.String(20)) # Easy, Moderate, Hard
    duration = db.Column(db.Integer)
    available_slots = db.Column(db.Integer)
    status = db.Column(db.String(20), default='Open') # Open, Closed, Completed
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    staff = db.relationship('User', foreign_keys=[assigned_staff_id])

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    trek_id = db.Column(db.Integer, db.ForeignKey('trek.id'))
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Booked')
    trek = db.relationship('Trek')
    user = db.relationship('User')

@app.route('/')
def home(): 
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and check_password_hash(u.password, request.form['password']):
            if u.status == 'Blacklisted': return "Blacklisted account.", 403
            if u.role == 'staff' and u.status == 'Pending': return "Pending admin approval.", 403
            session.update({'user_id': u.id, 'role': u.role, 'username': u.username})
            return redirect(url_for(f"{u.role}_dashboard"))
        flash("Invalid credentials")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        role = request.form['role']
        db.session.add(User(username=request.form['username'], password=hashed, role=role, contact=request.form['contact'], status='Pending' if role=='staff' else 'Approved'))
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    return render_template('admin_dashboard.html', 
        treks=Trek.query.all(),
        staff_members=User.query.filter_by(role='staff').all(),
        users=User.query.filter_by(role='user').all(),
        available_staff=User.query.filter_by(role='staff', status='Approved').all(),
        total_treks=Trek.query.count(), 
        total_users=User.query.filter_by(role='user').count(), 
        total_staff=User.query.filter_by(role='staff').count(), 
        total_bookings=Booking.query.count())

@app.route('/admin/add_trek', methods=['POST'])
def add_trek():
    db.session.add(Trek(name=request.form['name'], location=request.form['location'], difficulty=request.form['difficulty'], duration=int(request.form['duration']), available_slots=int(request.form['slots'])))
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/assign_staff/<int:trek_id>', methods=['POST'])
def assign_staff(trek_id):
    Trek.query.get(trek_id).assigned_staff_id = request.form['staff_id']
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user_status/<int:user_id>/<string:status>')
def change_user_status(user_id, status):
    User.query.get(user_id).status = status
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/staff/dashboard')
def staff_dashboard():
    if session.get('role') != 'staff': return redirect(url_for('login'))
    treks = Trek.query.filter_by(assigned_staff_id=session['user_id']).all()
    participants = {t.id: [b.user for b in Booking.query.filter_by(trek_id=t.id, status='Booked').all()] for t in treks}
    return render_template('staff_dashboard.html', treks=treks, participants=participants)

@app.route('/staff/update_trek/<int:trek_id>', methods=['POST'])
def update_trek(trek_id):
    t = Trek.query.get(trek_id)
    if t.assigned_staff_id == session['user_id']:
        t.available_slots, t.status = int(request.form['slots']), request.form['status']
        db.session.commit()
    return redirect(url_for('staff_dashboard'))

@app.route('/user/dashboard')
def user_dashboard():
    if session.get('role') != 'user': return redirect(url_for('login'))
    
    open_treks = Trek.query.filter_by(status='Open').all()
    user_bookings = Booking.query.filter_by(user_id=session['user_id']).all()
    current_user = User.query.get(session['user_id'])
    
    return render_template('user_dashboard.html', treks=open_treks, bookings=user_bookings, user=current_user)

@app.route('/user/book/<int:trek_id>')
def book_trek(trek_id):
    t = Trek.query.get(trek_id)
    if t.status == 'Open' and t.available_slots > 0 and not Booking.query.filter_by(user_id=session['user_id'], trek_id=trek_id, status='Booked').first():
        t.available_slots -= 1
        db.session.add(Booking(user_id=session['user_id'], trek_id=trek_id))
        db.session.commit()
    return redirect(url_for('user_dashboard'))

@app.route('/user/cancel/<int:booking_id>')
def cancel_booking(booking_id):
    b = Booking.query.get(booking_id)
    if b.user_id == session['user_id'] and b.status == 'Booked':
        b.status, b.trek.available_slots = 'Cancelled', b.trek.available_slots + 1
        db.session.commit()
    return redirect(url_for('user_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            db.session.add(User(username='admin', password=generate_password_hash('admin123', method='pbkdf2:sha256'), role='admin', status='Approved'))
            db.session.commit()
    app.run(debug=True)