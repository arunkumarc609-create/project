from pathlib import Path
from datetime import datetime, timezone
import os
import re
import uuid
import joblib
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
MODEL_PATH = BASE_DIR / "ml" / "civic_model.joblib"
DATA_PATH = BASE_DIR / "ml" / "civic_issues.csv"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'civicpulse.db'}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
db = SQLAlchemy(app)

CATEGORIES = {
    "pothole": "Road / Pothole", "waste": "Waste", "water": "Water",
    "drainage": "Drainage", "streetlight": "Streetlight", "other": "Other"
}
DEPARTMENTS = {
    "pothole": "Road Department", "waste": "Sanitation Department",
    "water": "Water Department", "drainage": "Drainage Department",
    "streetlight": "Electrical Department", "other": "General Maintenance"
}
STATUSES = ["Submitted", "Verified", "Assigned", "In Progress", "Resolved", "Closed"]
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="citizen")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False, default="other")
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    severity = db.Column(db.Integer, nullable=False, default=3)
    safety_risk = db.Column(db.Integer, nullable=False, default=3)
    public_impact = db.Column(db.Integer, nullable=False, default=2)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location_label = db.Column(db.String(300), nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Submitted")
    department = db.Column(db.String(100), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    reporter = db.relationship("User", backref=db.backref("complaints", lazy=True))

class ComplaintEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    actor = db.relationship("User")

try:
    model = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None
except Exception:
    model = None


def current_user():
    from flask import session
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "categories": CATEGORIES, "statuses": STATUSES, "model_ready": model is not None}

@app.before_request
def load_model_if_available():
    global model
    if model is None and MODEL_PATH.exists():
        try:
            model = joblib.load(MODEL_PATH)
        except Exception:
            pass

def predict_category(description):
    if model is None:
        return "other", 0.0
    category = str(model.predict([description])[0])
    confidence = 0.0
    if hasattr(model, "predict_proba"):
        confidence = float(max(model.predict_proba([description])[0]))
    return category if category in CATEGORIES else "other", confidence

def priority_score(c):
    # Transparent weighted score, not a trained ML priority predictor.
    duplicate = min(5, 1 + (c.duplicate_count or 0))
    age_minutes = max(0, (datetime.now(timezone.utc) - ensure_utc(c.created_at)).total_seconds() / 60)
    waiting = min(5, 1 + age_minutes / 1440)  # increases over days, not seconds
    impact = min(5, c.public_impact)
    return round(0.30*c.severity + 0.25*c.safety_risk + 0.20*impact + 0.15*duplicate + 0.10*waiting, 2)

def ensure_utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def priority_tier(score):
    return "Critical" if score >= 4.3 else "High" if score >= 3.5 else "Medium" if score >= 2.5 else "Low"

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def require_login():
    user = current_user()
    if not user:
        flash("Please sign in to continue.", "error")
        return None
    return user

def require_authority():
    user = require_login()
    if user is None:
        return None
    if user.role != "authority":
        abort(403)
    return user

@app.get("/")
def index():
    user = current_user()
    if not user:
        return render_template("index.html", complaints=[], stats={})
    if user.role == "authority":
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    else:
        complaints = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.created_at.desc()).all()
    stats = {
        "total": Complaint.query.count() if user.role == "authority" else len(complaints),
        "critical": sum(1 for c in complaints if priority_tier(priority_score(c)) == "Critical"),
        "progress": sum(1 for c in complaints if c.status in ("Assigned", "In Progress")),
        "resolved": sum(1 for c in complaints if c.status in ("Resolved", "Closed")),
    }
    return render_template("index.html", complaints=complaints, stats=stats, score=priority_score, tier=priority_tier)

@app.post("/register")
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if len(name) < 2 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(password) < 8:
        flash("Enter a name, valid email, and password with at least 8 characters.", "error")
        return redirect(url_for("index"))
    if User.query.filter_by(email=email).first():
        flash("An account with that email already exists.", "error")
        return redirect(url_for("index"))
    user = User(name=name, email=email, password_hash=generate_password_hash(password), role="citizen")
    db.session.add(user); db.session.commit()
    from flask import session
    session["user_id"] = user.id
    flash("Account created. You can now submit a complaint.", "success")
    return redirect(url_for("index"))

@app.post("/login")
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        flash("Incorrect email or password.", "error")
        return redirect(url_for("index"))
    from flask import session
    session.clear(); session["user_id"] = user.id
    flash("Signed in successfully.", "success")
    return redirect(url_for("index"))

@app.post("/logout")
def logout():
    from flask import session
    session.clear()
    return redirect(url_for("index"))

@app.post("/api/predict")
def api_predict():
    data = request.get_json(silent=True) or {}
    description = str(data.get("description", "")).strip()
    if len(description) < 6:
        return jsonify(error="Description must contain at least 6 characters."), 400
    category, confidence = predict_category(description)
    return jsonify(category=category, label=CATEGORIES[category], confidence=round(confidence, 4), model_ready=model is not None)

