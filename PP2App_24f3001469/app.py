from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'very_simple_secret'

# --- CONFIGURATION FOR RESUME UPLOADS ---
UPLOAD_FOLDER = os.path.join('static', 'resumes')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect('placement_simple.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        # Table Creation
        db.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, password TEXT, approved INTEGER DEFAULT 0, created_at TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, password TEXT, created_at TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS drives (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, title TEXT, description TEXT, deadline TEXT, status TEXT DEFAULT 'pending', FOREIGN KEY (company_id) REFERENCES companies(id))''')
        
        # Fixed: applications table now includes the resume column
        db.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            student_id INTEGER, 
            drive_id INTEGER, 
            status TEXT DEFAULT 'applied', 
            resume TEXT,
            UNIQUE(student_id, drive_id), 
            FOREIGN KEY (student_id) REFERENCES students(id), 
            FOREIGN KEY (drive_id) REFERENCES drives(id))''')
        
        cur = db.cursor()
        
        # 1. Default Admin
        if not cur.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone():
            db.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', generate_password_hash('admin123')))
        
        # 2. Sample Student: Debankush Ghosh
        if not cur.execute("SELECT * FROM students WHERE email = 'ghoshdebankush@gmail.com'").fetchone():
            db.execute("INSERT INTO students (name, email, password, created_at) VALUES (?,?,?,?)", 
                       ('Debankush Ghosh', 'ghoshdebankush@gmail.com', generate_password_hash('student123'), '2026-03-01 10:00'))
        
        # 3. Sample Company: Future Interns
        if not cur.execute("SELECT * FROM companies WHERE email = 'hr@futureinterns.com'").fetchone():
            db.execute("INSERT INTO companies (name, email, password, approved, created_at) VALUES (?,?,?,?,?)",
                       ('Future Interns', 'hr@futureinterns.com', generate_password_hash('company123'), 1, '2025-11-29 09:00'))

        db.commit()

init_db()

# --- SECURITY DECORATOR ---
@app.before_request
def require_login():
    allowed = ['index', 'admin_login', 'company_login', 'company_register', 'student_login', 'student_register', 'static']
    if request.endpoint not in allowed and 'role' not in session:
        return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

# --- ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        session.clear()
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        with get_db() as db:
            admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
            if admin and check_password_hash(admin['password'], password):
                session.clear()
                session['role'] = 'admin'
                return redirect(url_for('admin_home'))
        flash('Wrong username or password')
    return render_template('admin_login.html')

@app.route('/admin/home')
def admin_home():
    with get_db() as db:
        stats = {
            'students': db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            'companies': db.execute("SELECT COUNT(*) FROM companies WHERE approved=1").fetchone()[0],
            'drives': db.execute("SELECT COUNT(*) FROM drives").fetchone()[0],
        }
        students_list = db.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
    return render_template('admin_home.html', stats=stats, students=students_list)

@app.route('/admin/companies')
def admin_companies():
    with get_db() as db:
        companies = db.execute("SELECT * FROM companies ORDER BY created_at DESC").fetchall()
    return render_template('admin_companies.html', companies=companies)

@app.route('/admin/approve_company/<int:cid>')
def approve_company(cid):
    with get_db() as db:
        db.execute("UPDATE companies SET approved = 1 WHERE id = ?", (cid,))
        db.commit()
    flash('Company approved')
    return redirect(url_for('admin_companies'))

@app.route('/admin/drives')
def admin_drives():
    with get_db() as db:
        drives = db.execute("SELECT d.*, c.name as company_name FROM drives d JOIN companies c ON d.company_id = c.id").fetchall()
    return render_template('admin_drives.html', drives=drives)

@app.route('/admin/approve_drive/<int:did>')
def approve_drive(did):
    with get_db() as db:
        db.execute("UPDATE drives SET status = 'approved' WHERE id = ?", (did,))
        db.commit()
    flash('Drive approved')
    return redirect(url_for('admin_drives'))

