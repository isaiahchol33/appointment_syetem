from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    DateField,
    TextAreaField,
    BooleanField
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    Optional,
    EqualTo
)


# =========================================
# REGISTER FORM (TEMPLATE-DRIVEN VERSION)
# =========================================
class RegisterForm(FlaskForm):

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required"),
            Length(min=3, max=100)
        ]
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email is required"),
            Email(message="Invalid email format"),
            Length(max=120)
        ]
    )

    phone = StringField(
        "Phone Number",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    # Values supplied by template
    department = StringField(
        "Department",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    # Values supplied by template
    role = StringField(
        "Role",
        validators=[
            DataRequired(message="Role is required"),
            Length(max=50)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required"),
            Length(min=8, message="Password must be at least 8 characters")
        ]
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Confirm password is required"),
            EqualTo(
                "password",
                message="Passwords do not match"
            )
        ]
    )

    submit = SubmitField("Create Account")


# =========================================
# LOGIN FORM
# =========================================
class LoginForm(FlaskForm):

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(),
            Email()
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired()
        ]
    )

    remember = BooleanField("Remember Me")

    submit = SubmitField("Login")


# =========================================
# APPOINTMENT FORM
# =========================================
class AppointmentForm(FlaskForm):

    guest_name = StringField(
        "Full Name",
        validators=[
            DataRequired(),
            Length(min=3, max=150)
        ]
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=150)
        ]
    )

    phone = StringField(
        "Phone",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    institution = StringField(
        "Institution",
        validators=[
            DataRequired()
        ]
    )

    other_institution = StringField(
        "Other Institution",
        validators=[
            Optional(),
            Length(max=200)
        ]
    )

    service = StringField(
        "Service Type",
        validators=[
            DataRequired()
        ]
    )

    other_service = StringField(
        "Other Service",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    meeting_with = StringField(
        "Meeting With",
        validators=[
            Optional(),
            Length(max=150)
        ]
    )

    purpose = TextAreaField(
        "Purpose",
        validators=[
            DataRequired(),
            Length(max=500)
        ]
    )

    appointment_date = DateField(
        "Appointment Date",
        format="%Y-%m-%d",
        validators=[
            DataRequired()
        ]
    )

    appointment_time = StringField(
        "Appointment Time",
        validators=[
            DataRequired()
        ]
    )

    notes = TextAreaField(
        "Comments / Remarks",
        validators=[
            Optional(),
            Length(max=1000)
        ]
    )

    # Status controlled by template/backend
    status = StringField(
        "Status",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    submit = SubmitField("Submit Request")


# =========================================
# INVITATION FORM
# =========================================
class InvitationForm(FlaskForm):

    sender = StringField(
        "Sender Name",
        validators=[
            DataRequired(),
            Length(min=3, max=120)
        ]
    )

    recipient = StringField(
        "Recipient Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=120)
        ]
    )

    subject = StringField(
        "Subject",
        validators=[
            DataRequired(),
            Length(min=3, max=200)
        ]
    )

    message = TextAreaField(
        "Message",
        validators=[
            DataRequired(),
            Length(min=10, max=2000)
        ]
    )

    submit = SubmitField("Send Invitation")