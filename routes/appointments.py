from flask import (
    Blueprint, abort, render_template, redirect, url_for,
    flash, request, jsonify, send_file, make_response
)
from flask_login import login_required, current_user
from datetime import datetime as dt, timedelta
from sqlalchemy import or_, extract
from collections import OrderedDict, Counter
import pandas as pd
import io

from database import db
from models import Appointment, Invitation, User
from forms import AppointmentForm, InvitationForm
from xhtml2pdf import pisa
from datetime import datetime, timedelta, time
from collections import OrderedDict
from sqlalchemy import or_
import pandas as pd

appointments = Blueprint("appointments", __name__)

# =====================================================
# DASHBOARD
# =====================================================
@appointments.route("/dashboard")
@login_required
def dashboard():

    status_filter = request.args.get("status", "All")

    if current_user.role == "admin":
        query = Appointment.query
    else:
        query = Appointment.query.filter_by(email=current_user.email)

    if status_filter != "All":
        query = query.filter(Appointment.status == status_filter)

    data = query.order_by(Appointment.appointment_date.desc()).all()

    return render_template(
        "dashboard.html",
        appointments=data,
        status_filter=status_filter
    )

# =====================================================
# ANALYTICS API
# =====================================================
@appointments.route("/appointments/api/analytics")
@login_required
def analytics_api():

    filter_type = request.args.get("filter", "today")
    status_filter = request.args.get("status", "All")
    search = request.args.get("search", "")

    today = dt.today().date()

    if current_user.role == "admin":
        query = Appointment.query
        users_query = User.query
    else:
        query = Appointment.query.filter_by(email=current_user.email)
        users_query = None

    # ---------------- DATE FILTER ----------------
    if filter_type == "today":
        query = query.filter(Appointment.appointment_date == today)

    elif filter_type == "week":
        query = query.filter(Appointment.appointment_date >= today - timedelta(days=7))

    elif filter_type == "month":
        query = query.filter(
            extract("year", Appointment.appointment_date) == today.year,
            extract("month", Appointment.appointment_date) == today.month
        )

    elif filter_type == "last_month":
        month = 12 if today.month == 1 else today.month - 1
        year = today.year - 1 if today.month == 1 else today.year

        query = query.filter(
            extract("year", Appointment.appointment_date) == year,
            extract("month", Appointment.appointment_date) == month
        )

    elif filter_type == "year":
        query = query.filter(extract("year", Appointment.appointment_date) == today.year)

    # ---------------- STATUS ----------------
    if status_filter != "All":
        query = query.filter(Appointment.status.ilike(status_filter))

    # ---------------- SEARCH ----------------
    if search:
        query = query.filter(
            or_(
                Appointment.guest_name.ilike(f"%{search}%"),
                Appointment.email.ilike(f"%{search}%"),
                Appointment.service.ilike(f"%{search}%")
            )
        )

    appointments_data = query.all()

    approved = sum(1 for a in appointments_data if (a.status or "").lower() == "approved")
    pending = sum(1 for a in appointments_data if (a.status or "").lower() == "pending")
    rejected = sum(1 for a in appointments_data if (a.status or "").lower() == "rejected")

    # ---------------- MONTHLY ----------------
    monthly_counts = OrderedDict()

    for a in appointments_data:
        if a.appointment_date:
            key = a.appointment_date.strftime("%Y-%m")
            monthly_counts[key] = monthly_counts.get(key, 0) + 1

    monthly = [
        {
            "label": dt(year=int(k[:4]), month=int(k[5:7]), day=1).strftime("%b %Y"),
            "count": v
        }
        for k, v in sorted(monthly_counts.items())
    ]

    # ---------------- USERS ----------------
    users = {}
    if users_query:
        users = {
            "Admin": users_query.filter_by(role="admin").count(),
            "Member": users_query.filter_by(role="member").count(),
            "Clerk": users_query.filter_by(role="clerk").count()
        }

    # ---------------- INSTITUTIONS ----------------
    institutions = {}
    for a in appointments_data:
        inst = a.institution or "Unknown"
        institutions[inst] = institutions.get(inst, 0) + 1

    institutions = dict(sorted(institutions.items(), key=lambda x: x[1], reverse=True))

    return jsonify({
        "total": len(appointments_data),
        "approved": approved,
        "pending": pending,
        "rejected": rejected,
        "monthly": monthly,
        "users": users,
        "institutions": institutions
    })


