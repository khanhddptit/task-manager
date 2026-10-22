from datetime import date, timedelta

from app.core.db import get_db
from app.services.auth_service import register_user
from app.services.workspace_service import create_workspace


def make_owner_client(app):
    with app.app_context():
        user_id = register_user("sprint-api-owner", "correct-password")
        workspace = create_workspace("Sprint API workspace", "", user_id)
        project_id = get_db().execute(
            "INSERT INTO project (workspace_id, name, created_by) VALUES (?, ?, ?)",
            (workspace["id"], "Sprint API project", user_id),
        ).lastrowid
        get_db().commit()
    client = app.test_client()
    csrf = client.get("/auth/csrf").json["csrf_token"]
    login = client.post(
        "/auth/login",
        json={"username": "sprint-api-owner", "password": "correct-password"},
        headers={"X-CSRFToken": csrf},
    )
    assert login.status_code == 200
    return client, {"X-CSRFToken": login.json["csrf_token"]}, workspace["id"], project_id


def test_sprint_api_create_lifecycle_and_progress(app):
    client, headers, workspace_id, project_id = make_owner_client(app)
    base = f"/workspaces/{workspace_id}/projects/{project_id}/sprints"
    today = date.today()
    payload = {
        "name": "Sprint API 1",
        "goal": "Ship Sprint support",
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=6)).isoformat(),
    }

    created = client.post(base, json=payload, headers=headers)
    assert created.status_code == 201
    sprint_id = created.json["sprint"]["id"]
    assert created.json["sprint"]["status"] == "planned"
    assert client.get(base).json["sprints"][0]["id"] == sprint_id

    started = client.post(f"{base}/{sprint_id}/start", json={}, headers=headers)
    assert started.status_code == 200
    assert started.json["sprint"]["status"] == "active"
    progress = client.get(f"{base}/{sprint_id}/progress")
    assert progress.status_code == 200
    assert progress.json["summary"]["total_tasks"] == 0
    assert len(progress.json["burndown"]) == 7

    completed = client.post(f"{base}/{sprint_id}/complete", json={}, headers=headers)
    assert completed.status_code == 200
    assert completed.json["sprint"]["status"] == "completed"


def test_sprint_pages_render(app):
    client = app.test_client()
    assert client.get("/sprints/").status_code == 200
    assert client.get("/sprints/progress").status_code == 200


def test_sprint_api_validates_dates_and_project_scope(app):
    client, headers, workspace_id, project_id = make_owner_client(app)
    base = f"/workspaces/{workspace_id}/projects/{project_id}/sprints"
    response = client.post(base, json={
        "name": "Invalid Sprint",
        "start_date": "2026-04-02",
        "end_date": "2026-04-01",
    }, headers=headers)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    assert client.get(f"/workspaces/{workspace_id}/projects/{project_id + 999}/sprints").status_code == 404
