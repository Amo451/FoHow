"""
FoHow Natural Solutions — backend server (Supabase version).

Serves the existing admin UI (static/index.html, unmodified design) and a
small REST API backed by Supabase PostgreSQL. Run with:

    python3 app.py

Then open http://localhost:5000 in a browser.
"""
import os
import uuid
import secrets
import datetime
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables - only in development
if os.environ.get("VERCEL_ENV") != "production":
    load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Determine if running on Vercel
IS_VERCEL = os.environ.get("VERCEL_ENV") is not None

app = Flask(__name__, static_folder="static", static_url_path="/static")

# ---------------------------------------------------------------------
# Supabase Setup
# ---------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY")

if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
    print("⚠️  WARNING: SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be set as environment variables")
    if not IS_VERCEL:
        print("⚠️  Make sure they are in your .env file")
    print("⚠️  Using fallback mode - some features may not work")

# Initialize Supabase client
try:
    supabase: Client = create_client(
        SUPABASE_URL or "https://fallback-url.supabase.co",
        SUPABASE_PUBLISHABLE_KEY or "fallback-key"
    )
except Exception as e:
    print(f"⚠️ Failed to initialize Supabase client: {e}")
    supabase = None

# ---------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
_DEFAULT_PASSWORD = "changeme123"
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH") or generate_password_hash(_DEFAULT_PASSWORD)

if not os.environ.get("ADMIN_PASSWORD_HASH"):
    print(
        f"\n[!] No ADMIN_PASSWORD_HASH set — using the default login "
        f"admin / {_DEFAULT_PASSWORD}\n"
        f"    Run `python3 set_password.py <your-password>` and set the "
        f"printed values as environment variables before deploying.\n"
    )
if not os.environ.get("SECRET_KEY") and not IS_VERCEL:
    print(
        "[!] No SECRET_KEY set — using a random one generated for this run. "
        "Everyone will be logged out on restart. Set SECRET_KEY as an "
        "environment variable to avoid that.\n"
    )

# Ensure static folder exists
static_folder = os.path.join(BASE_DIR, "static")
if not os.path.exists(static_folder):
    os.makedirs(static_folder)
    print(f"Created static folder at {static_folder}")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def today():
    return datetime.date.today().isoformat()


def row_to_dict(data):
    """Convert Supabase response to dict"""
    if isinstance(data, list):
        return [dict(item) for item in data] if data else []
    return dict(data) if data else {}


# ---------------------------------------------------------------------
# Serializers: DB column names -> the field names the front-end JS expects
# (keeps the existing index.html render logic untouched)
# ---------------------------------------------------------------------
def student_out(r):
    return {
        "id": r["id"], "name": r["name"], "phone": r.get("phone", ""),
        "location": r.get("location", ""), "date": r.get("date_joined", ""), "notes": r.get("notes", ""),
    }


def distributor_out(r, points_log_map):
    return {
        "id": r["id"], "name": r["name"], "phone": r.get("phone", ""),
        "location": r.get("location", ""), "date": r.get("active_since", ""), "notes": r.get("notes", ""),
        "points": r.get("points", 0), "qualified": bool(r.get("qualified", False)),
        "qualifiedDate": r.get("qualified_date", ""),
        "pointsLog": points_log_map.get(r["id"], []),
    }


def client_out(r):
    return {
        "id": r["id"], "name": r["name"], "phone": r.get("phone", ""),
        "referredBy": r.get("referred_by", ""), "date": r.get("purchase_date", ""),
        "products": r.get("products", ""), "amount": r.get("amount", 0),
        "location": r.get("location", ""), "notes": r.get("notes", ""),
    }


def sale_out(r):
    return {
        "id": r["id"], "distId": r["distributor_id"], "clientId": r.get("client_id", ""),
        "products": r.get("products", ""), "date": r.get("sale_date", ""), "value": r.get("sale_value", 0),
        "commission": r.get("commission_amount", 0), "commissionRate": r.get("commission_rate", 10),
        "notes": r.get("notes", ""), "paid": bool(r.get("paid", False)), 
        "paidDate": r.get("paid_date", ""), "paidMethod": r.get("paid_method", ""), "paidRef": r.get("paid_ref", ""),
    }


