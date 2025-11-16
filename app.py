import os
import json
from datetime import datetime
from difflib import get_close_matches
from functools import wraps
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import re

# Load .env if present
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
CORS(app)

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
EMP_FILE = os.path.join(DATA_DIR, "employees.json")
POL_FILE = os.path.join(DATA_DIR, "policies.json")
BOOK_FILE = os.path.join(DATA_DIR, "bookings.json")


# -------------------------
# Helpers: JSON IO & ensure files
# -------------------------
def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def ensure_files_exist():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        write_json(USERS_FILE, {"users": {
            "admin@example.com": {"name": "Admin", "password": "Admin@123", "employee_id": "EMP000001"}
        }})
    if not os.path.exists(EMP_FILE):
        write_json(EMP_FILE, {"employees": {
            "admin@example.com": {
                "name": "Admin",
                "employee_id": "EMP000001",
                "leave_balance": {"casual": 10, "sick": 6, "earned": 12},
                "email_active": True,
                "attendance_status": "Present"
            }
        }})
    if not os.path.exists(POL_FILE):
        write_json(POL_FILE, {"policies": {
            "leave": "Employees are eligible for 10 Casual Leaves, 6 Sick Leaves, and 12 Privilege Leaves per year. Leave requests must be submitted through HRMS at least one day in advance.",
            "it": "Employees must use strong passwords, enable multi-factor authentication, and avoid sharing credentials. All devices must have company-approved antivirus and updated OS.",
            "security": "Employees must wear ID cards visibly inside office premises. Lost/damaged ID cards must be reported to Admin.",
            "work_from_home": "Work-from-home permitted with prior approval from reporting manager. Stable internet and VPN required."
        }})
    if not os.path.exists(BOOK_FILE):
        write_json(BOOK_FILE, {"records": []})

ensure_files_exist()

# -------------------------
# User utilities
# -------------------------
def load_users():
    return read_json(USERS_FILE)["users"]

def save_users(users):
    write_json(USERS_FILE, {"users": users})

def load_employees():
    return read_json(EMP_FILE)["employees"]

def save_employees(employees):
    write_json(EMP_FILE, {"employees": employees})

# -------------------------
# Authentication decorator
# -------------------------
def login_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    return wrapper

# -------------------------
# Employee ID helper (generate)
# -------------------------
def generate_next_emp():
    """
    Returns next EMP id like EMP000001 for reuse (not used when user provides digits).
    """
    users = load_users()
    nums = []
    for u in users.values():
        eid = u.get("employee_id", "")
        if isinstance(eid, str) and eid.upper().startswith("EMP"):
            try:
                n = int(eid[3:])
                nums.append(n)
            except:
                pass
    next_num = max(nums) + 1 if nums else 1
    return f"EMP{next_num:06d}"

# -------------------------
# Validation helpers
# -------------------------
def validate_password(pw: str):
    """Return (True, "") if valid else (False, message)"""
    if len(pw) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", pw):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", pw):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"[0-9]", pw):
        return False, "Password must include at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\\\/\[\]]", pw):
        return False, "Password must include at least one special character (e.g. !@#$%)."
    return True, ""

def validate_email_format(email: str):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

def build_empid_from_digits(digits: str):
    """
    Accept digits like '123' -> produce EMP000123 (6 digits).
    If user supplies 'EMP...' already, return as-is (uppercased).
    """
    d = digits.strip()
    if not d:
        return None
    if d.upper().startswith("EMP"):
        return d.upper()
    if not d.isdigit():
        return None
    return "EMP" + d.zfill(6)

# -------------------------
# Fuzzy email helper
# -------------------------
def find_closest_email(email, email_list):
    matches = get_close_matches(email, email_list, n=1, cutoff=0.6)
    return matches[0] if matches else None

# -------------------------
# Intent detection (simple)
# -------------------------
def detect_intent(text):
    if not text:
        return "unknown"
    t = text.lower()
    if "policy" in t or "policies" in t or "hr policy" in t or "it policy" in t:
        return "policy_lookup"
    mapping = {
        "password": "password_reset",
        "leave": "leave_info",
        "meeting": "meeting_room",
        "book": "meeting_room",
        "wifi": "wifi_info",
        "email": "email_status",
        "id card": "id_card",
        "id": "id_card",
        "salary": "salary_slip",
        "ticket": "support_ticket",
        "holiday": "holiday_info",
        "attendance": "attendance",
        "menu": "cafeteria",
        "cafeteria": "cafeteria",
        "travel": "travel_request",
        "asset": "asset_request",
        "laptop": "asset_request",
        "work from home": "wfh_request"
    }
    for k, v in mapping.items():
        if k in t:
            return v
    return "unknown"

# -------------------------
# Service handlers
# -------------------------
def handle_password_reset(_): return "Password reset queued; check your registered email in a few minutes."
def handle_policy_lookup(_):
    policies = read_json(POL_FILE)["policies"]
    out = "Company policies summary:\n"
    for name, desc in policies.items():
        out += f"- {name.title()}: {desc}\n"
    return out
def handle_meeting_room(_):
    db = read_json(BOOK_FILE)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    db["records"].append({"room": "Conference Room A", "time": now})
    write_json(BOOK_FILE, db)
    return f"Booked Conference Room A at {now} (demo)."
