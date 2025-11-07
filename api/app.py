from flask import Flask, jsonify, request

# The 'app' variable is what Vercel looks for.
app = Flask(__name__)

# --- In-Memory Database ---
# In a real app, this data would be in a database like Vercel Postgres.
# This is a simple list of dictionaries to act as a database.
db = {
    "patients": [
        {"id": 1, "name": "John Doe", "condition": "Fever"},
        {"id": 2, "name": "Jane Smith", "condition": "Broken Arm"},
        {"id": 3, "name": "Robert Brown", "condition": "Checkup"},
    ],
    "doctors": [
        {"id": 1, "name": "Dr. Alice Grey", "specialty": "Cardiology"},
        {"id": 2, "name": "Dr. Bob White", "specialty": "Orthopedics"},
    ]
}

# --- HTML Template Function ---
# We create a simple HTML wrapper to make the pages look nicer.
def html_wrapper(content, title="Hospital Management"):
    return f"""
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f7f6;">
        <nav style="background-color: #007bff; color: white; padding: 1rem 2rem; text-align: center;">
            <h1 style="margin: 0; font-size: 1.5rem;">{title}</h1>
        </nav>
        <div style="max-width: 800px; margin: 2rem auto; padding: 2rem; background-color: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <ul style="list-style: none; padding: 0; margin-bottom: 2rem; display: flex; gap: 1rem;">
                <li><a href="/" style="text-decoration: none; color: #007bff; font-weight: bold;">Home</a></li>
                <li><a href="/api/patients" style="text-decoration: none; color: #007bff; font-weight: bold;">Patients</a></li>
                <li><a href="/api/doctors" style="text-decoration: none; color: #007bff; font-weight: bold;">Doctors</a></li>
            </ul>
            <div>
                {content}
            </div>
        </div>
    </body>
    """

# --- Routes ---

@app.route('/')
def home():
    content = "<h2>Welcome to the Hospital Management System</h2><p>Use the links above to navigate the API.</p>"
    return html_wrapper(content, title="Home")

@app.route('/api/patients', methods=['GET'])
def get_patients():
    """Returns a list of all patients."""
    patients_list = "".join([f"<li>ID {p['id']}: {p['name']} ({p['condition']}) - <a href='/api/patients/{p['id']}'>View</a></li>" for p in db['patients']])
    content = f"<h2>All Patients</h2><ul>{patients_list}</ul>"
    return html_wrapper(content, title="Patients")

@app.route('/api/patients/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    """Returns details for a single patient."""
    patient = next((p for p in db['patients'] if p['id'] == patient_id), None)
    if patient:
        content = f"<h2>Patient Details</h2>"
        content += f"<p><b>ID:</b> {patient['id']}</p>"
        content += f"<p><b>Name:</b> {patient['name']}</p>"
        content += f"<p><b>Condition:</b> {patient['condition']}</p>"
        return html_wrapper(content, title=f"Patient {patient['name']}")
    else:
        # Use jsonify for API-like error responses
        return jsonify({"error": "Patient not found"}), 404

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    """Returns a list of all doctors."""
    doctors_list = "".join([f"<li>{d['name']} - <b>{d['specialty']}</b></li>" for d in db['doctors']])
    content = f"<h2>All Doctors</h2><ul>{doctors_list}</ul>"
    return html_wrapper(content, title="Doctors")

# Note: No app.run()!
# Vercel handles running the app as a serverless function.