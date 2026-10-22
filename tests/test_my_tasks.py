from datetime import date, timedelta

from app.core.db import get_db
from app.services.auth_service import register_user
from app.services.project_service import add_project_member, create_project
from app.services.task_service import create_task
from app.services.workspace_service import add_workspace_member, create_workspace


def create_my_tasks_context(app):
    with app.app_context():
        owner_id = register_user("my-tasks-owner", "correct-password", display_name="Project Owner")
        member_id = register_user("my-tasks-member", "correct-password", display_name="Mai Nguyen", email="mai@example.test")
        other_id = register_user("my-tasks-other", "correct-password", display_name="Other User")
        workspace = create_workspace("Kairo Workspace", "", owner_id)
        project = create_project(workspace["id"], owner_id, "Website", "Website project")
        add_workspace_member(workspace["id"], owner_id, member_id)
        add_project_member(workspace["id"], project["id"], owner_id, member_id, "member")
        add_workspace_member(workspace["id"], owner_id, other_id)
        add_project_member(workspace["id"], project["id"], owner_id, other_id, "member")
        second_project = create_project(workspace["id"], owner_id, "Mobile", "Mobile project")
        add_project_member(workspace["id"], second_project["id"], owner_id, member_id, "member")

        sprint_id = get_db().execute(
            """INSERT INTO sprint
                   (project_id, name, start_date, end_date, created_by, updated_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project["id"], "Sprint 08", "2026-10-01", "2026-10-14", owner_id, owner_id),
        ).lastrowid
        get_db().commit()
        assigned_task = create_task(
            workspace["id"], project["id"], owner_id, "Prepare release notes",
            assignee_id=member_id, status="in_progress", priority="high",
            due_date=(date.today() + timedelta(days=2)).isoformat(), sprint_id=sprint_id,
        )
        completed_task = create_task(
            workspace["id"], project["id"], owner_id, "Review design handoff",
            assignee_id=member_id, status="done", priority="low",
        )
        second_project_task = create_task(
            workspace["id"], second_project["id"], owner_id, "Plan mobile rollout",
            assignee_id=member_id, status="todo", priority="medium",
        )
        other_task = create_task(
            workspace["id"], project["id"], owner_id, "Private teammate task",
            assignee_id=other_id,
        )

    client = app.test_client()
    csrf = client.get("/auth/csrf").json["csrf_token"]
    login = client.post(
        "/auth/login",
        json={"username": "my-tasks-member", "password": "correct-password"},
        headers={"X-CSRFToken": csrf},
    )
    assert login.status_code == 200
    return (
        client,
        {"X-CSRFToken": login.json["csrf_token"]},
        workspace["id"],
        project["id"],
        assigned_task,
        completed_task,
        second_project_task,
        other_task,
    )


def test_my_tasks_page_and_api_require_authentication(app):
    client = app.test_client()
    page = client.get("/tasks/my")
    api = client.get("/tasks/api/my")
    assert page.status_code == 401
    assert api.status_code == 401
    assert api.headers["Cache-Control"] == "no-store"


def test_my_tasks_api_returns_only_accessible_tasks_assigned_to_current_user(app):
    client, _, _, _, assigned_task, completed_task, second_project_task, _ = create_my_tasks_context(app)

    response = client.get("/tasks/api/my")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    tasks = response.json["tasks"]
    assert {task["id"] for task in tasks} == {
        assigned_task["id"], completed_task["id"], second_project_task["id"]
    }
    task = next(item for item in tasks if item["id"] == assigned_task["id"])
    assert task["project_name"] == "Website"
    assert task["workspace_name"] == "Kairo Workspace"
    assert task["status"] == "in_progress"
    assert task["priority"] == "high"
    assert task["due_date"] == assigned_task["due_date"]
    assert task["sprint_name"] == "Sprint 08"
    assert task["assignee"] == {
        "id": task["assignee"]["id"],
        "username": "my-tasks-member",
        "display_name": "Mai Nguyen",
        "email": "mai@example.test",
        "avatar_url": None,
    }
    backlog = next(item for item in tasks if item["id"] == completed_task["id"])
    assert backlog["sprint_id"] is None
    assert backlog["sprint_name"] is None
    assert next(item for item in tasks if item["id"] == second_project_task["id"])["project_name"] == "Mobile"


def test_my_tasks_page_renders_grouping_filters_and_safe_status_controls(app):
    client, _, _, _, _, _, _, _ = create_my_tasks_context(app)

    response = client.get("/tasks/my")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Việc của tôi" in html
    assert "data-group=\"project\"" in html
    assert "data-group=\"due\"" in html
    assert "status-filter" in html
    assert "priority-filter" in html
    assert "my-tasks.js" in html
    assert "my-tasks.css" in html
    assert "task-title" not in html


def test_my_tasks_status_toggle_uses_existing_member_permissions(app):
    client, headers, workspace_id, project_id, task, _, _, other_task = create_my_tasks_context(app)
    task_url = f"/workspaces/{workspace_id}/projects/{project_id}/tasks/{task['id']}"

    changed = client.patch(task_url, json={"status": "done"}, headers=headers)
    forbidden_edit = client.patch(task_url, json={"title": "Changed from My Tasks"}, headers=headers)
    other_task_url = f"/workspaces/{workspace_id}/projects/{project_id}/tasks/{other_task['id']}"
    forbidden_status_change = client.patch(
        other_task_url, json={"status": "done"}, headers=headers
    )
    unchanged_task = client.get(other_task_url)

    assert changed.status_code == 200
    assert changed.json["task"]["status"] == "done"
    assert forbidden_edit.status_code == 403
    assert forbidden_edit.json["error"]["code"] == "permission_denied"
    assert forbidden_status_change.status_code == 403
    assert unchanged_task.json["task"]["status"] == "todo"
