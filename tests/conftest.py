import pytest

from app import create_app
from app.db import init_db


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-not-for-deployment",
        "DATABASE": str(tmp_path / "test.sqlite3"),
        "SESSION_COOKIE_SECURE": False,
    })
    with application.app_context():
        init_db()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()
