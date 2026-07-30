"""
database.py
------------
This file takes care of everything related to our SQLite database:
  1. Connecting to the database file
  2. Creating the tables (users, treks, bookings) if they don't exist
  3. Adding one default Admin account so we can log in for the first time

We are using the plain "sqlite3" module that comes built-in with Python.
No extra database library is needed.
"""

import sqlite3
from werkzeug.security import generate_password_hash

# Name of our database file. It will be created in the same folder as app.py
DATABASE_NAME = "trekking.db"


def get_db_connection():
    """
    Opens a connection to our SQLite database and returns it.
    row_factory = sqlite3.Row lets us access columns by name,
    e.g. row["name"] instead of row[1]. Much easier to read!
    """
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """
    Creates all the tables our app needs (only if they don't already exist)
    and inserts one default Admin user so the app is usable immediately.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # ---------- USERS TABLE ----------
    # This single table stores Admin, Trek Staff, and Trekkers (Users).
    # We tell them apart using the "role" column.
    #
    # role   : 'admin', 'staff', or 'user'
    # status : for staff   -> 'pending', 'approved', 'blacklisted'
    #          for user    -> 'active', 'blacklisted'
    #          for admin   -> 'active'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            contact TEXT,
            role TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    # ---------- TREKS TABLE ----------
    # assigned_staff_id points to the "id" of a user whose role is 'staff'.
    # status : 'Pending', 'Approved', 'Open', 'Ongoing', 'Closed', 'Completed'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            duration INTEGER NOT NULL,
            total_slots INTEGER NOT NULL,
            available_slots INTEGER NOT NULL,
            assigned_staff_id INTEGER,
            status TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            description TEXT,
            FOREIGN KEY (assigned_staff_id) REFERENCES users (id)
        )
    """)

    # ---------- BOOKINGS TABLE ----------
    # status : 'Booked', 'Cancelled', 'Completed'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trek_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (trek_id) REFERENCES treks (id)
        )
    """)

    # ---------- SEED ONE DEFAULT ADMIN ----------
    # The task says "Admin must pre-exist in the database (no admin registration)".
    # So we create one admin account the very first time the app runs.
    cursor.execute("SELECT * FROM users WHERE role = 'admin'")
    existing_admin = cursor.fetchone()

    if existing_admin is None:
        default_password = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO users (name, email, password, contact, role, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("System Admin", "admin@trek.com", default_password, "9999999999", "admin", "active"))
        print("Default admin created -> email: admin@trek.com | password: admin123")

    conn.commit()
    conn.close()