# =====================================================
# BOOK APPOINTMENT
# =====================================================
@appointments.route("/book", methods=["GET", "POST"])
@login_required
def book_appointment():

    if request.method == "GET":
        form = AppointmentForm()
        form.email.data = current_user.email

        if hasattr(current_user, "full_name"):
            form.guest_name.data = current_user.full_name

        return render_template("book_appointment.html", form=form)

    try:
        data = request.form.to_dict()

        institution = data.get("institution", "").strip()
        if institution == "other":
            institution = data.get("other_institution", "").strip() or "Unknown"

        service = data.get("service", "").strip()
        if service == "other":
            service = data.get("other_service", "").strip() or "Not specified"

        priority = data.get("priority", "Medium").strip()
        if priority not in ["High", "Medium", "Low"]:
            priority = "Medium"

        raw_time = data.get("appointment_time")
        if not raw_time:
            return jsonify(success=False, message="Appointment time required"), 400

        try:
            h, m = map(int, raw_time.split(":"))
            appointment_time = dt.strptime(f"{h}:{m}", "%H:%M").time()
        except:
            return jsonify(success=False, message="Invalid time format"), 400

        try:
            appointment_date = dt.strptime(data.get("appointment_date"), "%Y-%m-%d").date()
        except:
            return jsonify(success=False, message="Invalid date format"), 400

        form = AppointmentForm(request.form)
        if not form.validate():
            return jsonify(success=False, errors=form.errors), 400

        existing = Appointment.query.filter(
            Appointment.appointment_date == appointment_date,
            Appointment.appointment_time == appointment_time,
            Appointment.status != "Rejected"
        ).first()

        if existing:
            return jsonify(success=False, message="Slot already booked"), 409

        appointment = Appointment(
            guest_name=form.guest_name.data,
            email=form.email.data,
            phone=form.phone.data,
            institution=institution,
            service=service,
            purpose=form.purpose.data,
            notes=form.notes.data if hasattr(form, "notes") else None,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status="Pending",
            priority=priority,
            created_at=dt.utcnow()
        )

        db.session.add(appointment)
        db.session.commit()

        return jsonify(success=True, appointment_id=appointment.id)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500

@appointments.route("/appointments/check-email")
@login_required
def check_email():
    email = request.args.get("email")

    exists = User.query.filter_by(email=email).first() is not None

    return jsonify({
        "exists": exists
    })

# =====================================================
# LIST APPOINTMENTS
# =====================================================
@appointments.route("/appointments")
@login_required
def appointment_list():

    status = request.args.get("status")
    search = request.args.get("search")  # 🔥 future AJAX support

    if current_user.role == "admin":
        query = Appointment.query
    else:
        query = Appointment.query.filter_by(email=current_user.email)

    # status filter
    if status:
        query = query.filter_by(status=status)

    # 🔥 future search support (backend-ready)
    if search:
        query = query.filter(
            Appointment.guest_name.ilike(f"%{search}%")
            | Appointment.email.ilike(f"%{search}%")
            | Appointment.service.ilike(f"%{search}%")
        )

    data = query.order_by(Appointment.created_at.desc()).all()

    return render_template(
        "appointments.html",
        appointments=data,
        status_filter=status,
        search=search
    )
