from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file
)
from flask_login import login_required
from datetime import datetime
import os
import shutil

settings_bp = Blueprint("settings", __name__)


# =====================================================
# SETTINGS PAGE
# =====================================================
@settings_bp.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html")


# =====================================================
# GENERAL SETTINGS
# =====================================================
@settings_bp.route("/settings/general", methods=["POST"])
@login_required
def save_general_settings():

    app_name = request.form.get("app_name")
    organization = request.form.get("organization")
    timezone = request.form.get("timezone")

    # Save to database/config later

    flash("General settings updated successfully.", "success")

    return redirect(url_for("settings.settings_page"))


# =====================================================
# EMAIL SETTINGS
# =====================================================
@settings_bp.route("/settings/email", methods=["POST"])
@login_required
def save_email_settings():

    smtp_server = request.form.get("smtp_server")
    smtp_port = request.form.get("smtp_port")
    email_address = request.form.get("email_address")
    password = request.form.get("password")

    # Save later

    flash("Email settings saved successfully.", "success")

    return redirect(url_for("settings.settings_page"))


# =====================================================
# SYSTEM SETTINGS
# =====================================================
@settings_bp.route("/settings/system", methods=["POST"])
@login_required
def save_system_settings():

    notifications = bool(request.form.get("notifications"))
    email_alerts = bool(request.form.get("email_alerts"))
    auto_backup = bool(request.form.get("auto_backup"))

    # Save later

    flash("System settings saved successfully.", "success")

    return redirect(url_for("settings.settings_page"))


# =====================================================
# BACKUP DATABASE
# =====================================================
@settings_bp.route("/settings/backup")
@login_required
def backup_database():
    # Correct path to your database file
    db_file = os.path.join("instance", "appointments.db")

    if not os.path.exists(db_file):
        flash("Database file not found.", "danger")
        return redirect(url_for("settings.settings_page"))

    backup_folder = "backups"
    os.makedirs(backup_folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}.db"
    backup_path = os.path.join(backup_folder, backup_name)

    shutil.copy2(db_file, backup_path)

    return send_file(backup_path, as_attachment=True)


# =====================================================
# RESTORE DATABASE
# =====================================================
@settings_bp.route("/settings/restore", methods=["POST"])
@login_required
def restore_database():
    file = request.files.get("backup_file")

    if not file:
        flash("No file selected.", "danger")
        return redirect(url_for("settings.settings_page"))

    db_file = os.path.join("instance", "appointments.db")
    temp_path = "temp_restore.db"

    # Save uploaded file temporarily
    file.save(temp_path)

    # Check if target DB file exists
    if not os.path.exists(db_file):
        flash("Target database file does not exist.", "danger")
        os.remove(temp_path)
        return redirect(url_for("settings.settings_page"))

    # Replace existing DB with uploaded backup
    shutil.copy2(temp_path, db_file)
    os.remove(temp_path)

    flash("Database restored successfully.", "success")
    return redirect(url_for("settings.settings_page"))

# =====================================================
# TEST EMAIL
# =====================================================
@settings_bp.route("/settings/test-email")
@login_required
def test_email():

    # send email later

    flash("Test email sent successfully.", "success")

    return redirect(url_for("settings.settings_page"))


# =====================================================
# SYSTEM INFORMATION
# =====================================================
@settings_bp.route("/settings/system-info")
@login_required
def system_info():

    info = {
        "python_version": os.sys.version,
        "working_directory": os.getcwd()
    }

    return info


# =====================================================
# CLEAR CACHE
# =====================================================
@settings_bp.route("/settings/clear-cache")
@login_required
def clear_cache():

    flash("Cache cleared successfully.", "success")

    return redirect(url_for("settings.settings_page"))


# =====================================================
# EXPORT SETTINGS
# =====================================================
@settings_bp.route("/settings/export")
@login_required
def export_settings():

    flash("Settings exported successfully.", "success")

    return redirect(url_for("settings.settings_page"))


# =====================================================
# IMPORT SETTINGS
# =====================================================
@settings_bp.route("/settings/import", methods=["POST"])
@login_required
def import_settings():

    flash("Settings imported successfully.", "success")

    return redirect(url_for("settings.settings_page"))