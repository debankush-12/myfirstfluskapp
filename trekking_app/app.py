"""
app.py
------
This is the main Flask application file for the Trekking Management App.
It contains ALL the routes (pages) for Admin, Trek Staff, and Users (Trekkers).

To run this app:
    1. pip install -r requirements.txt
    2. python app.py
    3. Open http://127.0.0.1:5000 in your browser

Default admin login:
    email:    admin@trek.com
    password: admin123
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

from database import get_db_connection, init_db

app = Flask(__name__)
# secret_key is required by Flask to keep "session" data safe (used for login).
app.secret_key = "trekking_app_secret_key_change_this_later"

# Create the database & tables (and default admin) as soon as the app starts.
init_db()


# ======================================================================
#  HELPER DECORATORS (small functions that protect our routes)
# ======================================================================

def login_required(f):
    """Blocks access to a page unless the user is logged in."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(role_name):
    """Blocks access to a page unless the logged-in user has a specific role."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if session.get("role") != role_name:
                flash("You are not allowed to access that page.", "danger")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ======================================================================
#  HOME / AUTH ROUTES  (Login, Register, Logout)
# ======================================================================

@app.route("/")
def home():
    """Send the visitor to the correct dashboard, or to login if not logged in."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    elif role == "staff":
        return redirect(url_for("staff_dashboard"))
    elif role == "user":
        return redirect(url_for("user_dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page for Trek Staff and Users (Trekkers) only.
    Admin is NOT allowed to register from here - only pre-exists in the DB.
    """
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        contact = request.form["contact"].strip()
        role = request.form["role"]  # 'staff' or 'user'

        # Basic validation
        if role not in ("staff", "user"):
            flash("Invalid role selected.", "danger")
            return redirect(url_for("register"))

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

        if existing:
            flash("An account with that email already exists.", "danger")
            conn.close()
            return redirect(url_for("register"))

        # Staff accounts need admin approval first, so they start as 'pending'.
        # User (trekker) accounts can use the app right away, so they start as 'active'.
        starting_status = "pending" if role == "staff" else "active"

        hashed_password = generate_password_hash(password)
        conn.execute("""
            INSERT INTO users (name, email, password, contact, role, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, hashed_password, contact, role, starting_status))
        conn.commit()
        conn.close()

        if role == "staff":
            flash("Registration successful! Please wait for admin approval before logging in.", "success")
        else:
            flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page shared by Admin, Trek Staff, and Users."""
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password"], password):
            flash("Incorrect email or password.", "danger")
            return redirect(url_for("login"))

        # Blacklisted accounts cannot log in at all.
        if user["status"] == "blacklisted":
            flash("Your account has been blacklisted. Contact the admin.", "danger")
            return redirect(url_for("login"))

        # Save basic info about the logged-in user in the session.
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clears the session and logs the user out."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ======================================================================
#  ADMIN ROUTES
# ======================================================================

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    conn = get_db_connection()
    trek_count = conn.execute("SELECT COUNT(*) FROM treks").fetchone()[0]
    user_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
    staff_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'staff'").fetchone()[0]
    booking_count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    pending_staff_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'staff' AND status = 'pending'"
    ).fetchone()[0]
    conn.close()

    return render_template(
        "admin/dashboard.html",
        trek_count=trek_count,
        user_count=user_count,
        staff_count=staff_count,
        booking_count=booking_count,
        pending_staff_count=pending_staff_count,
    )


# ---------------- Trek management (Create / Edit / Delete) ----------------

@app.route("/admin/treks")
@role_required("admin")
def admin_treks():
    conn = get_db_connection()
    treks = conn.execute("""
        SELECT treks.*, users.name AS staff_name
        FROM treks
        LEFT JOIN users ON treks.assigned_staff_id = users.id
        ORDER BY treks.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin/treks.html", treks=treks)


@app.route("/admin/treks/add", methods=["GET", "POST"])
@role_required("admin")
def admin_add_trek():
    conn = get_db_connection()
    # Only "approved" staff can be assigned to a trek.
    staff_list = conn.execute(
        "SELECT id, name FROM users WHERE role = 'staff' AND status = 'approved'"
    ).fetchall()

    if request.method == "POST":
        name = request.form["name"].strip()
        location = request.form["location"].strip()
        difficulty = request.form["difficulty"]
        duration = int(request.form["duration"])
        total_slots = int(request.form["total_slots"])
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        description = request.form["description"].strip()
        assigned_staff_id = request.form.get("assigned_staff_id") or None
        status = request.form["status"]

        conn.execute("""
            INSERT INTO treks
                (name, location, difficulty, duration, total_slots, available_slots,
                 assigned_staff_id, status, start_date, end_date, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, location, difficulty, duration, total_slots, total_slots,
              assigned_staff_id, status, start_date, end_date, description))
        conn.commit()
        conn.close()

        flash("Trek created successfully.", "success")
        return redirect(url_for("admin_treks"))

    conn.close()
    return render_template("admin/trek_form.html", trek=None, staff_list=staff_list)


@app.route("/admin/treks/edit/<int:trek_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_edit_trek(trek_id):
    conn = get_db_connection()
    trek = conn.execute("SELECT * FROM treks WHERE id = ?", (trek_id,)).fetchone()
    staff_list = conn.execute(
        "SELECT id, name FROM users WHERE role = 'staff' AND status = 'approved'"
    ).fetchall()

    if trek is None:
        conn.close()
        flash("Trek not found.", "danger")
        return redirect(url_for("admin_treks"))

    if request.method == "POST":
        name = request.form["name"].strip()
        location = request.form["location"].strip()
        difficulty = request.form["difficulty"]
        duration = int(request.form["duration"])
        total_slots = int(request.form["total_slots"])
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        description = request.form["description"].strip()
        assigned_staff_id = request.form.get("assigned_staff_id") or None
        status = request.form["status"]

        # Keep available_slots consistent if the admin changes total_slots.
        # (booked_count = how many people already booked this trek)
        booked_count = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE trek_id = ? AND status = 'Booked'", (trek_id,)
        ).fetchone()[0]
        new_available_slots = max(total_slots - booked_count, 0)

        conn.execute("""
            UPDATE treks
            SET name = ?, location = ?, difficulty = ?, duration = ?, total_slots = ?,
                available_slots = ?, assigned_staff_id = ?, status = ?,
                start_date = ?, end_date = ?, description = ?
            WHERE id = ?
        """, (name, location, difficulty, duration, total_slots, new_available_slots,
              assigned_staff_id, status, start_date, end_date, description, trek_id))
        conn.commit()
        conn.close()

        flash("Trek updated successfully.", "success")
        return redirect(url_for("admin_treks"))

    conn.close()
    return render_template("admin/trek_form.html", trek=trek, staff_list=staff_list)


@app.route("/admin/treks/delete/<int:trek_id>", methods=["POST"])
@role_required("admin")
def admin_delete_trek(trek_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM bookings WHERE trek_id = ?", (trek_id,))
    conn.execute("DELETE FROM treks WHERE id = ?", (trek_id,))
    conn.commit()
    conn.close()
    flash("Trek deleted.", "info")
    return redirect(url_for("admin_treks"))


# ---------------- Staff management (Approve / Blacklist) ----------------

@app.route("/admin/staff")
@role_required("admin")
def admin_staff():
    conn = get_db_connection()
    staff = conn.execute("SELECT * FROM users WHERE role = 'staff' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/staff.html", staff=staff)


@app.route("/admin/staff/approve/<int:staff_id>", methods=["POST"])
@role_required("admin")
def admin_approve_staff(staff_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET status = 'approved' WHERE id = ? AND role = 'staff'", (staff_id,))
    conn.commit()
    conn.close()
    flash("Staff member approved.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/blacklist/<int:staff_id>", methods=["POST"])
@role_required("admin")
def admin_blacklist_staff(staff_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET status = 'blacklisted' WHERE id = ? AND role = 'staff'", (staff_id,))
    conn.commit()
    conn.close()
    flash("Staff member blacklisted.", "info")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/reactivate/<int:staff_id>", methods=["POST"])
@role_required("admin")
def admin_reactivate_staff(staff_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET status = 'approved' WHERE id = ? AND role = 'staff'", (staff_id,))
    conn.commit()
    conn.close()
    flash("Staff member reactivated.", "success")
    return redirect(url_for("admin_staff"))


# ---------------- User management (View / Blacklist) ----------------

@app.route("/admin/users")
@role_required("admin")
def admin_users():
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users WHERE role = 'user' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/blacklist/<int:user_id>", methods=["POST"])
@role_required("admin")
def admin_blacklist_user(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET status = 'blacklisted' WHERE id = ? AND role = 'user'", (user_id,))
    conn.commit()
    conn.close()
    flash("User blacklisted.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/reactivate/<int:user_id>", methods=["POST"])
@role_required("admin")
def admin_reactivate_user(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET status = 'active' WHERE id = ? AND role = 'user'", (user_id,))
    conn.commit()
    conn.close()
    flash("User reactivated.", "success")
    return redirect(url_for("admin_users"))


# ---------------- Bookings (view all) ----------------

@app.route("/admin/bookings")
@role_required("admin")
def admin_bookings():
    conn = get_db_connection()
    bookings = conn.execute("""
        SELECT bookings.*, users.name AS user_name, treks.name AS trek_name
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN treks ON bookings.trek_id = treks.id
        ORDER BY bookings.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin/bookings.html", bookings=bookings)


# ---------------- Search (treks, staff, users by name or ID) ----------------

@app.route("/admin/search")
@role_required("admin")
def admin_search():
    query = request.args.get("q", "").strip()
    treks, staff, users = [], [], []

    if query:
        conn = get_db_connection()
        search_term = f"%{query}%"

        # A search term could be a name (text) or an ID (number).
        # We try to match it against name OR id in each table.
        treks = conn.execute("""
            SELECT * FROM treks
            WHERE name LIKE ? OR CAST(id AS TEXT) = ?
        """, (search_term, query)).fetchall()

        staff = conn.execute("""
            SELECT * FROM users
            WHERE role = 'staff' AND (name LIKE ? OR CAST(id AS TEXT) = ?)
        """, (search_term, query)).fetchall()

        users = conn.execute("""
            SELECT * FROM users
            WHERE role = 'user' AND (name LIKE ? OR CAST(id AS TEXT) = ?)
        """, (search_term, query)).fetchall()

        conn.close()

    return render_template("admin/search.html", query=query, treks=treks, staff=staff, users=users)


# ======================================================================
#  TREK STAFF ROUTES
# ======================================================================

@app.route("/staff/dashboard")
@role_required("staff")
def staff_dashboard():
    conn = get_db_connection()
    staff_id = session["user_id"]
    staff_status = conn.execute("SELECT status FROM users WHERE id = ?", (staff_id,)).fetchone()["status"]

    # If admin hasn't approved this staff member yet, show a "pending" message instead.
    if staff_status != "approved":
        conn.close()
        return render_template("staff/dashboard.html", pending=True, treks=[])

    treks = conn.execute("""
        SELECT treks.*,
            (SELECT COUNT(*) FROM bookings WHERE bookings.trek_id = treks.id AND bookings.status = 'Booked') AS registered_count
        FROM treks
        WHERE assigned_staff_id = ?
        ORDER BY treks.id DESC
    """, (staff_id,)).fetchall()
    conn.close()

    return render_template("staff/dashboard.html", pending=False, treks=treks)


@app.route("/staff/treks/update/<int:trek_id>", methods=["GET", "POST"])
@role_required("staff")
def staff_update_trek(trek_id):
    conn = get_db_connection()
    staff_id = session["user_id"]
    trek = conn.execute(
        "SELECT * FROM treks WHERE id = ? AND assigned_staff_id = ?", (trek_id, staff_id)
    ).fetchone()

    if trek is None:
        conn.close()
        flash("You are not assigned to that trek.", "danger")
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        available_slots = int(request.form["available_slots"])
        status = request.form["status"]

        # A safety check: available slots can never be more than total slots.
        if available_slots > trek["total_slots"]:
            available_slots = trek["total_slots"]

        conn.execute(
            "UPDATE treks SET available_slots = ?, status = ? WHERE id = ?",
            (available_slots, status, trek_id)
        )
        conn.commit()
        conn.close()
        flash("Trek updated successfully.", "success")
        return redirect(url_for("staff_dashboard"))

    conn.close()
    return render_template("staff/trek_update.html", trek=trek)


@app.route("/staff/treks/participants/<int:trek_id>")
@role_required("staff")
def staff_view_participants(trek_id):
    conn = get_db_connection()
    staff_id = session["user_id"]
    trek = conn.execute(
        "SELECT * FROM treks WHERE id = ? AND assigned_staff_id = ?", (trek_id, staff_id)
    ).fetchone()

    if trek is None:
        conn.close()
        flash("You are not assigned to that trek.", "danger")
        return redirect(url_for("staff_dashboard"))

    participants = conn.execute("""
        SELECT users.name, users.email, users.contact, bookings.status, bookings.booking_date
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        WHERE bookings.trek_id = ?
        ORDER BY bookings.id DESC
    """, (trek_id,)).fetchall()
    conn.close()

    return render_template("staff/participants.html", trek=trek, participants=participants)


# ======================================================================
#  USER (TREKKER) ROUTES
# ======================================================================

@app.route("/user/dashboard")
@role_required("user")
def user_dashboard():
    conn = get_db_connection()
    user_id = session["user_id"]

    open_trek_count = conn.execute(
        "SELECT COUNT(*) FROM treks WHERE status = 'Open' AND available_slots > 0"
    ).fetchone()[0]

    my_bookings = conn.execute("""
        SELECT bookings.*, treks.name AS trek_name, treks.status AS trek_status
        FROM bookings
        JOIN treks ON bookings.trek_id = treks.id
        WHERE bookings.user_id = ?
        ORDER BY bookings.id DESC
        LIMIT 5
    """, (user_id,)).fetchall()
    conn.close()

    return render_template("user/dashboard.html", open_trek_count=open_trek_count, my_bookings=my_bookings)


@app.route("/user/treks")
@role_required("user")
def user_treks():
    """Browse treks that are Open for booking, with optional search/filter."""
    search = request.args.get("search", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    location = request.args.get("location", "").strip()

    query = "SELECT * FROM treks WHERE status = 'Open'"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")

    query += " ORDER BY id DESC"

    conn = get_db_connection()
    treks = conn.execute(query, params).fetchall()

    # Find which treks this user has already booked (so we can disable the button).
    user_id = session["user_id"]
    booked_rows = conn.execute(
        "SELECT trek_id FROM bookings WHERE user_id = ? AND status = 'Booked'", (user_id,)
    ).fetchall()
    booked_trek_ids = [row["trek_id"] for row in booked_rows]
    conn.close()

    return render_template(
        "user/treks.html",
        treks=treks,
        search=search,
        difficulty=difficulty,
        location=location,
        booked_trek_ids=booked_trek_ids,
    )


@app.route("/user/treks/book/<int:trek_id>", methods=["POST"])
@role_required("user")
def user_book_trek(trek_id):
    conn = get_db_connection()
    user_id = session["user_id"]
    trek = conn.execute("SELECT * FROM treks WHERE id = ?", (trek_id,)).fetchone()

    if trek is None:
        conn.close()
        flash("Trek not found.", "danger")
        return redirect(url_for("user_treks"))

    # Rule: users can only book if the trek is Open and has free slots.
    if trek["status"] != "Open":
        conn.close()
        flash("This trek is not open for booking.", "danger")
        return redirect(url_for("user_treks"))

    if trek["available_slots"] <= 0:
        conn.close()
        flash("Sorry, this trek is fully booked.", "danger")
        return redirect(url_for("user_treks"))

    # Rule: prevent a user from booking the same trek twice.
    already_booked = conn.execute(
        "SELECT id FROM bookings WHERE user_id = ? AND trek_id = ? AND status = 'Booked'",
        (user_id, trek_id)
    ).fetchone()
    if already_booked:
        conn.close()
        flash("You have already booked this trek.", "warning")
        return redirect(url_for("user_treks"))

    booking_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("""
        INSERT INTO bookings (user_id, trek_id, booking_date, status)
        VALUES (?, ?, ?, 'Booked')
    """, (user_id, trek_id, booking_date))

    # Reduce the available slots by 1 to prevent overbooking.
    conn.execute("UPDATE treks SET available_slots = available_slots - 1 WHERE id = ?", (trek_id,))
    conn.commit()
    conn.close()

    flash("Trek booked successfully!", "success")
    return redirect(url_for("user_bookings"))


@app.route("/user/bookings")
@role_required("user")
def user_bookings():
    conn = get_db_connection()
    user_id = session["user_id"]
    bookings = conn.execute("""
        SELECT bookings.*, treks.name AS trek_name, treks.location, treks.start_date, treks.end_date
        FROM bookings
        JOIN treks ON bookings.trek_id = treks.id
        WHERE bookings.user_id = ?
        ORDER BY bookings.id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return render_template("user/bookings.html", bookings=bookings)


@app.route("/user/bookings/cancel/<int:booking_id>", methods=["POST"])
@role_required("user")
def user_cancel_booking(booking_id):
    conn = get_db_connection()
    user_id = session["user_id"]
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ? AND user_id = ?", (booking_id, user_id)
    ).fetchone()

    if booking is None:
        conn.close()
        flash("Booking not found.", "danger")
        return redirect(url_for("user_bookings"))

    if booking["status"] != "Booked":
        conn.close()
        flash("Only an active booking can be cancelled.", "warning")
        return redirect(url_for("user_bookings"))

    conn.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = ?", (booking_id,))
    # Give the slot back to the trek.
    conn.execute(
        "UPDATE treks SET available_slots = available_slots + 1 WHERE id = ?", (booking["trek_id"],)
    )
    conn.commit()
    conn.close()

    flash("Booking cancelled.", "info")
    return redirect(url_for("user_bookings"))


@app.route("/user/profile", methods=["GET", "POST"])
@role_required("user")
def user_profile():
    conn = get_db_connection()
    user_id = session["user_id"]

    if request.method == "POST":
        name = request.form["name"].strip()
        contact = request.form["contact"].strip()
        new_password = request.form.get("password", "").strip()

        if new_password:
            hashed_password = generate_password_hash(new_password)
            conn.execute(
                "UPDATE users SET name = ?, contact = ?, password = ? WHERE id = ?",
                (name, contact, hashed_password, user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET name = ?, contact = ? WHERE id = ?",
                (name, contact, user_id)
            )
        conn.commit()
        session["name"] = name  # keep navbar greeting up to date
        conn.close()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("user_profile"))

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return render_template("user/profile.html", user=user)


# ======================================================================
#  RUN THE APP
# ======================================================================

if __name__ == "__main__":
    # debug=True auto-reloads the server when you save a file (great while learning).
    app.run(debug=True)