# =====================================================
# SEARCH API
# =====================================================
@appointments.route("/appointments/api/search")
@login_required
def search_appointments():

    q = request.args.get("q", "")

    query = Appointment.query

    if current_user.role != "admin":
        query = query.filter_by(email=current_user.email)

    if q:
        query = query.filter(
            Appointment.guest_name.ilike(f"%{q}%")
            | Appointment.email.ilike(f"%{q}%")
            | Appointment.service.ilike(f"%{q}%")
        )

    results = query.limit(50).all()

    return jsonify([
        {
            "id": a.id,
            "name": a.guest_name,
            "email": a.email,
            "service": a.service,
            "date": a.appointment_date.strftime("%Y-%m-%d"),
            "status": a.status
        }
        for a in results
    ])
# =====================================================
# VIEW APPOINTMENT
# =====================================================
@appointments.route("/appointment/<int:id>")
@login_required
def view_appointment(id):
    appointment = Appointment.query.get_or_404(id)

    if current_user.role != "admin" and appointment.email != current_user.email:
        flash("Access denied.", "danger")
        return redirect(url_for("appointments.dashboard"))

    return render_template("view_appointment.html", appointment=appointment)


@appointments.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # ==========================================
    # PERMISSION CHECK
    # ==========================================
    if current_user.role != "admin" and appointment.email != current_user.email:
        if is_ajax:
            return jsonify(success=False, message="Access denied"), 403
        flash("Access denied", "danger")
        return redirect(url_for("appointments.dashboard"))

    # ==========================================
    # GET REQUEST
    # ==========================================
    if request.method == "GET":
        return render_template("edit_appointment.html", appointment=appointment)

    # ==========================================
    # POST REQUEST
    # ==========================================
    try:
        form = request.form

        # Safe helper
        def safe(field, current=""):
            value = form.get(field)
            if value is None:
                return current
            value = value.strip()
            return value if value else current

        # Basic fields
        appointment.guest_name = safe("guest_name", appointment.guest_name)
        appointment.email = safe("email", appointment.email)
        appointment.phone = safe("phone", appointment.phone)
        appointment.purpose = safe("purpose", appointment.purpose)
        appointment.notes = safe("notes", appointment.notes)

        # Email validation
        if "@" not in appointment.email:
            return jsonify(success=False, message="Invalid email address"), 400

        # Date
        date_str = safe("appointment_date")
        if not date_str:
            return jsonify(success=False, message="Appointment date is required"), 400
        try:
            appointment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify(success=False, message="Invalid date format"), 400

        # Time
        time_str = safe("appointment_time")
        if not time_str:
            return jsonify(success=False, message="Appointment time is required"), 400
        try:
            try:
                appointment_time = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                appointment_time = datetime.strptime(time_str, "%H:%M:%S").time()
        except ValueError:
            return jsonify(success=False, message="Invalid time format"), 400

        # Duplicate slot check
        existing = Appointment.query.filter(
            Appointment.appointment_date == appointment_date,
            Appointment.appointment_time == appointment_time,
            Appointment.id != appointment.id,
            Appointment.status != "Rejected"
        ).first()
        if existing:
            return jsonify(success=False, message="This slot is already booked"), 409

        appointment.appointment_date = appointment_date
        appointment.appointment_time = appointment_time

        # Institution
        institution = form.get("institution", "").strip()
        if institution == "Other":
            institution = form.get("other_institution", "").strip()
        if not institution:
            return jsonify(success=False, message="Institution is required"), 400
        appointment.institution = institution

        # Service
        service = form.get("service", "").strip()
        if service == "Other":
            service = form.get("other_service", "").strip()
        if not service:
            return jsonify(success=False, message="Service is required"), 400
        appointment.service = service

        # Priority
        priority = form.get("priority", "").strip()
        if priority not in ["High", "Medium", "Low"]:
            priority = "Medium"
        appointment.priority = priority

        # Status (admin only)
        if current_user.role == "admin":
            status = form.get("status", "").strip()
            if status in ["Pending", "Approved", "Rejected"]:
                appointment.status = status

        # Final validation
        if not appointment.guest_name:
            return jsonify(success=False, message="Guest name is required"), 400
        if not appointment.email:
            return jsonify(success=False, message="Email is required"), 400

        # Save
        db.session.commit()
        return jsonify(
            success=True,
            message="Appointment updated successfully",
            appointment_id=appointment.id
        )

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=f"Server error: {str(e)}"), 500
# ==========================================
# APPROVE APPOINTMENT
# ==========================================
@appointments.route("/approve/<int:id>", methods=["POST"])
@login_required
def approve_appointment(id):

    if current_user.role != "admin":
        return jsonify(
            success=False,
            message="Access denied"
        ), 403

    appointment = Appointment.query.get_or_404(id)

    try:

        if appointment.status == "Approved":
            return jsonify(
                success=False,
                message="Appointment is already approved"
            ), 400

        appointment.status = "Approved"

        db.session.commit()

        return jsonify(
            success=True,
            message="Appointment approved successfully",
            appointment_id=appointment.id,
            status=appointment.status
        )

    except Exception as e:

        db.session.rollback()

        return jsonify(
            success=False,
            message="Failed to approve appointment",
            error=str(e)
        ), 500