def resource_out(r):
    return {
        "id": r["id"], "title": r["title"], "type": r.get("type", "other"), 
        "link": r.get("link", ""), "desc": r.get("description", ""), "date": r.get("date_added", ""),
    }
def medicine_out(r):
    return {
        "id": r["id"], 
        "name": r["name"], 
        "description": r.get("description", ""),
        "points": r.get("points", 0),
        "category": r.get("category", ""),
        "date_added": r.get("date_added", ""),
    }

# ---------------------------------------------------------------------
# Auth: session-based login gate in front of the whole app
# ---------------------------------------------------------------------
PUBLIC_PATHS = {"/login", "/favicon.ico", "/api/health"}


@app.before_request
def require_login():
    # Skip auth for public paths
    if request.path in PUBLIC_PATHS:
        return
    if request.path.startswith("/static/"):
        return
    
    # Skip auth for health check
    if request.path.startswith("/api/health"):
        return
    
    if not session.get("logged_in"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not authenticated"}), 401
        return redirect(url_for("login"))


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FoHow Natural Solutions — Sign in</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Georgia,serif;background:#f7f4f0;color:#1a1614;min-height:100vh;
     display:flex;align-items:center;justify-content:center}
.card{background:#fff;border:1px solid #e0d8d0;border-radius:12px;padding:32px;
      width:min(340px,90vw);box-shadow:0 1px 3px rgba(0,0,0,0.08)}
.mark{width:44px;height:44px;border-radius:50%;border:2px solid #8B1A1A;color:#8B1A1A;
      display:flex;align-items:center;justify-content:center;font-weight:700;
      font-size:14px;margin:0 auto 14px}
