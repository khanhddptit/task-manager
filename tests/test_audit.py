import sqlite3
from datetime import datetime

import pytest

from app.db import get_db
from app.services.auth_service import register_user


@pytest.fixture()
def audit_app(app):
    with app.app_context():
        # Tạo sẵn 2 user cho kiểm thử audit
        user_a_id = register_user("user_a", "password-a")
        user_b_id = register_user("user_b", "password-b")
    return app, user_a_id, user_b_id


def test_user_has_updated_at(audit_app):
    app, user_a_id, _ = audit_app
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT created_at, updated_at FROM user WHERE id = ?", (user_a_id,)).fetchone()
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
        # Format UTC YYYY-MM-DD HH:MM:SS
        datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S")


def test_create_workspace_and_project_audit(audit_app):
    app, user_a_id, _ = audit_app
    with app.app_context():
        db = get_db()
        # Tạo workspace bởi user A
        cursor = db.execute(
            """
            INSERT INTO workspace (name, description, created_by, updated_by)
            VALUES (?, ?, ?, ?)
            """,
            ("Workspace 1", "Mô tả", user_a_id, user_a_id),
        )
        ws_id = cursor.lastrowid
        db.commit()

        ws = db.execute("SELECT * FROM workspace WHERE id = ?", (ws_id,)).fetchone()
        assert ws["created_by"] == user_a_id
        assert ws["updated_by"] == user_a_id
        assert ws["created_at"] is not None
        assert ws["updated_at"] is not None

        # Tạo project bởi user A
        cursor = db.execute(
            """
            INSERT INTO project (workspace_id, name, description, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ws_id, "Project 1", "Mô tả project", user_a_id, user_a_id),
        )
        proj_id = cursor.lastrowid
        db.commit()

        proj = db.execute("SELECT * FROM project WHERE id = ?", (proj_id,)).fetchone()
        assert proj["created_by"] == user_a_id
        assert proj["updated_by"] == user_a_id
        assert proj["created_at"] is not None
        assert proj["updated_at"] is not None


def test_update_project_audit(audit_app):
    app, user_a_id, user_b_id = audit_app
    with app.app_context():
        db = get_db()
        # Khởi tạo workspace và project với timestamp giả định trong quá khứ
        db.execute(
            """
            INSERT INTO workspace (id, name, created_by, updated_by, created_at, updated_at)
            VALUES (1, 'Workspace 1', ?, ?, '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            (user_a_id, user_a_id),
        )
        db.execute(
            """
            INSERT INTO project (id, workspace_id, name, created_by, updated_by, created_at, updated_at)
            VALUES (1, 1, 'Tên cũ', ?, ?, '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            (user_a_id, user_a_id),
        )
        db.commit()

        # User B sửa project: created_by giữ nguyên, updated_by đổi sang User B, updated_at = CURRENT_TIMESTAMP
        db.execute(
            """
            UPDATE project
            SET name = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE id = ?
            """,
            ("Tên mới", user_b_id, 1),
        )
        db.commit()

        proj = db.execute("SELECT * FROM project WHERE id = 1").fetchone()
        assert proj["name"] == "Tên mới"
        assert proj["created_by"] == user_a_id  # Giữ nguyên
        assert proj["updated_by"] == user_b_id  # Đổi sang user sửa
        assert proj["created_at"] == "2026-01-01 00:00:00"  # Không đổi
        assert proj["updated_at"] != "2026-01-01 00:00:00"  # Đã được cập nhật


def test_task_and_comment_audit(audit_app):
    app, user_a_id, user_b_id = audit_app
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO workspace (id, name) VALUES (1, 'WS')")
        db.execute("INSERT INTO workspace_member (workspace_id, user_id) VALUES (1, ?), (1, ?)", (user_a_id, user_b_id))
        db.execute("INSERT INTO project (id, workspace_id, name) VALUES (1, 1, 'Proj')")
        db.execute("INSERT INTO project_member (project_id, workspace_id, user_id) VALUES (1, 1, ?), (1, 1, ?)", (user_a_id, user_b_id))

        # Tạo task bởi user A
        db.execute(
            """
            INSERT INTO task (id, project_id, created_by, updated_by, title, created_at, updated_at)
            VALUES (1, 1, ?, ?, 'Task 1', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            (user_a_id, user_a_id),
        )
        # Tạo comment bởi user A
        db.execute(
            """
            INSERT INTO comment (id, task_id, author_id, updated_by, content, created_at, updated_at)
            VALUES (1, 1, ?, ?, 'Comment 1', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
            """,
            (user_a_id, user_a_id),
        )
        db.commit()

        # User B sửa task
        db.execute(
            """
            UPDATE task
            SET title = 'Task 1 updated', status = 'in_progress',
                updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE id = 1
            """,
            (user_b_id,),
        )
        # User B sửa comment
        db.execute(
            """
            UPDATE comment
            SET content = 'Comment 1 edited',
                updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE id = 1
            """,
            (user_b_id,),
        )
        db.commit()

        task = db.execute("SELECT * FROM task WHERE id = 1").fetchone()
        assert task["title"] == "Task 1 updated"
        assert task["created_by"] == user_a_id
        assert task["updated_by"] == user_b_id
        assert task["updated_at"] != "2026-01-01 00:00:00"

        comment = db.execute("SELECT * FROM comment WHERE id = 1").fetchone()
        assert comment["content"] == "Comment 1 edited"
        assert comment["author_id"] == user_a_id
        assert comment["updated_by"] == user_b_id
        assert comment["updated_at"] != "2026-01-01 00:00:00"


def test_audit_foreign_key_constraints(audit_app):
    app, user_a_id, _ = audit_app
    with app.app_context():
        db = get_db()
        # Thử insert created_by trỏ tới user_id không tồn tại (999) -> phải lỗi
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO workspace (name, created_by) VALUES ('Fail', 999)")
            db.commit()
        db.rollback()

        # Thử insert updated_by trỏ tới user_id không tồn tại (999) -> phải lỗi
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO workspace (name, updated_by) VALUES ('Fail', 999)")
            db.commit()
        db.rollback()


def test_delete_user_sets_audit_to_null(audit_app):
    app, user_a_id, user_b_id = audit_app
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO workspace (id, name, created_by, updated_by) VALUES (1, 'WS', ?, ?)", (user_a_id, user_b_id))
        db.execute("INSERT INTO workspace_member (workspace_id, user_id) VALUES (1, ?), (1, ?)", (user_a_id, user_b_id))
        db.execute("INSERT INTO project (id, workspace_id, name, created_by, updated_by) VALUES (1, 1, 'Proj', ?, ?)", (user_a_id, user_b_id))
        db.execute("INSERT INTO project_member (project_id, workspace_id, user_id) VALUES (1, 1, ?), (1, 1, ?)", (user_a_id, user_b_id))
        db.execute("INSERT INTO task (id, project_id, created_by, updated_by, title) VALUES (1, 1, ?, ?, 'Task')", (user_a_id, user_b_id))
        db.execute("INSERT INTO comment (id, task_id, author_id, updated_by, content) VALUES (1, 1, ?, ?, 'Comment')", (user_a_id, user_b_id))
        db.commit()

        # Xóa user B (người sửa gần nhất)
        db.execute("DELETE FROM user WHERE id = ?", (user_b_id,))
        db.commit()

        # updated_by chuyển thành NULL, created_by / author_id của user A vẫn nguyên
        ws = db.execute("SELECT created_by, updated_by FROM workspace WHERE id = 1").fetchone()
        assert ws["created_by"] == user_a_id
        assert ws["updated_by"] is None

        proj = db.execute("SELECT created_by, updated_by FROM project WHERE id = 1").fetchone()
        assert proj["created_by"] == user_a_id
        assert proj["updated_by"] is None

        task = db.execute("SELECT created_by, updated_by FROM task WHERE id = 1").fetchone()
        assert task["created_by"] == user_a_id
        assert task["updated_by"] is None

        comment = db.execute("SELECT author_id, updated_by FROM comment WHERE id = 1").fetchone()
        assert comment["author_id"] == user_a_id
        assert comment["updated_by"] is None

        # Không có vi phạm foreign key
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_audit_foreign_key_indexes(audit_app):
    app, _, _ = audit_app
    with app.app_context():
        db = get_db()
        indexes = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        # Kiểm tra đầy đủ các index cho cả created_by và updated_by
        assert "idx_workspace_creator" in indexes
        assert "idx_workspace_updater" in indexes
        assert "idx_project_creator" in indexes
        assert "idx_project_updater" in indexes
        assert "idx_task_creator" in indexes
        assert "idx_task_updater" in indexes
        assert "idx_comment_author" in indexes
        assert "idx_comment_updater" in indexes

