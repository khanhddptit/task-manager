import pytest

from app.core.db import get_db
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


def project_url(workspace_id, suffix=""):
    return f"/workspaces/{workspace_id}/projects{suffix}"


@pytest.fixture()
def project_context(app):
    with app.app_context():
        user_ids = {
            username: register_user(username, "correct-password")
            for username in ("owner", "workspace_admin", "member", "outsider")
        }
        workspace = create_workspace("Team", "", user_ids["owner"])
        workspace_id = workspace["id"]
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (?, ?, 'admin')",
            (workspace_id, user_ids["workspace_admin"]),
        )
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) "
            "VALUES (?, ?, 'member')",
            (workspace_id, user_ids["member"]),
        )
        db.commit()
    return {"workspace_id": workspace_id, "user_ids": user_ids}


def make_client(app, username):
    client = app.test_client()
    csrf_token = login(client, username)
    return client, {"X-CSRFToken": csrf_token}


def create_project(client, workspace_id, headers, name="Project"):
    return client.post(
        project_url(workspace_id),
        json={"name": name},
        headers=headers,
    )


def add_project_member(app, workspace_id, project_id, user_id, role="member"):
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO project_member
               (project_id, workspace_id, user_id, role)
               VALUES (?, ?, ?, ?)""",
            (project_id, workspace_id, user_id, role),
        )
        db.commit()


def add_workspace_member(app, workspace_id, user_id, role="member"):
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO workspace_member (workspace_id, user_id, role)
               VALUES (?, ?, ?)""",
            (workspace_id, user_id, role),
        )
        db.commit()


def test_project_crud_and_creator_becomes_admin(app, project_context):
    workspace_id = project_context["workspace_id"]
    owner, headers = make_client(app, "owner")

    response = create_project(owner, workspace_id, headers, "  Roadmap  ")
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    project = response.json["project"]
    assert project["name"] == "Roadmap"
    assert project["description"] == ""
    assert project["role"] == "admin"
    project_id = project["id"]

    detail = owner.get(project_url(workspace_id, f"/{project_id}"))
    assert detail.status_code == 200
    assert detail.json["project"]["id"] == project_id

    update = owner.patch(
        project_url(workspace_id, f"/{project_id}"),
        json={"description": "Delivery plan"},
        headers=headers,
    )
    assert update.status_code == 200
    assert update.json["project"]["name"] == "Roadmap"
    assert update.json["project"]["description"] == "Delivery plan"

    listing = owner.get(project_url(workspace_id))
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json["projects"]] == [project_id]

    deleted = owner.delete(
        project_url(workspace_id, f"/{project_id}"), headers=headers
    )
    assert deleted.status_code == 200
    assert owner.get(project_url(workspace_id, f"/{project_id}")).status_code == 404


def test_workspace_owner_has_implicit_access_but_workspace_admin_does_not(
    app, project_context
):
    workspace_id = project_context["workspace_id"]
    user_ids = project_context["user_ids"]
    workspace_admin, admin_headers = make_client(app, "workspace_admin")

    created = create_project(
        workspace_admin, workspace_id, admin_headers, "Admin project"
    )
    assert created.status_code == 201
    project_id = created.json["project"]["id"]

    owner, owner_headers = make_client(app, "owner")
    owner_detail = owner.get(project_url(workspace_id, f"/{project_id}"))
    assert owner_detail.status_code == 200
    assert owner_detail.json["project"]["role"] == "admin"

    member, _ = make_client(app, "member")
    forbidden = member.get(project_url(workspace_id, f"/{project_id}"))
    assert forbidden.status_code == 403

    with app.app_context():
        db = get_db()
        assert db.execute(
            "SELECT role FROM workspace_member WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_ids["workspace_admin"]),
        ).fetchone()["role"] == "admin"
        assert db.execute(
            "SELECT 1 FROM project_member WHERE project_id = ? AND user_id = ?",
            (project_id, user_ids["owner"]),
        ).fetchone() is None


def test_project_admin_cannot_assign_admin_directly(app, project_context):
    workspace_id = project_context["workspace_id"]
    user_ids = project_context["user_ids"]
    owner, owner_headers = make_client(app, "owner")
    project_id = create_project(owner, workspace_id, owner_headers).json["project"]["id"]
    add_project_member(app, workspace_id, project_id, user_ids["workspace_admin"], "admin")
    add_workspace_member(app, workspace_id, user_ids["outsider"])
    project_admin, admin_headers = make_client(app, "workspace_admin")

    response = project_admin.post(
        project_url(workspace_id, f"/{project_id}/members"),
        json={"user_id": user_ids["outsider"], "role": "admin"},
        headers=admin_headers,
    )
    assert response.status_code == 403


