from flask import (
    Blueprint,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    make_response
)

from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from database import db
from models import Appointment, User

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
from datetime import date, datetime,timedelta

from flask import make_response


# =========================================
# BLUEPRINT
# =========================================

admin = Blueprint("admin", __name__)


# =========================================
# ROLE ACCESS CONTROL
# =========================================

ALLOWED_ROLES = ["admin", "speaker", "clerk"]


def require_admin_panel_access():
    if (
        not current_user.is_authenticated
        or current_user.role.lower() not in ALLOWED_ROLES
    ):
        flash("Access denied. Authorized personnel only.", "danger")
        return False
    return True

# =========================
# SAFE DATE HELPER
# =========================
def safe_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value  # already date

# =========================================
# ADMIN DASHBOARD
# =========================================

@admin.route("/admin")
@login_required
def admin_dashboard():

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointments = Appointment.query.order_by(
        Appointment.created_at.desc()
    ).all()

    total = Appointment.query.count()
    pending = Appointment.query.filter_by(status="Pending").count()
    approved = Appointment.query.filter_by(status="Approved").count()
    rejected = Appointment.query.filter_by(status="Rejected").count()

    consultation = Appointment.query.filter_by(
        service="Speaker Consultation"
    ).count()

    committee = Appointment.query.filter_by(
        service="Committee Meeting"
    ).count()

    policy = Appointment.query.filter_by(
        service="Policy Discussion"
    ).count()

    delegation = Appointment.query.filter_by(
        service="Official Delegation"
    ).count()

    return render_template(
        "admin_dashboard.html",
        appointments=appointments,
        total=total,
        pending=pending,
        approved=approved,
        rejected=rejected,
        consultation=consultation,
        committee=committee,
        policy=policy,
        delegation=delegation
    )


# =========================================
# USER MANAGEMENT
# =========================================

@admin.route("/users")
@login_required
def user_management():

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    users = User.query.order_by(User.full_name.asc()).all()

    return render_template("user_management.html", users=users)


# =========================================
# CREATE USER
# =========================================

@admin.route("/users/create", methods=["POST"])
@login_required
def create_user():

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    full_name = request.form.get("full_name")
    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role")

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        flash("User with this email already exists.", "danger")
        return redirect(url_for("admin.user_management"))

    new_user = User(
        full_name=full_name,
        email=email,
        password=generate_password_hash(password),
        role=role
    )

    db.session.add(new_user)
    db.session.commit()

    flash("User created successfully.", "success")
    return redirect(url_for("admin.user_management"))


# =========================================
# DELETE USER
# =========================================

@admin.route("/users/delete/<int:id>")
@login_required
def delete_user(id):

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("admin.user_management"))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted successfully.", "info")
    return redirect(url_for("admin.user_management"))



# =========================
# MAIN ANALYTICS ROUTE
# =========================
@admin.route("/analytics")
@login_required
def analytics_dashboard():

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    from datetime import datetime, date, timedelta
    from flask import request, jsonify

    filter_type = request.args.get("range", "all")

    appointments = Appointment.query.all()

    today = date.today()
    cutoff_30 = datetime.utcnow() - timedelta(days=30)

    # ---------------- SAFE DATE ----------------
    def get_date(a):
        d = getattr(a, "appointment_date", None)
        if not d:
            return None
        if isinstance(d, datetime):
            return d.date()
        return d

    # ---------------- LAST MONTH LOGIC ----------------
    now = datetime.utcnow()
    first_day_this_month = date(today.year, today.month, 1)

    last_month_start = (first_day_this_month - timedelta(days=1)).replace(day=1)
    last_month_end = first_day_this_month - timedelta(days=1)

    # ---------------- FILTERS ----------------
    if filter_type == "today":
        appointments = [a for a in appointments if get_date(a) == today]

    elif filter_type == "monthly":
        appointments = [
            a for a in appointments
            if getattr(a, "created_at", None)
            and a.created_at >= cutoff_30
        ]

    elif filter_type == "last_month":
        appointments = [
            a for a in appointments
            if getattr(a, "created_at", None)
            and last_month_start <= a.created_at.date() <= last_month_end
        ]

    # ---------------- STATS ----------------
    total = len(appointments)

    approved = sum(1 for a in appointments if (a.status or "").lower() == "approved")
    pending = sum(1 for a in appointments if (a.status or "").lower() == "pending")
    rejected = sum(1 for a in appointments if (a.status or "").lower() == "rejected")

    # ---------------- SERVICE ----------------
    service_data = {}

    for a in appointments:
        raw = (a.service or "").strip().lower()
        label = raw.replace("_", " ").title() if raw else "Unspecified"
        service_data[label] = service_data.get(label, 0) + 1

    # ---------------- MONTHLY TREND ----------------
    monthly_requests = {}

    for a in appointments:
        if getattr(a, "created_at", None):
            key = a.created_at.strftime("%b %Y")
            monthly_requests[key] = monthly_requests.get(key, 0) + 1

    # ---------------- TODAY ----------------
    today_meetings = sum(1 for a in appointments if get_date(a) == today)

    status_data = {
        "Approved": approved,
        "Pending": pending,
        "Rejected": rejected
    }

    # ---------------- JSON (AJAX) ----------------
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
            "status_data": status_data,
            "service_data": service_data,
            "monthly_requests": monthly_requests,
            "today_meetings": today_meetings
        })

    # ---------------- TEMPLATE ----------------
    return render_template(
        "analytics_dashboard.html",
        total=total,
        approved=approved,
        pending=pending,
        rejected=rejected,
        today_meetings=today_meetings,
        status_data=status_data,
        service_data=service_data,
        monthly_requests=monthly_requests,
        filter_type=filter_type
    )
