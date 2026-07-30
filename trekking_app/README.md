# Trekking Management Application

A simple Flask + SQLite + Jinja2 + Bootstrap web app for managing trekking
activities between an **Admin**, **Trek Staff**, and **Users (Trekkers)**.

No JavaScript is used anywhere — every action (search, filter, booking,
approvals, etc.) is done through normal HTML forms and links handled by Flask.

## Project Structure

```
trekking_app/
│
├── app.py              # Main Flask app - all routes live here
├── database.py         # Creates the SQLite tables + default admin
├── requirements.txt    # Python dependencies
├── trekking.db         # SQLite database file (auto-created on first run)
│
├── static/
│   └── style.css        # Small custom styles on top of Bootstrap
│
└── templates/
    ├── base.html          # Shared layout (navbar, flash messages, footer)
    ├── login.html
    ├── register.html
    ├── admin/              # Admin pages
    │   ├── dashboard.html
    │   ├── treks.html
    │   ├── trek_form.html  # used for BOTH add & edit trek
    │   ├── staff.html
    │   ├── users.html
    │   ├── bookings.html
    │   └── search.html
    ├── staff/               # Trek Staff pages
    │   ├── dashboard.html
    │   ├── trek_update.html
    │   └── participants.html
    └── user/                # User (Trekker) pages
        ├── dashboard.html
        ├── treks.html
        ├── bookings.html
        └── profile.html
```

## How to Run

1. **Install dependencies** (only Flask is needed):
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app**:
   ```bash
   python app.py
   ```

3. Open your browser and go to:
   ```
   http://127.0.0.1:5000
   ```

The SQLite database (`trekking.db`) and the default Admin account are created
automatically the very first time you run the app — you don't need to create
anything manually.

## Default Admin Login

```
Email:    admin@trek.com
Password: admin123
```

Trek Staff and Users must register themselves from the **Register** page.
Trek Staff accounts stay "pending" until the Admin approves them from the
**Manage Staff** page.

## How the Roles Work

### Admin (pre-exists, cannot be registered from the UI)
- Dashboard with totals (treks, users, staff, bookings)
- Create / edit / delete treks
- Approve or blacklist Trek Staff registrations
- Assign approved staff to a trek (dropdown in the trek form)
- View all users, staff, and bookings
- Search treks, staff, or users by name or ID
- Blacklist/reactivate users or staff

### Trek Staff (must register, needs admin approval)
- Sees a "pending approval" message until Admin approves them
- Once approved: sees only the treks assigned to them
- Can update a trek's available slots and status (Open/Ongoing/Closed/Completed)
- Can view the list of users registered for each of their treks

### User / Trekker (must register, can log in immediately)
- Browses treks that are currently "Open"
- Can search by name and filter by difficulty/location
- Can book a trek (blocked automatically if slots are full or trek isn't Open)
- Can view booking status and full trekking history
- Can cancel an active booking (this returns the slot back to the trek)
- Can edit their name, contact number, and password

## Key Business Rules Implemented

- A user cannot book a trek that is full or not marked "Open".
- A user cannot double-book the same trek.
- Cancelling a booking automatically frees up a slot again.
- Only staff who are "approved" show up in the Admin's "Assign Staff" dropdown.
- Staff can only update treks that are assigned to them.
- Blacklisted users/staff cannot log in.
- Pending staff cannot access their dashboard's trek data until approved.

## Notes for Beginners

- The whole app logic lives in **one file: `app.py`** to keep things easy to
  follow — each route is a small Python function with comments explaining
  what it does.
- `database.py` uses plain `sqlite3` (built into Python) — no extra ORM.
- Passwords are never stored as plain text — `werkzeug.security` is used to
  hash and check them.
- `session` (a Flask built-in) is used to remember who is logged in.
- Every page extends `base.html` using Jinja2's `{% extends %}` so the
  navbar/footer only need to be written once.
