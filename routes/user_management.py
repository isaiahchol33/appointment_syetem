from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, abort, send_file
)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

from database import db
from models import User
from forms import RegisterForm

import io
import pandas as pd

try:
    from app import socketio
except Exception:
    socketio = None


user_mgmt = Blueprint("user_mgmt", __name__)

ALLOWED_ROLES = [
    "user",
    "speaker",
    "d_speaker",
    "clerk",
    "mp",
    "admin"
]

# ==============================
# USERS LIST
# ==============================
@user_mgmt.route("/users")
@login_required
def users():

    if current_user.role != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("appointments.dashboard"))

    search = request.args.get("search", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()

    query = User.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(like)) |
            (User.email.ilike(like)) |
            (User.phone.ilike(like)) |
            (User.role.ilike(like))
        )

    if role:
        query = query.filter(User.role == role)

    if status == "active":
        query = query.filter(User.is_active_account.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active_account.is_(False))

    users = query.order_by(User.id.desc()).all()

    return render_template("users.html", users=users)


@user_mgmt.route("/users/create", methods=["POST"])
@login_required
def create_user():

    try:
        print("CREATE USER HIT")

        # =========================
        # AUTH CHECK
        # =========================
        if current_user.role != "admin":
            return jsonify({"error": "Access denied"}), 403

        # =========================
        # GET DATA SAFELY
        # =========================
        data = request.form or {}

        print("RAW FORM DATA:", data)

        full_name = (data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        phone = (data.get("phone") or "").strip()
        password = data.get("password") or ""
        confirm_password = data.get("confirm_password") or ""
        role = (data.get("role") or "").strip()
        department = (data.get("department") or "").strip()

        # =========================
        # VALIDATION
        # =========================
        if len(full_name) < 3:
            return jsonify({"error": "Full name too short"}), 400

        if any(char.isdigit() for char in full_name):
            return jsonify({"error": "Name cannot contain numbers"}), 400

        if not email or "@" not in email:
            return jsonify({"error": "Valid email required"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 400

        if len(password) < 8:
            return jsonify({"error": "Password too short"}), 400

        if password != confirm_password:
            return jsonify({"error": "Passwords do not match"}), 400

        allowed_roles = ["user", "speaker", "d_speaker", "clerk", "mp", "admin"]
        if role not in allowed_roles:
            return jsonify({"error": "Invalid role"}), 400

        # =========================
        # CREATE USER
        # =========================
        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            role=role,
            department=department,
            password=generate_password_hash(password),
            is_active_account=True
        )

        db.session.add(user)
        db.session.commit()

        print("USER CREATED SUCCESSFULLY")

        return jsonify({
            "success": True,
            "message": "User created successfully",
            "id": user.id
        }), 200

    except Exception as e:
        db.session.rollback()

        print("❌ ERROR:", str(e))

        # IMPORTANT: ALWAYS RETURN JSON
        return jsonify({
            "success": False,
            "error": "Server crashed",
            "details": str(e)
        }), 500
# ==============================
# INLINE EDIT USER (SAFE)
# ==============================
@user_mgmt.route("/users/edit/<int:id>", methods=["POST"])
@login_required
def edit_user(id):

    if current_user.role != "admin":
        return jsonify({"error": "Access denied"}), 403

    user = User.query.get_or_404(id)

    if user.role == "admin":
        return jsonify({"error": "Admin cannot be edited"}), 403

    allowed_fields = ["full_name", "email", "phone"]

    for field in allowed_fields:
        if field in request.form:
            value = request.form[field].strip()

            if field == "email":
                value = value.lower()
                if User.query.filter(User.email == value, User.id != id).first():
                    return jsonify({"error": "Email already exists"}), 400

            setattr(user, field, value)

    db.session.commit()

    if socketio:
        socketio.emit("user_update", {"action": "updated", "id": user.id})

    return jsonify({"success": True})


# ==============================
# BULK DELETE
# ==============================
@user_mgmt.route("/users/bulk-delete", methods=["POST"])
@login_required
def bulk_delete():

    if current_user.role != "admin":
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])

    if not ids:
        return jsonify({"error": "No IDs provided"}), 400

    users = User.query.filter(User.id.in_(ids)).all()

    deleted = []

    for u in users:
        if u.role != "admin":
            db.session.delete(u)
            deleted.append(u.id)

    db.session.commit()

    return jsonify({"success": True, "deleted": deleted})


# ==============================
# ACTIVATE / DEACTIVATE
# ==============================
@user_mgmt.route("/users/activate/<int:id>")
@login_required
def activate_user(id):

    if current_user.role != "admin":
        return jsonify({"error": "Access denied"}), 403

    user = User.query.get_or_404(id)

    if user.role == "admin":
        return jsonify({"error": "Admin cannot be modified"}), 403

    user.is_active_account = True
    db.session.commit()

    return jsonify({"success": True})


@user_mgmt.route("/users/deactivate/<int:id>")
@login_required
def deactivate_user(id):

    if current_user.role != "admin":
        return jsonify({"error": "Access denied"}), 403

    user = User.query.get_or_404(id)

    if user.role == "admin":
        return jsonify({"error": "Admin cannot be modified"}), 403

    user.is_active_account = False
    db.session.commit()

    return jsonify({"success": True})


# ==============================
# DELETE USER
# ==============================
@user_mgmt.route("/users/delete/<int:id>", methods=["POST"])
@login_required
def delete_user(id):

    if current_user.role != "admin":
        return jsonify({"error": "Access denied"}), 403

    user = User.query.get_or_404(id)

    if user.role == "admin":
        return jsonify({"error": "Admin cannot be deleted"}), 403

    db.session.delete(user)
    db.session.commit()

    return jsonify({"success": True})


# ==============================
# EXPORT USERS
# ==============================
@user_mgmt.route("/users/export")
@login_required
def export_users():

    if current_user.role != "admin":
        abort(403)

    users = User.query.all()

    data = [{
        "ID": u.id,
        "Name": u.full_name,
        "Email": u.email,
        "Phone": getattr(u, "phone", ""),
        "Role": u.role,
        "Status": "Active" if u.is_active_account else "Inactive"
    } for u in users]

    df = pd.DataFrame(data)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Users")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="users.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==============================
# PROFILE EDIT
# ==============================
@user_mgmt.route("/profile/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_profile(id):

    user = User.query.get_or_404(id)

    if user.id != current_user.id and current_user.role != "admin":
        abort(403)

    if request.method == "POST":

        user.full_name = request.form.get("full_name", "").strip()
        user.email = request.form.get("email", "").strip().lower()

        if hasattr(user, "phone"):
            user.phone = request.form.get("phone", "").strip()

        db.session.commit()

        flash("Profile updated successfully.", "success")

        return redirect(url_for("user_mgmt.edit_profile", id=user.id))

    all_users = User.query.order_by(User.full_name.asc()).all()

    return render_template(
        "edit_profile.html",
        user=user,
        all_users=all_users
    )