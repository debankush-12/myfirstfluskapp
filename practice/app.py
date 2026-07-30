from flask import Flask , render_template , url_for , session , flash , redirect , request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash , check_password_hash 

app = Flask(__name__)
app.secret_key = "secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///trekking.db"
db = SQLAlchemy(app)

class user(db.Model):
    id = db.Column(db.integer(),nullable = False)
    username = db.Column(db.string(50),nullable = False,unique = True)
    contact = db.Column(db.string(12), nullable = False , unique = True)
    password = db.Column(db.string(100), nullable = False)
    role = db.Column(db.string(10), nullable = False)
    status = db.Column(db.string(10), nullable = False)

@app.route('/')
def home():
    redirect(url_for('login.html'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u=username


