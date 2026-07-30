from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev_key_123' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/resumes'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'admin', 'company', 'student'
    active = db.Column(db.Boolean, default=True)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    hr_contact = db.Column(db.String(100))
    website = db.Column(db.String(200))
    approval_status = db.Column(db.String(20), default='pending') # 'pending', 'approved', 'rejected'
    
    user = db.relationship('User', backref=db.backref('company_profile', uselist=False))

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    resume = db.Column(db.String(200))
    
    user = db.relationship('User', backref=db.backref('student_profile', uselist=False))

class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    deadline = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')
    
    creator = db.relationship('User', backref='drives_created')

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drive.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), default='applied') # 'applied', 'shortlisted', 'selected', 'rejected'
    
    applicant = db.relationship('User', backref='my_applications')
    drive = db.relationship('PlacementDrive', backref='all_applications')

# --- Utilities ---

@app.context_processor
def inject_models():
    """Fallback to allow model access in templates if direct object access fails."""
    return dict(Company=Company, Student=Student, PlacementDrive=PlacementDrive, Application=Application)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin'), role='admin', active=True)
        db.session.add(admin)
        db.session.commit()

# --- Auth Routes ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password) and user.active:
            if user.role == 'company':
                company = Company.query.filter_by(user_id=user.id).first()
                if company and company.approval_status != 'approved':
                    flash('Account pending admin approval.', 'warning')
                    return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for(f'{user.role}_dashboard'))
        flash('Invalid credentials or inactive account.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Username taken.', 'danger')
            return redirect(url_for('register_company'))
        user = User(username=request.form['username'], 
                    password=generate_password_hash(request.form['password']), 
                    role='company')
        db.session.add(user)
        db.session.commit()
        company = Company(user_id=user.id, name=request.form['name'], 
                         hr_contact=request.form['hr_contact'], website=request.form['website'])
        db.session.add(company)
        db.session.commit()
        flash('Registered! Pending admin approval.', 'success')
        return redirect(url_for('login'))
    return render_template('register_company.html')

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Username taken.', 'danger')
            return redirect(url_for('register_student'))
        user = User(username=request.form['username'], 
                    password=generate_password_hash(request.form['password']), 
                    role='student')
        db.session.add(user)
        db.session.commit()
        student = Student(user_id=user.id, name=request.form['name'], contact=request.form['contact'])
        db.session.add(student)
        db.session.commit()
        flash('Registration successful.', 'success')
        return redirect(url_for('login'))
    return render_template('register_student.html')

# --- Admin Routes ---

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return redirect(url_for('login'))
    return render_template('admin_dashboard.html', 
                           students_count=Student.query.count(),
                           companies_count=Company.query.count(),
                           drives_count=PlacementDrive.query.count(),
                           applications_count=Application.query.count())

@app.route('/admin/companies', methods=['GET', 'POST'])
@login_required
def admin_companies():
    if request.method == 'POST':
        search = request.form.get('search')
        companies = Company.query.filter(Company.name.like(f'%{search}%')).all()
    else:
        companies = Company.query.all()
    return render_template('admin_companies.html', companies=companies)

@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
def admin_students():
    if request.method == 'POST':
        search = request.form.get('search')
        students = Student.query.filter(Student.name.like(f'%{search}%')).all()
    else:
        students = Student.query.all()
    return render_template('admin_students.html', students=students)

@app.route('/admin/blacklist_user/<int:user_id>')
@login_required
def blacklist_user(user_id):
    user = User.query.get_or_404(user_id)
    user.active = not user.active 
    db.session.commit()
    flash('User status updated.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve_company/<int:company_id>')
@login_required
def approve_company(company_id):
    comp = Company.query.get_or_404(company_id)
    comp.approval_status = 'approved'
    db.session.commit()
    return redirect(url_for('admin_companies'))

@app.route('/admin/drives')
@login_required
def admin_drives():
    drives = PlacementDrive.query.all()
    return render_template('admin_drives.html', drives=drives)

@app.route('/admin/approve_drive/<int:drive_id>')
@login_required
def approve_drive(drive_id):
    drive = PlacementDrive.query.get_or_404(drive_id)
    drive.status = 'approved'
    db.session.commit()
    flash('Drive approved.', 'success')
    return redirect(url_for('admin_drives'))

@app.route('/admin/applications')
@login_required
def admin_applications():
    applications = Application.query.all()
    return render_template('admin_applications.html', applications=applications)

# --- Company Routes ---

@app.route('/company/dashboard')
@login_required
def company_dashboard():
    if current_user.role != 'company': return redirect(url_for('login'))
    drives = PlacementDrive.query.filter_by(company_id=current_user.id).all()
    return render_template('company_dashboard.html', company=current_user.company_profile, drives=drives)

@app.route('/company/create_drive', methods=['GET', 'POST'])
@login_required
def create_drive():
    if request.method == 'POST':
        deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%d').date()
        drive = PlacementDrive(company_id=current_user.id, title=request.form['title'],
                               description=request.form['description'], eligibility=request.form['eligibility'],
                               deadline=deadline)
        db.session.add(drive)
        db.session.commit()
        flash('Drive created.', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('create_drive.html')

# --- Student Routes ---

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student': return redirect(url_for('login'))
    drives = PlacementDrive.query.filter_by(status='approved').all()
    applications = Application.query.filter_by(student_id=current_user.id).all()
    applied_ids = [a.drive_id for a in applications]
    return render_template('student_dashboard.html', drives=drives, applications=applications, applied_ids=applied_ids)

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
def student_profile():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        student.name = request.form['name']
        student.contact = request.form['contact']
        if 'resume' in request.files:
            file = request.files['resume']
            if file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                student.resume = filename
        db.session.commit()
        flash('Profile updated.', 'success')
    return render_template('student_profile.html', student=student)

@app.route('/student/apply/<int:drive_id>')
@login_required
def apply_drive(drive_id):
    if Application.query.filter_by(student_id=current_user.id, drive_id=drive_id).first():
        flash('Already applied.', 'info')
    else:
        app = Application(student_id=current_user.id, drive_id=drive_id)
        db.session.add(app)
        db.session.commit()
        flash('Applied successfully!', 'success')
    return redirect(url_for('student_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)