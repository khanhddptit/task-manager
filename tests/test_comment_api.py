import pytest

from app.core.db import get_db
from app.services.auth_service import register_user


def get_csrf_token(client):
    response = client.get("/auth/csrf")
    assert response.status_code == 200
    return response.json["csrf_token"]


def login(client, username, password="correct-password"):
    with client.session_transaction() as session:
        session.clear()
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRFToken": get_csrf_token(client)},
    )
    assert response.status_code == 200
    return response.json["csrf_token"]


@pytest.fixture()
def seeded_env(app):
    with app.app_context():
        # Tạo 5 user
        owner_id = register_user("owner_user", "correct-password")
        admin_id = register_user("admin_user", "correct-password")
        member_id = register_user("member_user", "correct-password")
        ws_only_id = register_user("ws_only_user", "correct-password")
        outsider_id = register_user("outsider_user", "correct-password")

        db = get_db()
        # Workspace 1 & 2
        db.execute(
            "INSERT INTO workspace (id, name, created_by) VALUES (1, 'Workspace 1', ?), (2, 'Workspace 2', ?)",
            (owner_id, owner_id),
        )

        # Workspace 1 memberships:
        # owner_id là owner
        # admin_id, member_id, ws_only_id là member
        db.execute(
            """
            INSERT INTO workspace_member (workspace_id, user_id, role)
            VALUES (1, ?, 'owner'),
                   (1, ?, 'member'),
                   (1, ?, 'member'),
                   (1, ?, 'member')
            """,
            (owner_id, admin_id, member_id, ws_only_id),
        )

        # Project 1 thuộc Workspace 1
        db.execute(
            "INSERT INTO project (id, workspace_id, name, created_by) VALUES (1, 1, 'Project 1', ?)",
            (owner_id,),
        )
        # Project 2 thuộc Workspace 1 (để test cross-project/cross-task)
        db.execute(
            "INSERT INTO project (id, workspace_id, name, created_by) VALUES (2, 1, 'Project 2', ?)",
            (owner_id,),
        )

        # Project 1 memberships:
        # admin_id là admin
        # member_id là member
        # (owner_id KHÔNG có trong project_member nhưng là Workspace Owner)
        # (ws_only_id KHÔNG có trong project_member)
        db.execute(
            """
            INSERT INTO project_member (project_id, workspace_id, user_id, role)
            VALUES (1, 1, ?, 'admin'),
                   (1, 1, ?, 'member')
            """,
            (admin_id, member_id),
        )

        # Task 1 thuộc Project 1
        db.execute(
            "INSERT INTO task (id, project_id, title, created_by) VALUES (1, 1, 'Task 1', ?)",
            (admin_id,),
        )
        # Task 2 thuộc Project 2
        db.execute(
            "INSERT INTO task (id, project_id, title, created_by) VALUES (2, 2, 'Task 2', ?)",
            (owner_id,),
        )
        db.commit()

    return {
        "owner_id": owner_id,
        "admin_id": admin_id,
        "member_id": member_id,
        "ws_only_id": ws_only_id,
        "outsider_id": outsider_id,
        "workspace_id": 1,
        "project_id": 1,
        "task_id": 1,
    }


# ===========================================================================
# 1. CRUD LUỒNG CHUẨN (HAPPY PATH) & FORMAT RESPONSE
# ===========================================================================