# ==========================================
# REJECT APPOINTMENT
# ==========================================
@appointments.route("/reject/<int:id>", methods=["POST"])
@login_required
def reject_appointment(id):

    if current_user.role != "admin":
        return jsonify(
            success=False,
            message="Access denied"
        ), 403

    appointment = Appointment.query.get_or_404(id)

    try:

        if appointment.status == "Rejected":
            return jsonify(
                success=False,
                message="Appointment is already rejected"
            ), 400

        appointment.status = "Rejected"

        db.session.commit()

        return jsonify(
            success=True,
            message="Appointment rejected successfully",
            appointment_id=appointment.id,
            status=appointment.status
        )

    except Exception as e:

        db.session.rollback()

        return jsonify(
            success=False,
            message="Failed to reject appointment",
            error=str(e)
        ), 500


# ==========================================
# DELETE APPOINTMENT
# ==========================================
@appointments.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_appointment(id):

    appointment = Appointment.query.get_or_404(id)

    # ==========================================
    # PERMISSION
    # ==========================================
    if (
        current_user.role != "admin"
        and appointment.email != current_user.email
    ):
        return jsonify(
            success=False,
            message="Access denied"
        ), 403

    try:

        deleted_id = appointment.id
        deleted_name = appointment.guest_name

        db.session.delete(appointment)
        db.session.commit()

        return jsonify(
            success=True,
            message="Appointment deleted successfully",
            appointment_id=deleted_id,
            guest_name=deleted_name
        )

    except Exception as e:

        db.session.rollback()

        return jsonify(
            success=False,
            message="Failed to delete appointment",
            error=str(e)
        ), 500

# =====================================================
# CALENDAR VIEW
# =====================================================
@appointments.route("/calendar")
@login_required
def calendar():
    if current_user.role == "admin":
        appointments_data = Appointment.query.order_by(Appointment.appointment_date.asc()).all()
        invitations_data = Invitation.query.order_by(Invitation.date.asc()).all()
    else:
        appointments_data = Appointment.query.filter_by(email=current_user.email).order_by(
            Appointment.appointment_date.asc()
        ).all()
        invitations_data = Invitation.query.filter_by(recipient=current_user.email).order_by(
            Invitation.date.asc()
        ).all()

    return render_template(
        "calendar.html",
        appointments=appointments_data,
        invitations=invitations_data
    )

# =====================================================
# INVITATIONS
# =====================================================
@appointments.route("/invitations")
@login_required
def invitations():
    if current_user.role == "admin":
        data = Invitation.query.order_by(Invitation.date.desc()).all()
    else:
        data = Invitation.query.filter_by(recipient=current_user.email).order_by(
            Invitation.date.desc()
        ).all()

    return render_template("invitations.html", invitations=data)


