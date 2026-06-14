from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash
from livereload import Server
from flask_migrate import Migrate

from config import Config
from database import db
from models import User

# BLUEPRINTS
from routes.auth import auth
from routes.appointments import appointments
from routes.admin import admin
from routes.analytics import analytics
from routes.user_management import user_mgmt
from routes.settings import settings_bp

# ==================================================
# APP CONFIGURATION
# ==================================================

app = Flask(__name__)
app.config.from_object(Config)

# Required for CSRF protection
app.config["SECRET_KEY"] = getattr(Config, "SECRET_KEY", "super-secret-key")

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# ==================================================
# EXTENSIONS
# ==================================================

db.init_app(app)
migrate = Migrate(app, db)

# Enable CSRF protection
csrf = CSRFProtect(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)

# ==================================================
# LOGIN MANAGER
# ==================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return User.query.get(int(user_id))

# ==================================================
# REGISTER BLUEPRINTS
# ==================================================

app.register_blueprint(auth)
app.register_blueprint(appointments)
app.register_blueprint(admin)
app.register_blueprint(analytics)
app.register_blueprint(user_mgmt)
app.register_blueprint(settings_bp)

# ==================================================
# HOME ROUTE
# ==================================================

@app.route("/")
def home():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("analytics.analytics_dashboard"))
        elif current_user.role == "speaker":
            return redirect(url_for("appointments.calendar"))
        else:
            return redirect(url_for("appointments.dashboard"))
    return redirect(url_for("auth.login"))

# ==================================================
# DATABASE INITIALIZATION
# ==================================================

with app.app_context():
    db.create_all()

    def seed_admin():
        admin_user = User.query.filter_by(
            email="superadmin@gmail.com"
        ).first()

        if not admin_user:
            admin_user = User(
                full_name="Administrator",
                email="superadmin@gmail.com",
                password=generate_password_hash("admin123"),
                role="admin"
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✓ Default admin created")

    seed_admin()

# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    print("\n====================================")
    print(" Parliamentary Appointment System")
    print(" URL: http://127.0.0.1:5000")
    print(" Auto Reload Enabled")
    print("====================================\n")

    server = Server(app.wsgi_app)

    server.watch("app.py")
    server.watch("config.py")
    server.watch("database.py")
    server.watch("models.py")
    server.watch("routes/")
    server.watch("templates/")
    server.watch("static/")

    server.serve(
        host="0.0.0.0",
        port=5000,
        debug=True,
        restart_delay=0.5
    )