@app.post("/complaints")
def create_complaint():
    user = require_login()
    if user is None: return redirect(url_for("index"))
    description = request.form.get("description", "").strip()
    if len(description) < 6 or len(description) > 4000:
        flash("Description must be between 6 and 4,000 characters.", "error"); return redirect(url_for("index"))
    try:
        lat, lng = float(request.form.get("latitude", "")), float(request.form.get("longitude", ""))
        severity = int(request.form.get("severity", 3)); risk = int(request.form.get("safety_risk", 3))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180): raise ValueError()
        if not (1 <= severity <= 5 and 1 <= risk <= 5): raise ValueError()
    except (TypeError, ValueError):
        flash("Choose a valid map location and severity/risk rating.", "error"); return redirect(url_for("index"))
    category, confidence = predict_category(description)
    sensitive = request.form.get("near_sensitive") == "on"
    impacts = {"pothole": 4, "water": 4, "drainage": 3, "waste": 3, "streetlight": 2, "other": 2}
    photo_filename = None
    photo = request.files.get("photo")
    if photo and photo.filename:
        if not allowed_file(photo.filename):
            flash("Photo must be PNG, JPG, JPEG, or WEBP.", "error"); return redirect(url_for("index"))
        ext = secure_filename(photo.filename).rsplit(".", 1)[1].lower()
        photo_filename = f"{uuid.uuid4().hex}.{ext}"
        photo.save(UPLOAD_DIR / photo_filename)
    complaint = Complaint(
        user_id=user.id, description=description, category=category, confidence=confidence,
        severity=severity, safety_risk=risk, public_impact=min(5, impacts[category] + int(sensitive)),
        latitude=lat, longitude=lng, location_label=request.form.get("location_label", "")[:300],
        photo_filename=photo_filename, status="Submitted"
    )
    db.session.add(complaint); db.session.flush()
    db.session.add(ComplaintEvent(complaint_id=complaint.id, actor_id=user.id, old_status=None, new_status="Submitted", note="Complaint submitted"))
    db.session.commit()
    flash(f"Complaint #{complaint.id} submitted. Predicted category: {CATEGORIES[category]}.", "success")
    return redirect(url_for("index"))

@app.post("/complaints/<int:complaint_id>/update")
def update_complaint(complaint_id):
    user = require_authority()
    if user is None: return redirect(url_for("index"))
    c = db.session.get(Complaint, complaint_id)
    if not c: abort(404)
    status = request.form.get("status", "")
    if status not in STATUSES:
        flash("Invalid status.", "error"); return redirect(url_for("index"))
    old = c.status
    c.status = status
    c.department = request.form.get("department", DEPARTMENTS[c.category])[:100]
    c.resolution_note = request.form.get("note", "").strip()[:2000]
    db.session.add(ComplaintEvent(complaint_id=c.id, actor_id=user.id, old_status=old, new_status=status, note=c.resolution_note))
    db.session.commit()
    flash(f"Complaint #{c.id} updated.", "success")
    return redirect(url_for("index"))

@app.get("/complaints/<int:complaint_id>/track")
def track_complaint(complaint_id):
    user = require_login()
    if user is None: return redirect(url_for("index"))
    c = db.session.get(Complaint, complaint_id)
    if not c: abort(404)
    if user.role != "authority" and c.user_id != user.id: abort(403)
    events = ComplaintEvent.query.filter_by(complaint_id=c.id).order_by(ComplaintEvent.created_at.asc()).all()
    return render_template("track.html", complaint=c, events=events, score=priority_score, tier=priority_tier)

@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    user = require_login()
    if user is None: abort(403)
    # Uploaded evidence is only accessible to the reporter or an authority.
    complaint = Complaint.query.filter_by(photo_filename=filename).first()
    if not complaint or (user.role != "authority" and complaint.user_id != user.id): abort(403)
    return send_from_directory(UPLOAD_DIR, filename)

@app.get("/api/complaints/map")
def map_complaints():
    user = require_login()
    if user is None: return jsonify(error="Authentication required"), 401
    q = Complaint.query if user.role == "authority" else Complaint.query.filter_by(user_id=user.id)
    rows = q.all()
    return jsonify([{"id": c.id, "category": CATEGORIES[c.category], "description": c.description,
        "latitude": c.latitude, "longitude": c.longitude, "status": c.status,
        "priority": priority_score(c), "tier": priority_tier(priority_score(c))} for c in rows])

with app.app_context():
    db.create_all()
    # Optional first-run authority account. Override both values with environment variables.
    admin_email = os.environ.get("CIVICPULSE_ADMIN_EMAIL", "admin@civicpulse.local").lower()
    admin_password = os.environ.get("CIVICPULSE_ADMIN_PASSWORD", "ChangeMe123!")
    if not User.query.filter_by(email=admin_email).first():
        db.session.add(User(name="Civic Authority Admin", email=admin_email,
            password_hash=generate_password_hash(admin_password), role="authority"))
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
