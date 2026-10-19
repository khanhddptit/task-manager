import os
from datetime import timedelta


class Config:
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = True
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024


def environment_config():
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SESSION_COOKIE_SECURE": os.environ.get(
            "SESSION_COOKIE_SECURE", "false"
        ).lower() in {"true", "1", "yes"},
        "GOOGLE_CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "GOOGLE_REDIRECT_URI": os.environ.get("GOOGLE_REDIRECT_URI"),
    }
