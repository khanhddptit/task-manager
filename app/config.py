import os
from datetime import timedelta


class Config:
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = True
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024


def environment_config():
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SESSION_COOKIE_SECURE": os.environ.get(
            "SESSION_COOKIE_SECURE", "false"
        ).lower() in {"true", "1", "yes"},
    }
