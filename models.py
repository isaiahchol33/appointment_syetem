from database import db
from flask_login import UserMixin
from datetime import datetime


# =========================================
# USER MODEL (UPDATED)
# =========================================
class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    # =========================
    # Identity
    # =========================
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # =========================
    # Contact
    # =========================
    phone = db.Column(db.String(50), nullable=True)

    # Department (NEW)
    department = db.Column(db.String(100), nullable=True)

    # =========================
    # Authentication
    # =========================
    password = db.Column(db.String(255), nullable=False)

    # =========================
    # Role System
    # =========================
    role = db.Column(db.String(20), default="user")

    # =========================
    # Account Status
    # =========================
    is_active_account = db.Column(db.Boolean, default=True)

    # =========================
    # Meta
    # =========================
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<User {self.email}>"

    # =====================================
    # Flask-Login compatibility
    # =====================================
    @property
    def is_active(self):
        return self.is_active_account

    @is_active.setter
    def is_active(self, value):
        self.is_active_account = value


# =========================================
# APPOINTMENT MODEL (UNCHANGED)
# =========================================
class Appointment(db.Model):
    __tablename__ = "appointment"

    id = db.Column(db.Integer, primary_key=True)

    guest_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))

    institution = db.Column(db.String(200), nullable=False)
    service = db.Column(db.String(100), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)

    status = db.Column(db.String(20), default="Pending")
    priority = db.Column(db.String(20), nullable=False, default="Medium")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Appointment {self.guest_name} - {self.service}>"


# =========================================
# INVITATION MODEL (UNCHANGED)
# =========================================
class Invitation(db.Model):
    __tablename__ = "invitation"

    id = db.Column(db.Integer, primary_key=True)

    sender = db.Column(db.String(120), nullable=False)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Pending")

    def __repr__(self):
        return f"<Invitation {self.subject} to {self.recipient}>"