import pytest

from app.db import get_db
from app.services.auth_service import register_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_csrf_token(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return response.json["csrf_token"]


def login(client, username="alice", password="secret-password"):
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRFToken": get_csrf_token(client)},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


def create_workspace(client, csrf_token, name="My Workspace"):
    response = client.post(
        "/workspaces",
        json={"name": name},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 201
    return response.json["workspace"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def alice_id(app):
    with app.app_context():
        return register_user("alice", "secret-password")


@pytest.fixture()
def bob_id(app):
    with app.app_context():
        return register_user("bob", "secret-password")


@pytest.fixture()
def alice_csrf(client, alice_id):
    return login(client, "alice", "secret-password")


@pytest.fixture()
def workspace(client, alice_id, alice_csrf):
    return create_workspace(client, alice_csrf)


# ---------------------------------------------------------------------------
# Project CRUD tests
# ---------------------------------------------------------------------------

def test_create_project_success(client, alice_id, alice_csrf, workspace):
    response = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Sprint 1", "description": "First sprint"},
        headers={"X-CSRFToken": alice_csrf},
    )

    assert response.status_code == 201
    project = response.json["project"]
    assert project["name"] == "Sprint 1"
    assert project["description"] == "First sprint"
    assert project["workspace_id"] == workspace["id"]
    assert project["created_by"] == alice_id
    assert project["role"] == "owner"


def test_create_project_requires_authentication(client, alice_id, workspace):
    # Đăng xuất khỏi session của alice (workspace fixture đã login alice)
    csrf = get_csrf_token(client)
    client.post("/auth/logout", headers={"X-CSRFToken": csrf})

    csrf = get_csrf_token(client)
    response = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Sprint 1"},
        headers={"X-CSRFToken": csrf},
    )
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"


def test_create_project_empty_name_fails(client, alice_id, alice_csrf, workspace):
    response = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "   "},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 400
    assert "name" in response.json["error"]["fields"]


