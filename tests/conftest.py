import pytest

from app import create_app
from app.db import init_db
from app.services.auth_service import register_user


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-not-for-deployment",
        "DATABASE": str(tmp_path / "test.sqlite3"),
        "SESSION_COOKIE_SECURE": False,
        "GOOGLE_CLIENT_ID": None,
        "GOOGLE_CLIENT_SECRET": None,
        "GOOGLE_REDIRECT_URI": None,
    })
    with application.app_context():
        init_db()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user_id(app):
    with app.app_context():
        return register_user("demo", "correct-password")