h1{font-size:16px;text-align:center;margin-bottom:4px}
p.sub{font-size:12px;color:#6b5f57;text-align:center;margin-bottom:20px;font-style:italic}
label{font-size:11px;font-weight:600;color:#6b5f57;text-transform:uppercase;
      letter-spacing:0.5px;display:block;margin-bottom:5px}
input{width:100%;padding:9px 11px;border:1px solid #c8bfb5;border-radius:8px;
      font-size:13px;font-family:inherit;margin-bottom:14px}
input:focus{outline:none;border-color:#8B1A1A}
button{width:100%;padding:10px;border-radius:8px;border:1px solid #8B1A1A;
       background:#8B1A1A;color:#f5e6a3;font-size:13px;font-weight:600;
       cursor:pointer;font-family:inherit}
button:hover{background:#6e1515}
.err{background:#fdf0f0;color:#5c1010;border:1px solid #e8b8b8;border-radius:8px;
     padding:8px 12px;font-size:12px;margin-bottom:14px}
</style></head>
<body>
<form class="card" method="POST" action="/login">
  <div class="mark">FH</div>
  <h1>FoHow Natural Solutions</h1>
  <p class="sub">Admin Management System</p>
  {{ERROR}}
  <label>Username</label>
  <input type="text" name="username" autofocus required>
  <label>Password</label>
  <input type="password" name="password" required>
  <button type="submit">Sign in</button>
</form>
</body></html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    error_html = ""
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, p):
            session.clear()
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("index"))
        error_html = '<div class="err">Incorrect username or password</div>'
    return LOGIN_PAGE.replace("{{ERROR}}", error_html)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# Serve static files
@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory(app.static_folder, path)


# ---------------------------------------------------------------------
# Combined read: everything the UI needs on load / after any mutation
# ---------------------------------------------------------------------
@app.route("/api/all")
def api_all():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        # Get students
        students_resp = supabase.table('students').select('*').order('created_at').execute()
        students = [student_out(r) for r in students_resp.data] if students_resp.data else []

        # Get points log and build map
        pts_resp = supabase.table('points_log').select('*').order('created_at').execute()
        pts_map = {}
        if pts_resp.data:
            for r in pts_resp.data:
                pts_map.setdefault(r["distributor_id"], []).append({
                    "pts": r["points"], "reason": r.get("reason", ""), 
                    "notes": r.get("notes", ""), "date": r.get("log_date", ""),
                })

        # Get distributors
        dist_resp = supabase.table('distributors').select('*').order('created_at').execute()
        distributors = [distributor_out(r, pts_map) for r in dist_resp.data] if dist_resp.data else []

        # Get clients
        clients_resp = supabase.table('clients').select('*').order('created_at').execute()
        clients = [client_out(r) for r in clients_resp.data] if clients_resp.data else []

        # Get sales
        sales_resp = supabase.table('sales').select('*').order('created_at').execute()
        sales = [sale_out(r) for r in sales_resp.data] if sales_resp.data else []

                # Get resources
        resources_resp = supabase.table('resources').select('*').order('created_at').execute()
        resources = [resource_out(r) for r in resources_resp.data] if resources_resp.data else []

        # Get medicines
        medicines_resp = supabase.table('medicines').select('*').order('name').execute()
        medicines = [medicine_out(r) for r in medicines_resp.data] if medicines_resp.data else []

        return jsonify({
            "students": students,
            "distributors": distributors,
            "clients": clients,
            "sales": sales,
            "resources": resources,
            "medicines": medicines,
        })
    except Exception as e:
        print(f"Error in /api/all: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------
# STUDENTS
# ---------------------------------------------------------------------
@app.route("/api/students", methods=["POST"])
def create_student():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        if not d.get("name", "").strip():
            return jsonify({"error": "Name is required"}), 400
        
        sid = uid("s")
        data = {
            "id": sid,
            "name": d["name"].strip(),
            "phone": d.get("phone", ""),
            "location": d.get("location", ""),
            "date_joined": d.get("date") or today(),
            "notes": d.get("notes", ""),
        }
        supabase.table('students').insert(data).execute()
        return jsonify({"id": sid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/students/<sid>", methods=["PUT"])
def update_student(sid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        data = {
            "name": d.get("name", ""),
            "phone": d.get("phone", ""),
            "location": d.get("location", ""),
            "date_joined": d.get("date", ""),
            "notes": d.get("notes", ""),
        }
        supabase.table('students').update(data).eq('id', sid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/students/<sid>", methods=["DELETE"])
def delete_student(sid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        supabase.table('students').delete().eq('id', sid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/students/<sid>/promote", methods=["POST"])
def promote_student(sid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        # Get student
        student_resp = supabase.table('students').select('*').eq('id', sid).execute()
        if not student_resp.data:
            return jsonify({"error": "Student not found"}), 404
        
        s = student_resp.data[0]
        did = uid("d")
        
        # Create distributor
        dist_data = {
            "id": did,
            "name": s["name"],
            "phone": s.get("phone", ""),
            "location": s.get("location", ""),
            "active_since": today(),
            "notes": s.get("notes", ""),
            "promoted_from_student_id": sid,
        }
        supabase.table('distributors').insert(dist_data).execute()
        
        # Delete student
        supabase.table('students').delete().eq('id', sid).execute()
        
        return jsonify({"id": did}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------
# DISTRIBUTORS
# ---------------------------------------------------------------------
@app.route("/api/distributors", methods=["POST"])
def create_distributor():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        if not d.get("name", "").strip():
            return jsonify({"error": "Name is required"}), 400
        
        did = uid("d")
        from_student_id = d.get("fromStudentId") or None
        
        data = {
            "id": did,
            "name": d["name"].strip(),
            "phone": d.get("phone", ""),
            "location": d.get("location", ""),
            "active_since": d.get("date") or today(),
            "notes": d.get("notes", ""),
            "promoted_from_student_id": from_student_id,
        }
        supabase.table('distributors').insert(data).execute()
        
        if from_student_id:
            supabase.table('students').delete().eq('id', from_student_id).execute()
        
        return jsonify({"id": did}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/distributors/<did>", methods=["PUT"])
def update_distributor(did):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        data = {
            "name": d.get("name", ""),
            "phone": d.get("phone", ""),
            "location": d.get("location", ""),
            "active_since": d.get("date", ""),
            "notes": d.get("notes", ""),
        }
        supabase.table('distributors').update(data).eq('id', did).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/distributors/<did>", methods=["DELETE"])
def delete_distributor(did):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        supabase.table('distributors').delete().eq('id', did).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/distributors/<did>/points", methods=["POST"])
def award_points(did):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        pts = int(d.get("pts") or 0)
        if pts <= 0:
            return jsonify({"error": "Enter a valid number of points"}), 400
        
        # Check if distributor exists and get current qualified status
        dist_resp = supabase.table('distributors').select('qualified').eq('id', did).execute()
        if not dist_resp.data:
            return jsonify({"error": "Distributor not found"}), 404
        
        was_qualified = bool(dist_resp.data[0].get("qualified", False))
        
        # Insert points (trigger will auto-add to points and qualify if >= 500)
        log_data = {
            "distributor_id": did,
            "points": pts,
            "reason": d.get("reason", ""),
            "notes": d.get("notes", ""),
            "log_date": today(),
        }
        supabase.table('points_log').insert(log_data).execute()
        
        # Get updated distributor info
        updated_resp = supabase.table('distributors').select('points, qualified').eq('id', did).execute()
        after = updated_resp.data[0]
        promoted = (not was_qualified) and bool(after.get("qualified", False))
        
        return jsonify({"ok": True, "points": after.get("points", 0), "promoted": promoted}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/distributors/<did>/qualify", methods=["POST"])
def manual_qualify(did):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        data = {
            "qualified": 1,
            "qualified_date": today()
        }
        supabase.table('distributors').update(data).eq('id', did).eq('qualified', 0).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------
# CLIENTS
# ---------------------------------------------------------------------
@app.route("/api/clients", methods=["POST"])
def create_client():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        if not d.get("name", "").strip():
            return jsonify({"error": "Name is required"}), 400
        
        cid = uid("cl")
        data = {
            "id": cid,
            "name": d["name"].strip(),
            "phone": d.get("phone", ""),
            "referred_by": d.get("referredBy") or None,
            "purchase_date": d.get("date") or today(),
            "products": d.get("products", ""),
            "amount": float(d.get("amount") or 0),
            "location": d.get("location", ""),
            "notes": d.get("notes", ""),
        }
        supabase.table('clients').insert(data).execute()
        return jsonify({"id": cid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/clients/<cid>", methods=["DELETE"])
def delete_client(cid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        supabase.table('clients').delete().eq('id', cid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------
# SALES / COMMISSIONS
# ---------------------------------------------------------------------
@app.route("/api/sales", methods=["POST"])
def create_sale():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        dist_id = d.get("distId")
        value = float(d.get("value") or 0)
        points = int(d.get("points") or 0)  # NEW: Get points from request
        
        if not dist_id:
            return jsonify({"error": "Please select a distributor"}), 400
        if not value:
            return jsonify({"error": "Please enter a sale value"}), 400
        
        sid = uid("sl")
        data = {
            "id": sid,
            "distributor_id": dist_id,
            "client_id": d.get("clientId") or None,
            "products": d.get("products", ""),
            "sale_date": d.get("date") or today(),
            "sale_value": value,
            "commission_rate": float(d.get("commissionRate") or 10),
            "commission_amount": float(d.get("commission") or 0),
            "notes": d.get("notes", ""),
            "paid": 0,
        }
        supabase.table('sales').insert(data).execute()
        
        # NEW: Award points to distributor if any
        if points > 0:
            log_data = {
                "distributor_id": dist_id,
                "points": points,
                "reason": f"Sale #{sid} - {data['products']}",
                "notes": f"Points from sale recorded on {data['sale_date']}",
                "log_date": today(),
            }
            supabase.table('points_log').insert(log_data).execute()
            print(f"✅ Awarded {points} points to distributor {dist_id} for sale {sid}")
        
        return jsonify({"id": sid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/sales/<sid>", methods=["DELETE"])
def delete_sale(sid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        supabase.table('sales').delete().eq('id', sid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/sales/<sid>/pay", methods=["POST"])
def pay_sale(sid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        data = {
            "paid": 1,
            "paid_date": d.get("date") or today(),
            "paid_method": d.get("method", ""),
            "paid_ref": d.get("ref", ""),
        }
        supabase.table('sales').update(data).eq('id', sid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------
# RESOURCES
# ---------------------------------------------------------------------
@app.route("/api/resources", methods=["POST"])
def create_resource():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        if not d.get("title", "").strip():
            return jsonify({"error": "Title is required"}), 400
        
        rid = uid("r")
        data = {
            "id": rid,
            "title": d["title"].strip(),
            "type": d.get("type", "other"),
            "link": d.get("link", ""),
            "description": d.get("desc", ""),
            "date_added": today(),
        }
        supabase.table('resources').insert(data).execute()
        return jsonify({"id": rid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/resources/<rid>", methods=["DELETE"])
def delete_resource(rid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        supabase.table('resources').delete().eq('id', rid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------------------------------------------------------------
# MEDICINES
# ---------------------------------------------------------------------
@app.route("/api/medicines", methods=["GET"])
def get_medicines():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        response = supabase.table('medicines').select('*').order('name').execute()
        medicines = [medicine_out(r) for r in response.data] if response.data else []
        return jsonify(medicines)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/medicines", methods=["POST"])
def create_medicine():
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        if not d.get("name", "").strip():
            return jsonify({"error": "Name is required"}), 400
        
        mid = uid("m")
        data = {
            "id": mid,
            "name": d["name"].strip(),
            "description": d.get("description", ""),
            "points": int(d.get("points") or 0),
            "category": d.get("category", ""),
            "date_added": today(),
        }
        supabase.table('medicines').insert(data).execute()
        return jsonify({"id": mid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/medicines/<mid>", methods=["PUT"])
def update_medicine(mid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        d = request.get_json(force=True)
        data = {
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "points": int(d.get("points") or 0),
            "category": d.get("category", ""),
        }
        supabase.table('medicines').update(data).eq('id', mid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/medicines/<mid>", methods=["DELETE"])
def delete_medicine(mid):
    if supabase is None:
        return jsonify({"error": "Supabase client not initialized"}), 500
    
    try:
        supabase.table('medicines').delete().eq('id', mid).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------
@app.route("/api/health")
def health():
    if supabase is None:
        return jsonify({
            "status": "unhealthy",
            "database": "supabase",
            "connected": False,
            "error": "Supabase client not initialized"
        }), 500
    
    try:
        # Test Supabase connection
        supabase.table('students').select('id').limit(1).execute()
        return jsonify({
            "status": "healthy",
            "database": "supabase",
            "connected": True,
            "environment": "production" if IS_VERCEL else "development"
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "supabase",
            "connected": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------------------
# Root path for Vercel compatibility
# ---------------------------------------------------------------------
@app.route('/vercel')
def vercel_info():
    return jsonify({
        "status": "running",
        "environment": "Vercel",
        "message": "FoHow Natural Solutions API is live!"
    })


# For Vercel - the app object is the WSGI application
# This is what Vercel looks for
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print("🚀 Starting FoHow Natural Solutions with Supabase...")
    print(f"📊 Database: Supabase PostgreSQL")
    print(f"🌐 Server: http://localhost:{port}")
    print(f"🔑 Login: {ADMIN_USERNAME} / {_DEFAULT_PASSWORD if not os.environ.get('ADMIN_PASSWORD_HASH') else '[secure]'}")
    print(f"📦 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    app.run(host="0.0.0.0", port=port, debug=debug)
