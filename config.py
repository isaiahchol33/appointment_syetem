import os

class Config:
    SECRET_KEY = "your-secret-key"

    SQLALCHEMY_DATABASE_URI = "sqlite:///appointments.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0