# =========================
# TODAY MEETINGS API (LIVE CARD)
# =========================
@admin.route("/analytics/today-meetings")
@login_required
def today_meetings_api():

    if not require_admin_panel_access():
        return jsonify({"error": "unauthorized"}), 403

    appointments = Appointment.query.all()

    today = datetime.utcnow().date()

    count = sum(
        1 for a in appointments
        if safe_date(getattr(a, "appointment_date", None)) == today
    )

    return jsonify({"today_meetings": count})
# =========================================
# APPROVE
# =========================================

@admin.route("/approve/<int:id>")
@login_required
def approve_appointment(id):

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointment = Appointment.query.get_or_404(id)
    appointment.status = "Approved"

    db.session.commit()

    flash("Meeting request approved successfully.", "success")
    return redirect(url_for("admin.admin_dashboard"))


# =========================================
# REJECT
# =========================================

@admin.route("/reject/<int:id>")
@login_required
def reject_appointment(id):

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointment = Appointment.query.get_or_404(id)
    appointment.status = "Rejected"

    db.session.commit()

    flash("Meeting request rejected.", "warning")
    return redirect(url_for("admin.admin_dashboard"))


# =========================================
# DELETE APPOINTMENT
# =========================================

@admin.route("/delete/<int:id>")
@login_required
def delete_appointment(id):

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointment = Appointment.query.get_or_404(id)

    db.session.delete(appointment)
    db.session.commit()

    flash("Meeting request deleted successfully.", "info")
    return redirect(url_for("admin.admin_dashboard"))


# =========================================
# VIEW (FOR MODAL AJAX)
# =========================================

@admin.route("/view/<int:id>")
@login_required
def view_appointment(id):

    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointment = Appointment.query.get_or_404(id)

    return render_template(
        "view_appointment.html",
        appointment=appointment
    )


@admin.route("/print-registry")
@login_required
def print_registry():
    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointments = Appointment.query.order_by(Appointment.created_at.desc()).all()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 60

    # HEADER
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, y, "REPUBLIC OF SOUTH SUDAN")
    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(width / 2, y, "PARLIAMENTARY SPEAKER OFFICE")
    y -= 30
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "OFFICIAL APPOINTMENT REGISTRY")
    y -= 25

    # TABLE HEADER
    p.setFont("Helvetica-Bold", 9)
    p.drawString(40, y, "Name")
    p.drawString(160, y, "Service")
    p.drawString(300, y, "Date")
    p.drawString(420, y, "Status")
    y -= 15
    p.line(40, y, 550, y)
    y -= 15

    # DATA
    p.setFont("Helvetica", 8)
    for a in appointments:
        if y < 60:
            p.showPage()
            y = height - 60
        p.drawString(40, y, str(a.guest_name)[:18])
        p.drawString(160, y, str(a.service)[:20])
        p.drawString(300, y, str(a.appointment_date))
        p.drawString(420, y, str(a.status))
        y -= 15

    # FOOTER
    p.setFont("Helvetica-Oblique", 8)
    p.drawCentredString(width / 2, 40, "Official Parliamentary Record System")

    p.save()
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=registry.pdf"
    return response


@admin.route("/appointment/pdf/<int:id>")
def appointment_pdf(id):
    appointment = Appointment.query.get_or_404(id)
    return render_template("appointment_pdf.html", appointment=appointment)

# =========================================
# PRINT PDF (OFFICIAL PARLIAMENT STYLE)
# =========================================
@admin.route("/print/<int:id>")
@login_required
def print_appointment_pdf(id):
    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointment = Appointment.query.get_or_404(id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # HEADER
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 80, "REPUBLIC OF SOUTH SUDAN")
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 105, "PARLIAMENTARY SPEAKER OFFICE")
    p.setFont("Helvetica", 11)
    p.drawCentredString(width / 2, height - 125, "OFFICIAL APPOINTMENT CONFIRMATION")
    p.line(50, height - 140, width - 50, height - 140)

    # BODY
    y = height - 200
    p.setFont("Helvetica", 12)
    p.drawString(80, y, f"Citizen Name: {appointment.guest_name}"); y -= 25
    p.drawString(80, y, f"Email: {appointment.email}"); y -= 25
    p.drawString(80, y, f"Service: {appointment.service}"); y -= 25
    p.drawString(80, y, f"Appointment Date: {appointment.appointment_date}"); y -= 25
    p.drawString(80, y, f"Status: {appointment.status}"); y -= 40

    # SIGNATURE
    p.line(80, y, 250, y)
    p.drawString(80, y - 15, "Speaker / Authorized Officer")
    p.line(350, y, 520, y)
    p.drawString(350, y - 15, "Official Stamp")

    # FOOTER
    p.setFont("Helvetica-Oblique", 9)
    p.drawCentredString(width / 2, 50, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    p.showPage()
    p.save()
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=appointment_{id}.pdf"
    return response


# =========================================
# PRINT HTML (RENDER appointment_pdf.html)
# =========================================
@admin.route("/appointments/<int:id>/print", methods=["GET"])
@login_required
def print_appointment_html(id):
    if not require_admin_panel_access():
        return redirect(url_for("appointments.dashboard"))

    appointment = Appointment.query.get_or_404(id)
    return render_template("appointment_pdf.html", appointment=appointment)