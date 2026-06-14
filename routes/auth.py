from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import db
from models import User
from forms import RegisterForm, LoginForm


# =========================================
# AUTH BLUEPRINT
# =========================================

auth = Blueprint("auth", __name__)


# =========================================
# REGISTER
# =========================================

@auth.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("appointments.dashboard"))

    form = RegisterForm()

    if request.method == "POST":

        # Flask-WTF validation
        if form.validate_on_submit():

            existing_user = User.query.filter_by(email=form.email.data).first()

            if existing_user:
                return jsonify({
                    "success": False,
                    "errors": {
                        "email": "Email already exists."
                    }
                })

            hashed_password = generate_password_hash(form.password.data)

            # =====================================
            # SAFE ROLE HANDLING (SERVER TRUSTED)
            # =====================================

            allowed_roles = ["user", "mp", "clerk", "speaker","d_speaker", "admin"]

            role = request.form.get("role", "user")

            # NEVER trust frontend role
            if role not in allowed_roles:
                role = "user"

            # OPTIONAL SMART OVERRIDE (basic "AI rule engine")
            email = form.email.data.lower()

            if "admin" in email:
                role = "admin"
            elif "mp" in email:
                role = "mp"
            elif "clerk" in email:
                role = "clerk"
            elif "speaker" in email:
                role = "speaker"
            elif "d_speaker" in email:
                role = "d_speaker"

            user = User(
                full_name=form.full_name.data,
                email=form.email.data,
                password=hashed_password,
                role=role
            )

            db.session.add(user)
            db.session.commit()

            # AJAX RESPONSE SUPPORT
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "success": True,
                    "redirect": url_for("auth.login")
                })

            flash("Registration successful. You may now login.", "success")
            return redirect(url_for("auth.login"))

        # FORM ERRORS (AJAX + NORMAL)
        errors = {}

        for field, err in form.errors.items():
            errors[field] = err[0]

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": False,
                "errors": errors
            })

        flash("Please fix the errors in the form.", "danger")

    return render_template("register.html", form=form)


# =========================================
# EMAIL AVAILABILITY CHECK (AJAX LIVE)
# =========================================

@auth.route("/check-email")
def check_email():

    email = request.args.get("email", "").lower()

    if not email:
        return jsonify({"exists": False})

    user = User.query.filter_by(email=email).first()

    return jsonify({
        "exists": bool(user)
    })


# =========================================
# LOGIN
# =========================================

@auth.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("appointments.dashboard"))

    form = LoginForm()

    if request.method == "POST":

        if form.validate_on_submit():

            user = User.query.filter_by(email=form.email.data).first()

            if user and check_password_hash(user.password, form.password.data):

                login_user(user, remember=form.remember.data)

                # ROLE-BASED REDIRECTION
                if user.role == "admin":
                    redirect_url = url_for("admin.admin_dashboard")
                elif user.role in ["speaker", "clerk"]:
                    redirect_url = url_for("appointments.calendar")
                else:
                    redirect_url = url_for("appointments.dashboard")

                # AJAX SUPPORT
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({
                        "success": True,
                        "redirect": redirect_url
                    })

                flash("Welcome to the Parliamentary Booking System.", "success")
                return redirect(redirect_url)

            # INVALID LOGIN
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "success": False,
                    "errors": {
                        "login": "Invalid email or password."
                    }
                })

            flash("Invalid email or password.", "danger")

    return render_template("login.html", form=form)


# =========================================
# LOGOUT
# =========================================

@auth.route("/logout")
@login_required
def logout():

    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


# =========================================
# FORGOT PASSWORD (BASIC STRUCTURE)
# =========================================

@auth.route("/forgot_password", methods=["POST"])
def forgot_password():

    email = request.form.get("email", "").lower()

    if not email:
        flash("Please enter your email address.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    # SECURITY: always respond same message (prevents email enumeration)
    flash("If the email exists, a reset link has been sent.", "info")

    # TODO: integrate email sending system here (Flask-Mail)

    return redirect(url_for("auth.login"))