@appointments.route("/invitations/new", methods=["GET", "POST"])
@login_required
def new_invitation():

    edit_id = request.args.get("edit")
    invite = None

    # =========================
    # LOAD EXISTING (EDIT MODE)
    # =========================
    if edit_id:
        invite = Invitation.query.get_or_404(edit_id)

        if current_user.role != "admin" and invite.recipient != current_user.email:
            flash("Access denied.", "danger")
            return redirect(url_for("appointments.invitations"))

        form = InvitationForm(obj=invite)
    else:
        form = InvitationForm()

    # =========================
    # HANDLE POST
    # =========================
    if form.validate_on_submit():

        try:
            inv_date = request.form.get("invitation_date")
            parsed_date = None

            if inv_date:
                try:
                    parsed_date = datetime.strptime(inv_date, "%Y-%m-%d")
                except Exception:
                    parsed_date = datetime.utcnow()

            # =========================
            # UPDATE EXISTING
            # =========================
            if invite:
                invite.sender = form.sender.data
                invite.recipient = form.recipient.data
                invite.subject = form.subject.data
                invite.message = form.message.data

                if parsed_date:
                    invite.date = parsed_date

                db.session.commit()
                flash("Invitation updated successfully.", "success")

            # =========================
            # CREATE NEW
            # =========================
            else:
                new_invite = Invitation(
                    sender=form.sender.data,
                    recipient=form.recipient.data,
                    subject=form.subject.data,
                    message=form.message.data,
                    date=parsed_date or datetime.utcnow(),
                    status="Pending"
                )

                db.session.add(new_invite)
                db.session.commit()
                flash("Invitation created successfully.", "success")

            return redirect(url_for("appointments.invitations"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    # =========================
    # DEFAULT DATE FOR TEMPLATE
    # =========================
    today_date = (
        invite.date.strftime("%Y-%m-%d")
        if invite and invite.date
        else datetime.utcnow().strftime("%Y-%m-%d")
    )

    return render_template(
        "new_invitation.html",
        form=form,
        invite=invite,
        today_date=today_date
    )

@appointments.route("/invitations/view/<int:id>")
@login_required
def view_invitation(id):
    invite = Invitation.query.get_or_404(id)
    if current_user.role != "admin" and invite.recipient != current_user.email:
        flash("Access denied.", "danger")
        return redirect(url_for("appointments.invitations"))
    return render_template("view_invitation.html", invite=invite)

@appointments.route("/invitations/accept/<int:id>", methods=["POST"])
@login_required
def accept_invitation(id):
    invite = Invitation.query.get_or_404(id)
    invite.status = "Accepted"
    db.session.commit()
    flash("Invitation accepted.", "success")
    return redirect(url_for("appointments.invitations"))

@appointments.route("/invitations/decline/<int:id>", methods=["POST"])
@login_required
def decline_invitation(id):
    invite = Invitation.query.get_or_404(id)
    invite.status = "Declined"
    db.session.commit()
    flash("Invitation declined.", "warning")
    return redirect(url_for("appointments.invitations"))

@appointments.route("/invitations/delete/<int:id>", methods=["POST"])
@login_required
def delete_invitation(id):
    invite = Invitation.query.get_or_404(id)
    db.session.delete(invite)
    db.session.commit()
    flash("Invitation deleted successfully.", "info")
    return redirect(url_for("appointments.invitations"))

@appointments.route("/invitations/export", methods=["GET"])
def export_invitations():
    invitations = Invitation.query.all()
    data = [
        {
            "Sender": inv.sender,
            "Recipient": inv.recipient,
            "Subject": inv.subject,
            "Date": inv.date.strftime("%Y-%m-%d"),
            "Status": inv.status,
        }
        for inv in invitations
    ]
    df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Invitations")

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="invitations.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@appointments.route("/appointments/api/reschedule", methods=["POST"])
@login_required
def reschedule_event():
    data = request.get_json()

    raw_id = data.get("id")
    new_date = data.get("new_date")

    if not raw_id or not new_date:
        return jsonify(success=False, message="Missing data"), 400

    try:
        target_date = datetime.strptime(new_date[:10], "%Y-%m-%d").date()

        # =========================
        # INVITATION
        # =========================
        if str(raw_id).startswith("invitation-"):

            invite_id = raw_id.replace("invitation-", "")
            invite = Invitation.query.get(invite_id)

            if not invite:
                return jsonify(success=False, message="Not found"), 404

            if current_user.role != "admin" and invite.recipient != current_user.email:
                return jsonify(success=False, message="Unauthorized"), 403

            invite.date = target_date
            db.session.commit()

            return jsonify(success=True, message="Invitation rescheduled")

        # =========================
        # APPOINTMENT
        # =========================
        appointment_id = raw_id.replace("appointment-", "")
        appointment = Appointment.query.get(appointment_id)

        if not appointment:
            return jsonify(success=False, message="Not found"), 404

        if current_user.role != "admin" and appointment.email != current_user.email:
            return jsonify(success=False, message="Unauthorized"), 403

        # 🔴 CONFLICT CHECK
        conflict = Appointment.query.filter(
            Appointment.id != appointment.id,
            Appointment.appointment_date == target_date,
            Appointment.status != "Rejected"
        ).first()

        if conflict:
            return jsonify(
                success=False,
                message="⚠ Slot already booked on that date"
            ), 409

        appointment.appointment_date = target_date
        db.session.commit()

        return jsonify(success=True, message="Appointment rescheduled")

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
@appointments.route("/calendar/events")
@login_required
def calendar_events():

    events = []

    # =========================
    # DATA LOAD (ROLE BASED)
    # =========================
    if current_user.role == "admin":
        appointments_data = Appointment.query.all()
        invitations_data = Invitation.query.all()
    else:
        appointments_data = Appointment.query.filter_by(
            email=current_user.email
        ).all()

        invitations_data = Invitation.query.filter_by(
            recipient=current_user.email
        ).all()

    today = datetime.today().date()

    # =========================
    # APPOINTMENTS EVENTS
    # =========================
    for a in appointments_data:

        if not a.appointment_date:
            continue

        events.append({
            "id": f"appointment-{a.id}",
            "title": a.guest_name,
            "start": a.appointment_date.strftime("%Y-%m-%d"),
            "className": "appointment-event"
        })

    # =========================
    # INVITATIONS EVENTS
    # =========================
    for i in invitations_data:

        event_date = (
            i.date.date() if hasattr(i.date, "date") else i.date
        )

        overdue = event_date < today

        events.append({
            "id": f"invitation-{i.id}",
            "title": f"⚠ {i.subject}",
            "start": event_date.strftime("%Y-%m-%d"),
            "className": (
                "invitation-overdue" if overdue else "invitation-event"
            ),
            "backgroundColor": "#475569" if overdue else "#dc2626",
            "borderColor": "#475569" if overdue else "#dc2626",
            "textColor": "#ffffff"
        })

    # =========================
    # FINAL RETURN (ONLY ONE)
    # =========================
    return jsonify(events)
@appointments.route("/appointments/api/check-slot")
@login_required
def check_slot():

    date_str = request.args.get("date")

    if not date_str:
        return jsonify({"available": False}), 400

    try:
        target_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()

        conflict = Appointment.query.filter(
            Appointment.appointment_date == target_date,
            Appointment.status != "Rejected"
        ).first()

        return jsonify({
            "available": conflict is None
        })

    except Exception as e:
        return jsonify({
            "available": False,
            "error": str(e)
        }), 500
    # =========================
    # INVITATION EVENTS (WITH OVERDUE STYLE)
    # =========================
    for i in invitations_data:

        event_date = (
            i.date.date()
            if hasattr(i.date, "date")
            else i.date
        )

        overdue = event_date < today if event_date else False

        events.append({
            "id": f"invitation-{i.id}",
            "title": f"⚠ {i.subject}",
            "start": event_date.strftime("%Y-%m-%d") if event_date else "",
            "backgroundColor": "#475569" if overdue else "#dc2626",
            "borderColor": "#475569" if overdue else "#dc2626",
            "textColor": "#ffffff",
            "className": "invitation-overdue" if overdue else "invitation-event"
        })

    return jsonify(events)
# =====================================================
# LIVE NOTIFICATIONS
# =====================================================
@appointments.route("/appointments/api/notifications")
@login_required
def notifications_api():

    if current_user.role == "admin":
        appointments_data = Appointment.query.filter_by(status="Pending") \
            .order_by(Appointment.appointment_date.desc()).limit(10).all()
    else:
        appointments_data = Appointment.query.filter_by(
            email=current_user.email, status="Pending"
        ).order_by(Appointment.appointment_date.desc()).limit(10).all()

    items = []
    for a in appointments_data:
        items.append({
            "id": a.id,
            "name": a.guest_name,
            "service": a.service,
            "date": a.appointment_date.strftime("%Y-%m-%d") if a.appointment_date else "",
            "url": url_for("appointments.view_appointment", id=a.id)
        })

    return jsonify({
        "count": len(items),
        "items": items
    })
# =====================================================
# PRINT INVITATION (PDF)
# =====================================================
@appointments.route("/invitations/print/<int:id>")
@login_required
def print_invitation(id):
    invite = Invitation.query.get_or_404(id)
    html = render_template("print_invitation.html", invite=invite)

    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(html, dest=pdf_buffer)

    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=invitation_{id}.pdf"
    return response


@appointments.route("/appointments/print/<int:id>")
@login_required
def print_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    html = render_template("appointment_pdf.html", appointment=appointment)

    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(html, dest=pdf_buffer)

    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=appointment_{id}.pdf"
    return response


# =====================================================
# EXPORT REGISTRY
# =====================================================
@appointments.route("/export_registry")
@login_required
def export_registry():
    if current_user.role == "admin":
        data = Appointment.query.all()
    else:
        data = Appointment.query.filter_by(email=current_user.email).all()

    # Return JSON so the modal can load dynamically
    return jsonify([
        {
            "id": a.id,
            "guest_name": a.guest_name,
            "service": a.service,
            "appointment_date": a.appointment_date.strftime("%Y-%m-%d"),
            "status": a.status
        }
        for a in data
    ])
@appointments.route("/appointments/api/drilldown")
@login_required
def drilldown():
    status = request.args.get("status")

    query = Appointment.query
    if status:
        query = query.filter_by(status=status)

    data = query.all()

    return jsonify({
        "count": len(data),
        "items": [
            {
                "name": a.guest_name,
                "service": a.service,
                "date": a.appointment_date.strftime("%Y-%m-%d"),
                "status": a.status
            }
            for a in data
        ]
    })
@appointments.route("/speaker/report")
@login_required
def speaker_report():

    from datetime import datetime, timedelta
    from sqlalchemy import extract
    from collections import Counter

    filter_type = request.args.get("filter", "today")
    filter_type = (filter_type or "today").lower()

    today = datetime.today().date()

    # =========================
    # BASE QUERY (ROLE CONTROL)
    # =========================
    if current_user.role == "admin":
        appt_query = Appointment.query
        inv_query = Invitation.query
    else:
        appt_query = Appointment.query.filter_by(email=current_user.email)
        inv_query = Invitation.query.filter_by(recipient=current_user.email)

    # =========================
    # DATE FILTER LOGIC
    # =========================
    if filter_type == "today":

        appt_query = appt_query.filter(
            Appointment.appointment_date == today
        )
        inv_query = inv_query.filter(
            Invitation.date == today
        )

    elif filter_type == "week":

        start_date = today - timedelta(days=7)

        appt_query = appt_query.filter(
            Appointment.appointment_date >= start_date
        )
        inv_query = inv_query.filter(
            Invitation.date >= start_date
        )

    elif filter_type == "month":

        appt_query = appt_query.filter(
            extract("year", Appointment.appointment_date) == today.year,
            extract("month", Appointment.appointment_date) == today.month
        )

        inv_query = inv_query.filter(
            extract("year", Invitation.date) == today.year,
            extract("month", Invitation.date) == today.month
        )

    else:
        filter_type = "today"
        appt_query = appt_query.filter(Appointment.appointment_date == today)
        inv_query = inv_query.filter(Invitation.date == today)

    # =========================
    # FETCH DATA
    # =========================
    appointments = appt_query.order_by(Appointment.appointment_date.desc()).all()
    invitations = inv_query.order_by(Invitation.date.desc()).all()

    # =========================
    # COUNTS
    # =========================
    total_appointments = len(appointments)
    total_invitations = len(invitations)

    # =========================
    # APPOINTMENT ANALYTICS
    # =========================
    status_counter = Counter(a.status for a in appointments)
    date_counter = Counter(a.appointment_date for a in appointments)

    most_active_day = None
    if date_counter:
        most_active_day = date_counter.most_common(1)[0]

    # invitation status analysis
    inv_status_counter = Counter(i.status for i in invitations)

    # =========================
    # EXECUTIVE SUMMARY (AUTO GENERATED)
    # =========================
    summary_parts = []

    summary_parts.append(
        f"This report covers {total_appointments} appointments and "
        f"{total_invitations} invitations for the selected period."
    )

    if status_counter:
        summary_parts.append(
            f"Appointment status breakdown: "
            f"{dict(status_counter)}."
        )

    if inv_status_counter:
        summary_parts.append(
            f"Invitation status breakdown: "
            f"{dict(inv_status_counter)}."
        )

    if most_active_day:
        summary_parts.append(
            f"The busiest appointment day was {most_active_day[0]} "
            f"with {most_active_day[1]} appointment(s)."
        )

    executive_summary = " ".join(summary_parts)

    # =========================
    # RENDER TEMPLATE
    # =========================
    return render_template(
        "speaker_report.html",
        appointments=appointments,
        invitations=invitations,
        total_appointments=total_appointments,
        total_invitations=total_invitations,
        filter_type=filter_type,
        report_date=today,
        generated_by=getattr(current_user, "full_name", current_user.email),
        executive_summary=executive_summary
    )
    
    
@appointments.route("/speaker/report/pdf")
@login_required
def export_speaker_pdf():

    filter_type = request.args.get("filter", "today")

    today = datetime.today().date()

    # same logic reuse
    if current_user.role == "admin":
        appt_query = Appointment.query
        inv_query = Invitation.query
    else:
        appt_query = Appointment.query.filter_by(email=current_user.email)
        inv_query = Invitation.query.filter_by(recipient=current_user.email)

    if filter_type == "today":
        appt_query = appt_query.filter(Appointment.appointment_date == today)
        inv_query = inv_query.filter(Invitation.date == today)

    elif filter_type == "week":
        start = today - timedelta(days=7)
        appt_query = appt_query.filter(Appointment.appointment_date >= start)
        inv_query = inv_query.filter(Invitation.date >= start)

    elif filter_type == "month":
        appt_query = appt_query.filter(
            db.extract("year", Appointment.appointment_date) == today.year,
            db.extract("month", Appointment.appointment_date) == today.month
        )
        inv_query = inv_query.filter(
            db.extract("year", Invitation.date) == today.year,
            db.extract("month", Invitation.date) == today.month
        )

    appointments = appt_query.all()
    invitations = inv_query.all()

    html = render_template(
        "speaker_report.html",
        appointments=appointments,
        invitations=invitations,
        total_appointments=len(appointments),
        total_invitations=len(invitations),
        filter_type=filter_type,
        report_date=today,
        generated_by=current_user.full_name if hasattr(current_user, "full_name") else current_user.email
    )

    pdf = io.BytesIO()
    pisa.CreatePDF(html, dest=pdf)

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=speaker_report.pdf"
    return response
