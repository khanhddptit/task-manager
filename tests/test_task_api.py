from app.db import get_db
from app.services.auth_service import register_user
from app.services.workspace_service import create_workspace


def login(client, username):
    csrf_response = client.get("/auth/csrf")
    response = client.post(
        "/auth/login",
        json={"username": username, "password": "correct-password"},
        headers={"X-CSRFToken": csrf_response.json["csrf_token"]},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


def task_collection_url(workspace_id, project_id):
    return f"/workspaces/{workspace_id}/projects/{project_id}/tasks"


def task_url(workspace_id, project_id, task_id):
    return f"{task_collection_url(workspace_id, project_id)}/{task_id}"


def make_client(app, username):
    client = app.test_client()
    csrf_token = login(client, username)
    return client, {"X-CSRFToken": csrf_token}


def add_project_member(app, project_id, workspace_id, user_id, role):
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO project_member
               (project_id, workspace_id, user_id, role)
               VALUES (?, ?, ?, ?)""",
            (project_id, workspace_id, user_id, role),
        )
        db.commit()


def insert_task(app, project_id, title, *, assignee_id=None, status="todo"):
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            """INSERT INTO task (project_id, title, assignee_id, status)
               VALUES (?, ?, ?, ?)""",
            (project_id, title, assignee_id, status),
        )
        db.commit()
        return cursor.lastrowid


def task_world(app):
    with app.app_context():
        user_ids = {
            username: register_user(username, "correct-password")
            for username in ("owner", "admin", "member", "outsider")
        }
        workspace = create_workspace("Team", "", user_ids["owner"])
        workspace_id = workspace["id"]
        db = get_db()
        for username in ("admin", "member", "outsider"):
            db.execute(
                """INSERT INTO workspace_member (workspace_id, user_id, role)
                   VALUES (?, ?, 'member')""",
                (workspace_id, user_ids[username]),
            )
        project_id = db.execute(
            """INSERT INTO project (workspace_id, name, created_by)
               VALUES (?, 'Project', ?)""",
            (workspace_id, user_ids["owner"]),
        ).lastrowid
        other_project_id = db.execute(
            """INSERT INTO project (workspace_id, name, created_by)
               VALUES (?, 'Other project', ?)""",
            (workspace_id, user_ids["owner"]),
        ).lastrowid
        db.commit()

    add_project_member(
        app, project_id, workspace_id, user_ids["admin"], "admin"
    )
    add_project_member(
        app, project_id, workspace_id, user_ids["member"], "member"
    )
    add_project_member(
        app, other_project_id, workspace_id, user_ids["admin"], "admin"
    )
    add_project_member(
        app, other_project_id, workspace_id, user_ids["member"], "member"
    )
    assigned_task_id = insert_task(
        app, project_id, "Assigned task", assignee_id=user_ids["member"]
    )
    other_task_id = insert_task(app, other_project_id, "Other project task")
    return {
        "workspace_id": workspace_id,
        "project_id": project_id,
        "other_project_id": other_project_id,
        "user_ids": user_ids,
        "assigned_task_id": assigned_task_id,
        "other_task_id": other_task_id,
    }


def test_task_crud_and_project_member_read_access(app):
    world = task_world(app)
    workspace_id = world["workspace_id"]
    project_id = world["project_id"]
    owner, owner_headers = make_client(app, "owner")
    member, _ = make_client(app, "member")

    created = owner.post(
        task_collection_url(workspace_id, project_id),
        json={
            "title": "  Prepare release  ",
            "description": "  Release checklist  ",
            "assignee_id": world["user_ids"]["member"],
            "due_date": "2026-10-31",
        },
        headers=owner_headers,
    )
    assert created.status_code == 201
    assert created.json["task"]["title"] == "Prepare release"
    assert created.json["task"]["description"] == "Release checklist"
    assert created.json["task"]["status"] == "todo"
    assert created.json["task"]["assignee_id"] == world["user_ids"]["member"]
    assert created.json["task"]["created_by"] == world["user_ids"]["owner"]
    task_id = created.json["task"]["id"]

    read = member.get(task_url(workspace_id, project_id, task_id))
    assert read.status_code == 200
    assert read.json["task"]["id"] == task_id

    updated = owner.patch(
        task_url(workspace_id, project_id, task_id),
        json={"title": "Release", "status": "in_progress"},
        headers=owner_headers,
    )
    assert updated.status_code == 200
    assert updated.json["task"]["title"] == "Release"
    assert updated.json["task"]["status"] == "in_progress"

    deleted = owner.delete(
        task_url(workspace_id, project_id, task_id),
        headers=owner_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json["message"]
    assert owner.get(task_url(workspace_id, project_id, task_id)).status_code == 404


def test_task_list_filters_by_status_and_assignee(app):
    world = task_world(app)
    workspace_id = world["workspace_id"]
    project_id = world["project_id"]
    member, _ = make_client(app, "member")
    with app.app_context():
        get_db().execute(
            "UPDATE task SET status = 'in_progress' WHERE id = ?",
            (world["assigned_task_id"],),
        )
        get_db().commit()
    insert_task(app, project_id, "Unassigned todo")

    response = member.get(
        f"{task_collection_url(workspace_id, project_id)}"
        f"?status=in_progress&assignee_id={world['user_ids']['member']}"
    )
    assert response.status_code == 200
    assert [task["id"] for task in response.json["tasks"]] == [
        world["assigned_task_id"]
    ]


def test_member_can_only_change_status_of_assigned_task(app):
    world = task_world(app)
    member, headers = make_client(app, "member")
    collection_url = task_collection_url(world["workspace_id"], world["project_id"])
    url = task_url(
        world["workspace_id"], world["project_id"], world["assigned_task_id"]
    )

    forbidden = member.post(
        collection_url, json={"title": "Member created"}, headers=headers
    )
    assert forbidden.status_code == 403

    updated = member.patch(url, json={"status": "done"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json["task"]["status"] == "done"

    forbidden = member.patch(
        url, json={"title": "Changed title"}, headers=headers
    )
    assert forbidden.status_code == 403

    forbidden = member.delete(url, headers=headers)
    assert forbidden.status_code == 403

    unassigned_task_id = insert_task(app, world["project_id"], "Unassigned")
    forbidden = member.patch(
        task_url(world["workspace_id"], world["project_id"], unassigned_task_id),
        json={"status": "done"},
        headers=headers,
    )
    assert forbidden.status_code == 403

    admin, admin_headers = make_client(app, "admin")
    created = admin.post(
        collection_url, json={"title": "Admin created"}, headers=admin_headers
    )
    assert created.status_code == 201


def test_non_project_member_cannot_access_tasks(app):
    world = task_world(app)
    outsider, _ = make_client(app, "outsider")
    response = outsider.get(
        task_collection_url(world["workspace_id"], world["project_id"])
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "permission_denied"


def test_task_ids_are_scoped_to_project_and_workspace(app):
    world = task_world(app)
    admin, _ = make_client(app, "admin")

    wrong_project = admin.get(
        task_url(world["workspace_id"], world["project_id"], world["other_task_id"])
    )
    assert wrong_project.status_code == 404
    assert wrong_project.json["error"]["code"] == "task_not_found"

    wrong_workspace = admin.get(
        task_url(
            world["workspace_id"] + 1,
            world["project_id"],
            world["assigned_task_id"],
        )
    )
    assert wrong_workspace.status_code == 404


def test_task_payload_validation_returns_consistent_json_errors(app):
    world = task_world(app)
    admin, headers = make_client(app, "admin")
    url = task_collection_url(world["workspace_id"], world["project_id"])

    response = admin.post(url, json={"title": " "}, headers=headers)
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    assert "title" in response.json["error"]["fields"]

    response = admin.post(
        url, json={"title": "Valid", "unexpected": "value"}, headers=headers
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    assert "unexpected" in response.json["error"]["fields"]

    response = admin.post(url, json={"title": "Valid", "status": "blocked"}, headers=headers)
    assert response.status_code == 400
    assert "status" in response.json["error"]["fields"]

    response = admin.patch(
        task_url(world["workspace_id"], world["project_id"], world["assigned_task_id"]),
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    assert "task" in response.json["error"]["fields"]

    response = admin.get(f"{url}?status=invalid")
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"


def test_assignments_must_be_project_members(app):
    world = task_world(app)
    admin, headers = make_client(app, "admin")
    response = admin.post(
        task_collection_url(world["workspace_id"], world["project_id"]),
        json={"title": "Invalid assignment", "assignee_id": world["user_ids"]["outsider"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "invalid_assignee"


def test_task_api_requires_login_and_csrf(app):
    world = task_world(app)
    client = app.test_client()
    url = task_collection_url(world["workspace_id"], world["project_id"])

    response = client.get(url)
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"

    authenticated, _ = make_client(app, "admin")
    response = authenticated.post(url, json={"title": "No CSRF token"})
    assert response.status_code == 400
    assert response.json["error"]["code"] == "csrf_failed"