# --- COMPANY ROUTES ---
@app.route('/company/register', methods=['GET', 'POST'])
def company_register():
    if request.method == 'POST':
        name, email, password = request.form.get('name'), request.form.get('email'), generate_password_hash(request.form.get('password'))
        try:
            with get_db() as db:
                db.execute("INSERT INTO companies (name, email, password, created_at) VALUES (?,?,?,?)", (name, email, password, datetime.now().strftime("%Y-%m-%d %H:%M")))
                db.commit()
            flash('Registered! Wait for admin approval.')
            return redirect(url_for('company_login'))
        except sqlite3.IntegrityError: flash('Email already exists')
    return render_template('company_register.html')

@app.route('/company/login', methods=['GET', 'POST'])
def company_login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        with get_db() as db:
            company = db.execute("SELECT * FROM companies WHERE email = ?", (email,)).fetchone()
            if company and check_password_hash(company['password'], password):
                if company['approved']:
                    session.clear()
                    session['role'], session['user_id'] = 'company', company['id']
                    return redirect(url_for('company_home'))
                flash('Your account is not approved yet.')
            else: flash('Invalid credentials')
    return render_template('company_login.html')

@app.route('/company/home')
def company_home():
    with get_db() as db:
        # This JOIN query connects applications to students and drives
        applicants = db.execute("""
            SELECT s.name, s.email, d.title, a.resume, a.status 
            FROM applications a 
            JOIN students s ON a.student_id = s.id 
            JOIN drives d ON a.drive_id = d.id 
            WHERE d.company_id = ?
        """, (session['user_id'],)).fetchall()
        
        drives = db.execute("SELECT * FROM drives WHERE company_id = ?", (session['user_id'],)).fetchall()
    return render_template('company_home.html', drives=drives, applicants=applicants)

@app.route('/company/add_drive', methods=['GET', 'POST'])
def company_add_drive():
    if request.method == 'POST':
        title, desc, deadline = request.form.get('title'), request.form.get('description'), request.form.get('deadline')
        with get_db() as db:
            db.execute("INSERT INTO drives (company_id, title, description, deadline) VALUES (?,?,?,?)", (session['user_id'], title, desc, deadline))
            db.commit()
        flash('Drive created (awaiting approval)')
        return redirect(url_for('company_home'))
    return render_template('company_add_drive.html')

# --- STUDENT ROUTES ---
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        name, email, password = request.form.get('name'), request.form.get('email'), generate_password_hash(request.form.get('password'))
        try:
            with get_db() as db:
                db.execute("INSERT INTO students (name, email, password, created_at) VALUES (?,?,?,?)", (name, email, password, datetime.now().strftime("%Y-%m-%d %H:%M")))
                db.commit()
            flash('Registered successfully!')
            return redirect(url_for('student_login'))
        except sqlite3.IntegrityError: flash('Email already exists')
    return render_template('student_register.html')

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')
        with get_db() as db:
            student = db.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
            if student and check_password_hash(student['password'], password):
                session.clear()
                session['role'], session['user_id'] = 'student', student['id']
                return redirect(url_for('student_home'))
            flash('Invalid credentials')
    return render_template('student_login.html')

@app.route('/student/home')
def student_home():
    with get_db() as db:
        drives = db.execute("SELECT * FROM drives WHERE status = 'approved'").fetchall()
        my_apps = db.execute("SELECT a.*, d.title, c.name as company FROM applications a JOIN drives d ON a.drive_id = d.id JOIN companies c ON d.company_id = c.id WHERE a.student_id = ?", (session['user_id'],)).fetchall()
    return render_template('student_home.html', drives=drives, my_apps=my_apps)

@app.route('/student/apply/<int:drive_id>', methods=['POST'])
def student_apply(drive_id):
    if 'resume' not in request.files:
        flash('Resume required.')
        return redirect(url_for('student_home'))
    
    file = request.files['resume']
    if file and allowed_file(file.filename):
        # Secure filename generation
        filename = secure_filename(f"S{session['user_id']}_D{drive_id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        with get_db() as db:
            try:
                db.execute("INSERT INTO applications (student_id, drive_id, resume) VALUES (?,?,?)", (session['user_id'], drive_id, filename))
                db.commit()
                flash('Applied successfully with resume!')
            except sqlite3.IntegrityError: flash('Already applied.')
    else:
        flash('Invalid file format. Upload PDF/DOC.')
    return redirect(url_for('student_home'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)