def test_create_comment_success(client, seeded_env):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"
    response = client.post(
        url,
        json={"content": "  Đây là bình luận đầu tiên.  "},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json
    assert "comment" in data
    comment = data["comment"]
    assert comment["id"] is not None
    assert comment["task_id"] == t_id
    assert comment["author_id"] == seeded_env["member_id"]
    assert comment["author_username"] == "member_user"
    assert comment["content"] == "Đây là bình luận đầu tiên."
    assert comment["created_at"] is not None
    assert comment["updated_at"] is not None
    assert comment["updated_by"] == seeded_env["member_id"]


def test_list_comments_ordered_by_created_at_and_id_asc(client, seeded_env, app):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    # Tạo 3 comment với cùng timestamp để kiểm tra sắp xếp id ASC
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO comment (id, task_id, author_id, content, created_at, updated_at, updated_by)
            VALUES (10, ?, ?, 'Comment 10', '2026-01-01 10:00:00', '2026-01-01 10:00:00', ?),
                   (5, ?, ?, 'Comment 5', '2026-01-01 10:00:00', '2026-01-01 10:00:00', ?),
                   (12, ?, ?, 'Comment 12', '2026-01-01 11:00:00', '2026-01-01 11:00:00', ?)
            """,
            (
                t_id, seeded_env["member_id"], seeded_env["member_id"],
                t_id, seeded_env["member_id"], seeded_env["member_id"],
                t_id, seeded_env["member_id"], seeded_env["member_id"],
            ),
        )
        db.commit()

    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json
    assert "comments" in data
    comments = data["comments"]
    assert len(comments) == 3
    # Sắp xếp theo created_at ASC, id ASC -> ID: 5, 10, 12
    assert [c["id"] for c in comments] == [5, 10, 12]
    assert comments[0]["content"] == "Comment 5"
    assert comments[1]["content"] == "Comment 10"
    assert comments[2]["content"] == "Comment 12"


def test_update_comment_success(client, seeded_env):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # Tạo comment
    create_res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Nội dung cũ"},
        headers={"X-CSRFToken": csrf},
    )
    c_id = create_res.json["comment"]["id"]
    old_created_at = create_res.json["comment"]["created_at"]

    # Cập nhật comment
    update_res = client.patch(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        json={"content": "  Nội dung đã sửa  "},
        headers={"X-CSRFToken": csrf},
    )
    assert update_res.status_code == 200
    updated_comment = update_res.json["comment"]
    assert updated_comment["content"] == "Nội dung đã sửa"
    assert updated_comment["author_id"] == seeded_env["member_id"]
    assert updated_comment["created_at"] == old_created_at
    assert updated_comment["updated_by"] == seeded_env["member_id"]


def test_delete_comment_by_author(client, seeded_env):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # Tạo comment
    create_res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Sẽ bị xóa"},
        headers={"X-CSRFToken": csrf},
    )
    c_id = create_res.json["comment"]["id"]

    # Tác giả xóa comment
    delete_res = client.delete(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        headers={"X-CSRFToken": csrf},
    )
    assert delete_res.status_code == 200
    assert delete_res.json["message"] == "Bình luận đã được xóa."

    # Danh sách comment sau khi xóa phải rỗng
    list_res = client.get(f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments")
    assert list_res.json["comments"] == []


# ===========================================================================
# 2. XỬ LÝ TÁC GIẢ BỊ XÓA (LEFT JOIN & AUTHOR_USERNAME: NULL)
# ===========================================================================

def test_deleted_author_comment_preserves_history(client, seeded_env, app):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # Tạo comment bởi member_user
    create_res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Bình luận lưu vết lịch sử"},
        headers={"X-CSRFToken": csrf},
    )
    c_id = create_res.json["comment"]["id"]

    # Giả lập xóa member_user khỏi database (schema ON DELETE SET NULL)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE task SET assignee_id = NULL WHERE id = ?", (t_id,))
        db.execute("DELETE FROM user WHERE id = ?", (seeded_env["member_id"],))
        db.commit()

    # Login bằng admin_user để xem lại danh sách comment
    admin_csrf = login(client, "admin_user")
    list_res = client.get(f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments")
    assert list_res.status_code == 200
    comments = list_res.json["comments"]
    assert len(comments) == 1
    assert comments[0]["id"] == c_id
    assert comments[0]["author_id"] is None
    assert comments[0]["author_username"] is None
    assert comments[0]["content"] == "Bình luận lưu vết lịch sử"


# ===========================================================================
# 3. PHÂN QUYỀN (RBAC) THEO QUY TẮC ĐÃ CHỐT
# ===========================================================================

def test_unauthenticated_request_rejected(client, seeded_env):
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    res = client.get(url)
    assert res.status_code == 401
    assert res.json["error"]["code"] == "authentication_required"

    csrf = get_csrf_token(client)
    res = client.post(url, json={"content": "test"}, headers={"X-CSRFToken": csrf})
    assert res.status_code == 401
    assert res.json["error"]["code"] == "authentication_required"


def test_workspace_member_not_in_project_rejected(client, seeded_env):
    # ws_only_user là thành viên workspace 1 nhưng KHÔNG thuộc project 1
    csrf = login(client, "ws_only_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    # GET bị từ chối
    get_res = client.get(url)
    assert get_res.status_code == 403
    assert get_res.json["error"]["code"] == "forbidden"

    # POST bị từ chối
    post_res = client.post(url, json={"content": "lén bình luận"}, headers={"X-CSRFToken": csrf})
    assert post_res.status_code == 403
    assert post_res.json["error"]["code"] == "forbidden"


def test_workspace_admin_not_in_project_rejected(client, seeded_env, app):
    # Đặt ws_only_user thành workspace admin nhưng không thuộc project_member
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE workspace_member SET role = 'admin' WHERE workspace_id = ? AND user_id = ?",
            (seeded_env["workspace_id"], seeded_env["ws_only_id"]),
        )
        db.commit()

    csrf = login(client, "ws_only_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    # Workspace Admin không tự có quyền trong mọi project -> 403
    assert client.get(url).status_code == 403
    assert client.post(url, json={"content": "test"}, headers={"X-CSRFToken": csrf}).status_code == 403


def test_workspace_owner_access_without_project_member(client, seeded_env):
    # owner_user là Workspace Owner, không có bản ghi trong project_member
    csrf = login(client, "owner_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    # Workspace Owner đọc danh sách thành công
    get_res = client.get(url)
    assert get_res.status_code == 200

    # Workspace Owner tạo bình luận thành công
    post_res = client.post(url, json={"content": "Owner comment"}, headers={"X-CSRFToken": csrf})
    assert post_res.status_code == 201


def test_project_admin_can_delete_member_comment(client, seeded_env):
    # member tạo comment
    member_csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment của member"},
        headers={"X-CSRFToken": member_csrf},
    )
    c_id = res.json["comment"]["id"]

    # admin_user (Project Admin) xóa comment của member -> thành công (200)
    admin_csrf = login(client, "admin_user")
    del_res = client.delete(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        headers={"X-CSRFToken": admin_csrf},
    )
    assert del_res.status_code == 200


def test_workspace_owner_can_delete_any_comment(client, seeded_env):
    member_csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment chuẩn bị bị owner xóa"},
        headers={"X-CSRFToken": member_csrf},
    )
    c_id = res.json["comment"]["id"]

    owner_csrf = login(client, "owner_user")
    del_res = client.delete(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        headers={"X-CSRFToken": owner_csrf},
    )
    assert del_res.status_code == 200


def test_regular_member_cannot_update_others_comment(client, seeded_env, app):
    # Tạo thêm 1 project member khác
    with app.app_context():
        second_member_id = register_user("second_member", "correct-password")
        db = get_db()
        db.execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES (?, ?, 'member')",
            (seeded_env["workspace_id"], second_member_id),
        )
        db.execute(
            "INSERT INTO project_member (project_id, workspace_id, user_id, role) VALUES (?, ?, ?, 'member')",
            (seeded_env["project_id"], seeded_env["workspace_id"], second_member_id),
        )
        db.commit()

    member_csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment của member 1"},
        headers={"X-CSRFToken": member_csrf},
    )
    c_id = res.json["comment"]["id"]

    # second_member cố sửa comment của member 1 -> 403
    second_csrf = login(client, "second_member")
    patch_res = client.patch(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        json={"content": "Sửa trộm"},
        headers={"X-CSRFToken": second_csrf},
    )
    assert patch_res.status_code == 403
    assert patch_res.json["error"]["code"] == "forbidden"


def test_project_admin_cannot_update_others_comment(client, seeded_env):
    # Ngay cả Project Admin cũng không được phép sửa nội dung bình luận của tác giả khác (chỉ được xóa)
    member_csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment của member"},
        headers={"X-CSRFToken": member_csrf},
    )
    c_id = res.json["comment"]["id"]

    admin_csrf = login(client, "admin_user")
    patch_res = client.patch(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        json={"content": "Admin sửa hộ"},
        headers={"X-CSRFToken": admin_csrf},
    )
    assert patch_res.status_code == 403
    assert patch_res.json["error"]["code"] == "forbidden"


def test_author_lost_project_access_cannot_update_or_delete(client, seeded_env, app):
    member_csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # member tạo comment
    res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment lúc còn trong project"},
        headers={"X-CSRFToken": member_csrf},
    )
    c_id = res.json["comment"]["id"]

    # Xóa member khỏi project_member
    with app.app_context():
        db = get_db()
        db.execute(
            "DELETE FROM project_member WHERE project_id = ? AND user_id = ?",
            (p_id, seeded_env["member_id"]),
        )
        db.commit()

    # Thử sửa -> 403 vì không còn quyền truy cập project
    patch_res = client.patch(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        json={"content": "Cố sửa sau khi bị kick"},
        headers={"X-CSRFToken": member_csrf},
    )
    assert patch_res.status_code == 403

    # Thử xóa -> 403
    del_res = client.delete(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        headers={"X-CSRFToken": member_csrf},
    )
    assert del_res.status_code == 403


# ===========================================================================
# 4. VALIDATION & ERROR HANDLING
# ===========================================================================

@pytest.mark.parametrize("invalid_content", [
    "",
    "   ",
    None,
    123,
    [],
    {},
    "x" * 5001,
])
def test_create_comment_validation_errors(client, seeded_env, invalid_content):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    res = client.post(url, json={"content": invalid_content}, headers={"X-CSRFToken": csrf})
    assert res.status_code == 400
    assert res.json["error"]["code"] == "validation_error"
    assert "content" in res.json["error"]["fields"]


def test_create_comment_missing_field(client, seeded_env):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    res = client.post(url, json={}, headers={"X-CSRFToken": csrf})
    assert res.status_code == 400
    assert res.json["error"]["code"] == "validation_error"


def test_invalid_request_body_format(client, seeded_env):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    # Non-JSON content type -> 415
    res = client.post(url, data="content=test", content_type="text/plain", headers={"X-CSRFToken": csrf})
    assert res.status_code == 415
    assert res.json["error"]["code"] == "unsupported_media_type"

    # Malformed JSON -> 400
    res = client.post(url, data="{invalid json", content_type="application/json", headers={"X-CSRFToken": csrf})
    assert res.status_code == 400


def test_csrf_token_required_for_mutations(client, seeded_env):
    login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    url = f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments"

    # POST không có CSRF
    res = client.post(url, json={"content": "test"})
    assert res.status_code == 400
    assert res.json["error"]["code"] == "csrf_failed"

    # PATCH với token giả
    res = client.patch(f"{url}/1", json={"content": "test"}, headers={"X-CSRFToken": "invalid"})
    assert res.status_code == 400
    assert res.json["error"]["code"] == "csrf_failed"


# ===========================================================================
# 5. TOÀN VẸN QUAN HỆ & 404 NOT FOUND
# ===========================================================================

def test_hierarchy_mismatch_returns_404(client, seeded_env):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # Sai workspace_id
    res = client.get(f"/workspaces/999/projects/{p_id}/tasks/{t_id}/comments")
    assert res.status_code == 404
    assert res.json["error"]["code"] == "not_found"

    # Sai project_id
    res = client.get(f"/workspaces/{ws_id}/projects/999/tasks/{t_id}/comments")
    assert res.status_code == 404

    # Sai task_id
    res = client.get(f"/workspaces/{ws_id}/projects/{p_id}/tasks/999/comments")
    assert res.status_code == 404

    # Task 2 thuộc Project 2 nhưng gọi dưới URL của Project 1
    res = client.get(f"/workspaces/{ws_id}/projects/{p_id}/tasks/2/comments")
    assert res.status_code == 404


def test_comment_not_found_or_belongs_to_another_task(client, seeded_env, app):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # Sửa comment không tồn tại -> 404
    res = client.patch(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/999",
        json={"content": "sửa"},
        headers={"X-CSRFToken": csrf},
    )
    assert res.status_code == 404

    # Tạo comment thuộc Task 2
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO comment (id, task_id, author_id, content, created_at, updated_at)
            VALUES (88, 2, ?, 'Task 2 comment', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            (seeded_env["owner_id"],),
        )
        db.commit()

    # Cố truy cập comment 88 dưới URL của Task 1 -> 404
    res = client.patch(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/88",
        json={"content": "hack cross-task"},
        headers={"X-CSRFToken": csrf},
    )
    assert res.status_code == 404


# ===========================================================================
# 6. CASCADE DELETE KHI XÓA TASK
# ===========================================================================

def test_cascade_delete_task_deletes_comments(client, seeded_env, app):
    csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    # Tạo 2 comment cho task 1
    client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment 1"},
        headers={"X-CSRFToken": csrf},
    )
    client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment 2"},
        headers={"X-CSRFToken": csrf},
    )

    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM comment WHERE task_id = ?", (t_id,)).fetchone()[0] == 2

        # Xóa task
        db.execute("DELETE FROM task WHERE id = ?", (t_id,))
        db.commit()

        # Comment tự động bị xóa theo CASCADE
        assert db.execute("SELECT COUNT(*) FROM comment WHERE task_id = ?", (t_id,)).fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_project_admin_strictly_requires_admin_role(client, seeded_env, app):
    # Tạo comment bởi member_user
    member_csrf = login(client, "member_user")
    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]

    res = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment của member"},
        headers={"X-CSRFToken": member_csrf},
    )
    c_id = res.json["comment"]["id"]

    # Đảm bảo admin_user có role 'admin' trong project_member và xóa thành công
    admin_csrf = login(client, "admin_user")
    del_res = client.delete(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id}",
        headers={"X-CSRFToken": admin_csrf},
    )
    assert del_res.status_code == 200

    # Nếu admin_user bị hạ quyền xuống 'member' trong project_member
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE project_member SET role = 'member' WHERE project_id = ? AND user_id = ?",
            (p_id, seeded_env["admin_id"]),
        )
        db.commit()

    # Đăng nhập lại member để tạo comment mới
    member_csrf = login(client, "member_user")
    res2 = client.post(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments",
        json={"content": "Comment mới của member"},
        headers={"X-CSRFToken": member_csrf},
    )
    assert res2.status_code == 201
    c_id2 = res2.json["comment"]["id"]

    # admin_user giờ chỉ là 'member' -> xóa comment của người khác bị 403
    admin_csrf = login(client, "admin_user")
    del_res2 = client.delete(
        f"/workspaces/{ws_id}/projects/{p_id}/tasks/{t_id}/comments/{c_id2}",
        headers={"X-CSRFToken": admin_csrf},
    )
    assert del_res2.status_code == 403
    assert del_res2.json["error"]["code"] == "forbidden"


def test_write_transaction_is_active_during_permission_check(app, seeded_env):
    from unittest.mock import patch
    import app.services.comment_service as cs
    from app.core.db import get_db

    ws_id = seeded_env["workspace_id"]
    p_id = seeded_env["project_id"]
    t_id = seeded_env["task_id"]
    u_id = seeded_env["member_id"]

    original_ensure_access = cs._ensure_project_access
    in_tx_flags = []

    def wrapped_ensure_access(*args, **kwargs):
        in_tx_flags.append(get_db().in_transaction)
        return original_ensure_access(*args, **kwargs)

    with app.app_context():
        with patch("app.services.comment_service._ensure_project_access", side_effect=wrapped_ensure_access):
            # 1. create_comment mở transaction ngay từ bước kiểm tra quyền
            comment = cs.create_comment(ws_id, p_id, t_id, {"content": "tx test"}, u_id)
            assert in_tx_flags[-1] is True

            # 2. update_comment_content mở transaction ngay từ bước kiểm tra quyền
            cs.update_comment_content(ws_id, p_id, t_id, comment["id"], {"content": "tx test edited"}, u_id)
            assert in_tx_flags[-1] is True

            # 3. delete_comment_by_id mở transaction ngay từ bước kiểm tra quyền
            cs.delete_comment_by_id(ws_id, p_id, t_id, comment["id"], u_id)
            assert in_tx_flags[-1] is True