def test_create_project_non_member_workspace_fails(app, client, alice_id, alice_csrf, bob_id):
    # alice tạo workspace, bob không phải thành viên
    csrf = alice_csrf
    ws = create_workspace(client, csrf)

    # Đăng xuất alice trước khi login bob
    client.post("/auth/logout", headers={"X-CSRFToken": csrf})
    csrf_bob = login(client, "bob", "secret-password")
    response = client.post(
        f"/workspaces/{ws['id']}/projects",
        json={"name": "Sprint 1"},
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_list_projects_returns_member_projects(client, alice_id, alice_csrf, workspace):
    for name in ["Project A", "Project B"]:
        client.post(
            f"/workspaces/{workspace['id']}/projects",
            json={"name": name},
            headers={"X-CSRFToken": alice_csrf},
        )

    response = client.get(f"/workspaces/{workspace['id']}/projects")
    assert response.status_code == 200
    names = [p["name"] for p in response.json["projects"]]
    assert "Project A" in names
    assert "Project B" in names


def test_get_project_detail(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Detail Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    response = client.get(f"/workspaces/{workspace['id']}/projects/{project_id}")
    assert response.status_code == 200
    assert response.json["project"]["name"] == "Detail Project"


def test_update_project(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Old Name"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    response = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        json={"name": "New Name", "description": "Updated"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 200
    assert response.json["project"]["name"] == "New Name"
    assert response.json["project"]["description"] == "Updated"


def test_delete_project(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "To Delete"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    response = client.delete(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 200
    assert "xóa" in response.json["message"]

    # Xác nhận đã xóa
    get_resp = client.get(f"/workspaces/{workspace['id']}/projects/{project_id}")
    assert get_resp.status_code == 403


# ---------------------------------------------------------------------------
# Project Member tests
# ---------------------------------------------------------------------------

def test_list_members_returns_creator_as_owner(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Team Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    response = client.get(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members"
    )
    assert response.status_code == 200
    members = response.json["members"]
    assert len(members) == 1
    assert members[0]["id"] == alice_id
    assert members[0]["username"] == "alice"


def test_add_member_success(app, client, alice_id, alice_csrf, bob_id, workspace):
    # Thêm bob vào workspace trước
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    # alice tạo project
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Shared Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Thêm bob vào project
    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 201
    member_ids = [m["id"] for m in response.json["members"]]
    assert bob_id in member_ids


def test_add_member_not_in_workspace_fails(app, client, alice_id, alice_csrf, bob_id, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Bob không phải workspace member → 422
    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 422
    assert response.json["error"]["code"] == "not_workspace_member"


def test_add_duplicate_member_fails(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Thêm lần 2 → 409
    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 409
    assert response.json["error"]["code"] == "already_member"


def test_change_member_role(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    response = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{bob_id}",
        json={"role": "admin"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 200
    assert response.json["member"]["role"] == "admin"


def test_remove_last_owner_fails(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Alice là owner duy nhất — xóa mình sẽ thất bại
    response = client.delete(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{alice_id}",
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 409
    assert response.json["error"]["code"] == "last_owner"


def test_delete_project_requires_owner_role(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "admin"},
        headers={"X-CSRFToken": alice_csrf},
    )
    # Đăng xuất alice, đăng nhập bob
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")
    response = client.delete(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_update_project_partial(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Initial Name", "description": "Initial Desc"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Chỉ cập nhật description
    resp1 = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        json={"description": "Updated Desc Only"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert resp1.status_code == 200
    assert resp1.json["project"]["name"] == "Initial Name"
    assert resp1.json["project"]["description"] == "Updated Desc Only"

    # Chỉ cập nhật name
    resp2 = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        json={"name": "Updated Name Only"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert resp2.status_code == 200
    assert resp2.json["project"]["name"] == "Updated Name Only"
    assert resp2.json["project"]["description"] == "Updated Desc Only"

    # Body rỗng -> 400
    resp3 = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        json={},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert resp3.status_code == 400
    assert resp3.json["error"]["code"] == "validation_error"


def test_member_can_leave_project(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Bob đăng nhập và tự rời project
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.delete(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{bob_id}",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 200

    # Bob không còn quyền truy cập project
    get_resp = client.get(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert get_resp.status_code == 403


def test_regular_member_cannot_remove_others(app, client, alice_id, alice_csrf, bob_id, workspace):
    # Tạo user charlie
    with app.app_context():
        charlie_id = register_user("charlie", "secret-password")
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], charlie_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": charlie_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Bob (member) thử xóa charlie (member)
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")
    response = client.delete(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{charlie_id}",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_remove_member_with_assigned_tasks_fails(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project with task"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Gán một task cho Bob
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO task (project_id, title, assignee_id, created_by)
               VALUES (?, 'Important Task', ?, ?)""",
            (project_id, bob_id, alice_id),
        )
        db.commit()

    # Thử xóa Bob khi đang được gán task -> 409 has_assigned_tasks
    response = client.delete(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{bob_id}",
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 409
    assert response.json["error"]["code"] == "has_assigned_tasks"


def test_access_project_from_wrong_workspace_fails(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project In WS 1"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Tạo workspace thứ hai cho alice
    ws2 = create_workspace(client, alice_csrf, name="Second Workspace")

    # Truy cập project_id từ ws2 (sai workspace) -> 403
    response = client.get(
        f"/workspaces/{ws2['id']}/projects/{project_id}",
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_admin_cannot_add_owner(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        charlie_id = register_user("charlie", "secret-password")
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?), (?, ?, ?)",
            (workspace["id"], bob_id, "member", workspace["id"], charlie_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Alice thêm Bob làm admin
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "admin"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Bob đăng nhập và thử thêm Charlie làm owner -> 403
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": charlie_id, "role": "owner"},
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_admin_cannot_change_another_admin_role(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        charlie_id = register_user("charlie", "secret-password")
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?), (?, ?, ?)",
            (workspace["id"], bob_id, "member", workspace["id"], charlie_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Alice thêm Bob và Charlie đều làm admin
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "admin"},
        headers={"X-CSRFToken": alice_csrf},
    )
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": charlie_id, "role": "admin"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Bob thử hạ cấp Charlie xuống member -> 403
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{charlie_id}",
        json={"role": "member"},
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_update_project_requires_admin_or_owner_role(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Bob là member thường
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        json={"name": "New Name"},
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_regular_member_cannot_add_members(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        charlie_id = register_user("charlie", "secret-password")
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?), (?, ?, ?)",
            (workspace["id"], bob_id, "member", workspace["id"], charlie_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Bob là member thường
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": charlie_id, "role": "member"},
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_add_member_rejects_boolean_user_id(client, alice_id, alice_csrf, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": True, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"


def test_list_projects_requires_authentication(client, workspace):
    # Đăng xuất
    csrf = get_csrf_token(client)
    client.post("/auth/logout", headers={"X-CSRFToken": csrf})

    response = client.get(f"/workspaces/{workspace['id']}/projects")
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"


def test_list_projects_for_non_workspace_member_fails(client, alice_id, alice_csrf, bob_id, workspace):
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.get(f"/workspaces/{workspace['id']}/projects")
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


def test_removing_workspace_member_cascades_to_project_member_and_revokes_access(
    app, client, alice_id, alice_csrf, bob_id, workspace
):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Cascade Test Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Thêm Bob vào project
    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    # Bob truy cập được project
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")
    resp_before = client.get(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert resp_before.status_code == 200

    # Xóa Bob khỏi workspace_member
    with app.app_context():
        db = get_db()
        db.execute(
            "DELETE FROM workspace_member WHERE workspace_id = ? AND user_id = ?",
            (workspace["id"], bob_id),
        )
        db.commit()
        # Kiểm tra SQLite cascade xóa tự động trong project_member
        pm = db.execute(
            "SELECT * FROM project_member WHERE project_id = ? AND user_id = ?",
            (project_id, bob_id),
        ).fetchone()
        assert pm is None

    # Bob không còn quyền truy cập project -> 403
    resp_after = client.get(
        f"/workspaces/{workspace['id']}/projects/{project_id}",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert resp_after.status_code == 403
    assert resp_after.json["error"]["code"] == "forbidden"


def test_add_project_member_invalid_role_fails(client, alice_id, alice_csrf, bob_id, workspace):
    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    response = client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "invalid_role"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    assert "role" in response.json["error"]["fields"]


def test_change_project_member_invalid_role_fails(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    client.post(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        json={"user_id": bob_id, "role": "member"},
        headers={"X-CSRFToken": alice_csrf},
    )

    response = client.patch(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members/{bob_id}",
        json={"role": "invalid_role"},
        headers={"X-CSRFToken": alice_csrf},
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    assert "role" in response.json["error"]["fields"]


def test_list_members_requires_project_membership(app, client, alice_id, alice_csrf, bob_id, workspace):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, ?)",
            (workspace["id"], bob_id, "member"),
        )
        db.commit()

    create_resp = client.post(
        f"/workspaces/{workspace['id']}/projects",
        json={"name": "Project"},
        headers={"X-CSRFToken": alice_csrf},
    )
    project_id = create_resp.json["project"]["id"]

    # Bob là thành viên workspace nhưng chưa được thêm vào project
    client.post("/auth/logout", headers={"X-CSRFToken": alice_csrf})
    csrf_bob = login(client, "bob", "secret-password")

    response = client.get(
        f"/workspaces/{workspace['id']}/projects/{project_id}/members",
        headers={"X-CSRFToken": csrf_bob},
    )
    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"



