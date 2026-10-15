from datetime import timedelta

import pytest
from flask import flash, session

from app import create_app


@pytest.mark.parametrize("path, text", [
    ("/", "Quản lý công việc cùng nhóm"),
    ("/tasks/", "Module sẵn sàng để phát triển"),
])
def test_pages(client, path, text):
    response = client.get(path)
    assert response.status_code == 200
    assert text in response.get_data(as_text=True)
    assert 'lang="vi"' in response.get_data(as_text=True)


def test_static_css(client):
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"


def test_not_found(client):
    response = client.get("/missing-page")
    assert response.status_code == 404
    assert "Không tìm thấy trang" in response.get_data(as_text=True)


def test_server_error(app, client):
    app.config.update(PROPAGATE_EXCEPTIONS=False)

    @app.get("/test-error")
    def test_error():
        raise RuntimeError("internal-only-error")

    response = client.get("/test-error")
    assert response.status_code == 500
    assert "Lỗi hệ thống" in response.get_data(as_text=True)
    assert "internal-only-error" not in response.get_data(as_text=True)


def test_secret_key_required():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"SECRET_KEY": ""})


def test_secure_cookie_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-environment-key")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    app = create_app({"TESTING": True})
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SECRET_KEY"] == "test-only-environment-key"


def test_session_and_flash(app, client):
    @app.get("/test-session")
    def set_session():
        session.clear()
        session["user_id"] = 1
        session.permanent = True
        flash("<script>alert('test')</script>", "success")
        return "ok"

    response = client.get("/test-session")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=8)
    with client.session_transaction() as stored_session:
        assert stored_session["user_id"] == 1

    response = client.get("/")
    html = response.get_data(as_text=True)
    assert "alert-success" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html
    assert "&lt;script&gt;" not in client.get("/").get_data(as_text=True)