def handle_wifi_info(_): return "Office WiFi: SSID = CorpNet | Password = Secure@2025"
def handle_id_card(_): return "ID card request received. Admin will contact you."
def handle_salary_slip(_): return "Salary slip has been emailed to your registered email."
def handle_support_ticket(_): return "IT support ticket created; team will reach out."
def handle_holiday_info(_): return "Next holiday: Republic Day (January 26)."

def handle_leave_info(email):
    employees = load_employees()
    emp = employees.get(email)
    if not emp:
        return "Leave record not found. Please contact HR."
    lv = emp.get("leave_balance", {"casual":0,"sick":0,"earned":0})
    return f"You have {lv['casual']} casual, {lv['sick']} sick and {lv['earned']} earned leaves."

def handle_email_status(email):
    employees = load_employees()
    emp = employees.get(email)
    if not emp:
        return "Employee record not found. Please contact Admin."
    return "Your corporate email is active." if emp.get("email_active", False) else "Your corporate email is pending activation."

def handle_attendance(email):
    employees = load_employees()
    emp = employees.get(email)
    if not emp:
        return "Attendance data unavailable. Contact HR."
    return f"Today's attendance: {emp.get('attendance_status','Unknown')}."

def handle_cafeteria(_):
    menu = ["Veg Biryani", "Paneer Butter Masala", "Curd Rice", "Salad", "Dosa (breakfast)"]
    return "Today's cafeteria menu:\n- " + "\n- ".join(menu)

def handle_travel_request(_): return "Travel request submitted."
def handle_asset_request(_): return "Asset request logged with IT Asset Team."
def handle_wfh_request(_): return "Work-from-home request submitted for manager approval."

HANDLERS = {
    "password_reset": handle_password_reset,
    "policy_lookup": handle_policy_lookup,
    "meeting_room": handle_meeting_room,
    "wifi_info": handle_wifi_info,
    "id_card": handle_id_card,
    "salary_slip": handle_salary_slip,
    "support_ticket": handle_support_ticket,
    "holiday_info": handle_holiday_info,
    "leave_info": handle_leave_info,
    "email_status": handle_email_status,
    "attendance": handle_attendance,
    "cafeteria": handle_cafeteria,
    "travel_request": handle_travel_request,
    "asset_request": handle_asset_request,
    "wfh_request": handle_wfh_request
}

# -------------------------
# Routes: Auth + register + login
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        payload = request.get_json(force=True)
        email = (payload.get("email") or "").strip().lower()
        pwd = payload.get("password") or ""
        users = load_users()
        if email in users and users[email]["password"] == pwd:
            session["user_email"] = email
            session["user_name"] = users[email].get("name", email)
            return jsonify({"status":"success"})
        return jsonify({"status":"fail","message":"Invalid credentials. Please check email/password."})
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json(force=True)
        name = data.get("name", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        empid_input = data.get("employee_id", "").strip()

        # validations
        if not name or not email or not password:
            return jsonify({"status":"fail","message":"Please fill all required fields."})
        if not validate_email_format(email):
            return jsonify({"status":"fail","message":"Please enter a valid email address."})
        valid_pw, msg = validate_password(password)
        if not valid_pw:
            return jsonify({"status":"fail","message": msg})

        # build employee id from digits or accept EMP... format
        emp_final = build_empid_from_digits(empid_input)
        if not emp_final:
            # if user didn't provide digits, auto-generate next one
            emp_final = generate_next_emp()

        users = load_users()
        if email in users:
            return jsonify({"status":"fail","message":"Email already registered. Please login."})

        # save user
        users[email] = {"name": name, "password": password, "employee_id": emp_final}
        save_users(users)

        # ensure employee record exists; create default if missing
        employees = load_employees()
        if email not in employees:
            employees[email] = {
                "name": name,
                "employee_id": emp_final,
                "leave_balance": {"casual": 6, "sick": 2, "earned": 4},
                "email_active": True,
                "attendance_status": "Present"
            }
            save_employees(employees)

        # Log the user in and redirect client-side
        session["user_email"] = email
        session["user_name"] = name

        return jsonify({"status":"success", "employee_id": emp_final})
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
# Main assistant route
# -------------------------
@app.route("/")
@login_required
def index():
    policies = read_json(POL_FILE)["policies"]
    return render_template("index.html", policies=policies, name=session.get("user_name", ""))

# -------------------------
# AI ASK endpoint
# -------------------------
@app.route("/ask", methods=["POST"])
@login_required
def ask():
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    email = (data.get("email") or session.get("user_email","")).strip().lower()

    intent = detect_intent(message)
    handler = HANDLERS.get(intent)

    if intent in ["leave_info", "email_status", "attendance"]:
        employees = load_employees()
        if email not in employees:
            return jsonify({"reply":"Employee details not present in HR records. Please contact HR."})
        reply = handler(email)
    else:
        reply = handler(message) if handler else "I didn't catch that. Try asking about your leave balance, booking a meeting room, or 'show policies'."
    return jsonify({"reply": reply})

@app.route("/reset", methods=["POST"])
@login_required
def reset():
    return jsonify({"status":"ok"})

@app.route("/me")
@login_required
def me():
    return jsonify({"email": session.get("user_email"), "name": session.get("user_name")})

# -------------------------
# Run app
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","5000")), debug=True)