def test_project_admin_promotes_member_only_inside_project(app, project_context):
    workspace_id = project_context["workspace_id"]
    user_ids = project_context["user_ids"]
    owner, owner_headers = make_client(app, "owner")
    project_id = create_project(owner, workspace_id, owner_headers).json["project"]["id"]
    add_project_member(app, workspace_id, project_id, user_ids["workspace_admin"], "admin")
    add_workspace_member(app, workspace_id, user_ids["outsider"])
    add_project_member(app, workspace_id, project_id, user_ids["outsider"])
    project_admin, admin_headers = make_client(app, "workspace_admin")

    response = project_admin.patch(
        project_url(
            workspace_id,
            f"/{project_id}/members/{user_ids['outsider']}",
        ),
        json={"role": "admin"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json["member"]["role"] == "admin"
    with app.app_context():
        role = get_db().execute(
            "SELECT role FROM workspace_member WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_ids["outsider"]),
        ).fetchone()["role"]
    assert role == "member"


def test_workspace_member_must_exist_before_project_invite(app, project_context):
    workspace_id = project_context["workspace_id"]
    user_ids = project_context["user_ids"]
    owner, headers = make_client(app, "owner")
    project_id = create_project(owner, workspace_id, headers).json["project"]["id"]

    response = owner.post(
        project_url(workspace_id, f"/{project_id}/members"),
        json={"user_id": user_ids["outsider"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "target_not_workspace_member"


def test_project_member_cannot_edit_or_delete_project(app, project_context):
    workspace_id = project_context["workspace_id"]
    user_ids = project_context["user_ids"]
    owner, owner_headers = make_client(app, "owner")
    project_id = create_project(owner, workspace_id, owner_headers).json["project"]["id"]
    add_project_member(app, workspace_id, project_id, user_ids["member"])

    member, member_headers = make_client(app, "member")
    response = member.patch(
        project_url(workspace_id, f"/{project_id}"),
        json={"name": "Changed"},
        headers=member_headers,
    )
    assert response.status_code == 403
    assert member.delete(
        project_url(workspace_id, f"/{project_id}"), headers=member_headers
    ).status_code == 403


def test_project_admin_cannot_remove_peer_or_member_with_assigned_task(
    app, project_context
):
    workspace_id = project_context["workspace_id"]
    user_ids = project_context["user_ids"]
    owner, owner_headers = make_client(app, "owner")
    project_id = create_project(owner, workspace_id, owner_headers).json["project"]["id"]
    add_project_member(app, workspace_id, project_id, user_ids["workspace_admin"], "admin")
    add_project_member(app, workspace_id, project_id, user_ids["member"], "member")

    project_admin, admin_headers = make_client(app, "workspace_admin")
    peer_removal = project_admin.delete(
        project_url(
            workspace_id,
            f"/{project_id}/members/{user_ids['owner']}",
        ),
        headers=admin_headers,
    )
    assert peer_removal.status_code == 403

    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO task (project_id, title, assignee_id) VALUES (?, ?, ?)",
            (project_id, "Assigned task", user_ids["member"]),
        )
        db.commit()

    blocked = project_admin.delete(
        project_url(workspace_id, f"/{project_id}/members/{user_ids['member']}"),
        headers=admin_headers,
    )
    assert blocked.status_code == 409
    assert blocked.json["error"]["code"] == "member_has_assigned_tasks"


def test_delete_project_cascades_tasks_and_comments(app, project_context):
    workspace_id = project_context["workspace_id"]
    owner, headers = make_client(app, "owner")
    project_id = create_project(owner, workspace_id, headers).json["project"]["id"]
    with app.app_context():
        db = get_db()
        task_id = db.execute(
            "INSERT INTO task (project_id, title) VALUES (?, ?)",
            (project_id, "Cascade task"),
        ).lastrowid
        db.execute(
            "INSERT INTO comment (task_id, content) VALUES (?, ?)",
            (task_id, "Cascade comment"),
        )
        db.commit()

    response = owner.delete(
        project_url(workspace_id, f"/{project_id}"), headers=headers
    )
    assert response.status_code == 200
    with app.app_context():
        db = get_db()
        assert db.execute(
            "SELECT COUNT(*) FROM task WHERE project_id = ?", (project_id,)
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM comment WHERE task_id = ?", (task_id,)
        ).fetchone()[0] == 0


def test_project_api_requires_authentication_and_validates_payload(
    app, project_context
):
    workspace_id = project_context["workspace_id"]
    unauthenticated = app.test_client()
    response = unauthenticated.get(project_url(workspace_id))
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"

    owner, headers = make_client(app, "owner")
    invalid = owner.post(
        project_url(workspace_id), json={"name": "   "}, headers=headers
    )
    assert invalid.status_code == 400
    assert "name" in invalid.json["error"]["fields"]

    project_id = create_project(owner, workspace_id, headers).json["project"]["id"]
    empty_patch = owner.patch(
        project_url(workspace_id, f"/{project_id}"), json={}, headers=headers
    )
    assert empty_patch.status_code == 400
