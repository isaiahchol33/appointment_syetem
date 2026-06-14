from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    jsonify,
    request
)
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import Appointment

analytics = Blueprint("analytics", __name__)


# =========================================================
# MAIN DASHBOARD PAGE
# =========================================================
@analytics.route("/analytics")
@login_required
def analytics_dashboard():

    if current_user.role != "admin":
        flash("Access denied. Administrator privileges required.", "danger")
        return redirect(url_for("appointments.dashboard"))

    range_filter = request.args.get("range", "all")

    appointments = Appointment.query.all()

    today = datetime.utcnow().date()
    cutoff = datetime.utcnow() - timedelta(days=30)

    # =========================
    # FILTER
    # =========================
    if range_filter == "today":
        filtered = []
        for a in appointments:
            d = getattr(a, "appointment_date", None)

            if not d:
                continue

            # FIX: handle BOTH datetime and date safely
            if isinstance(d, datetime):
                d = d.date()

            if d == today:
                filtered.append(a)

        appointments = filtered

    elif range_filter == "monthly":
        appointments = [
            a for a in appointments
            if getattr(a, "created_at", None)
            and a.created_at >= cutoff
        ]

    # =========================
    # STATS
    # =========================
    total = len(appointments)

    approved = sum(1 for a in appointments if (a.status or "").lower() == "approved")
    pending = sum(1 for a in appointments if (a.status or "").lower() == "pending")
    rejected = sum(1 for a in appointments if (a.status or "").lower() == "rejected")

    # =========================
    # SERVICE
    # =========================
    service_map = {
        "speaker_consultation": "Speaker Consultation",
        "public": "Public Policy",
        "committee_review": "Committee Review",
        "official_delegation": "Official Delegation",
        "other": "Other"
    }

    service_data = {}

    for a in appointments:
        raw = (a.service or "").strip().lower()

        if not raw:
            label = "Unspecified"
        else:
            label = service_map.get(raw, raw.replace("_", " ").title())

        service_data[label] = service_data.get(label, 0) + 1

    # =========================
    # MONTHLY
    # =========================
    monthly_requests = {}

    for a in appointments:
        if getattr(a, "created_at", None):
            key = a.created_at.strftime("%b %Y")
            monthly_requests[key] = monthly_requests.get(key, 0) + 1

    # =========================
    # TODAY COUNT (SAFE FIX)
    # =========================
    today_meetings = 0

    for a in appointments:
        d = getattr(a, "appointment_date", None)

        if not d:
            continue

        if isinstance(d, datetime):
            d = d.date()

        if d == today:
            today_meetings += 1

    status_data = {
        "Approved": approved,
        "Pending": pending,
        "Rejected": rejected
    }

    # =========================
    # 🔥 JSON RESPONSE FOR AJAX
    # =========================
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
            "today_meetings": today_meetings,
            "status_data": status_data,
            "service_data": service_data,
            "monthly_requests": monthly_requests
        })

    # =========================
    # NORMAL PAGE LOAD
    # =========================
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
        filter_type=range_filter
    )


# =========================================================
# API FOR FILTERED CHART DATA (IMPORTANT FIX)
# =========================================================
@analytics.route("/analytics/api")
@login_required
def analytics_api():

    if current_user.role != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    filter_type = request.args.get("range", "all")

    appointments = Appointment.query.all()

    today = date.today()
    cutoff = datetime.utcnow() - timedelta(days=30)

    def safe_date(val):
        if not val:
            return None
        if isinstance(val, datetime):
            return val.date()
        return val

    # =========================
    # FILTERING
    # =========================
    if filter_type == "today":
        appointments = [
            a for a in appointments
            if safe_date(getattr(a, "appointment_date", None)) == today
        ]

    elif filter_type == "monthly":
        appointments = [
            a for a in appointments
            if getattr(a, "created_at", None)
            and a.created_at >= cutoff
        ]

    # =========================
    # STATS
    # =========================
    total = len(appointments)

    approved = sum(1 for a in appointments if (a.status or "").lower() == "approved")
    pending = sum(1 for a in appointments if (a.status or "").lower() == "pending")
    rejected = sum(1 for a in appointments if (a.status or "").lower() == "rejected")

    # =========================
    # SERVICE DATA
    # =========================
    service_data = {}
    for a in appointments:
        raw = (a.service or "").strip().lower()
        service_data[raw] = service_data.get(raw, 0) + 1

    # =========================
    # MONTHLY DATA
    # =========================
    monthly = {}
    for a in appointments:
        if a.created_at:
            key = a.created_at.strftime("%b %Y")
            monthly[key] = monthly.get(key, 0) + 1

    # =========================
    # TODAY COUNT
    # =========================
    today_meetings = sum(
        1 for a in appointments
        if safe_date(getattr(a, "appointment_date", None)) == today
    )

    return jsonify({
        "total": total,
        "approved": approved,
        "pending": pending,
        "rejected": rejected,
        "status_data": {
            "Approved": approved,
            "Pending": pending,
            "Rejected": rejected
        },
        "service_data": service_data,
        "monthly_requests": monthly,
        "today_meetings": today_meetings
    })