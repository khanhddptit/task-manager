from app.core.db import get_db


def check_task_hierarchy(workspace_id, project_id, task_id):
    """
    Kiểm tra tính toàn vẹn quan hệ phân cấp:
    task thuộc project, project thuộc workspace.
    Trả về dòng task kèm project_id và workspace_id nếu hợp lệ, ngược lại None.
    """
    db = get_db()
    return db.execute(
        """
        SELECT t.id AS task_id, p.id AS project_id, p.workspace_id
        FROM task t
        JOIN project p ON t.project_id = p.id
        WHERE t.id = ? AND p.id = ? AND p.workspace_id = ?
        """,
        (task_id, project_id, workspace_id),
    ).fetchone()


def get_user_permissions(user_id, workspace_id, project_id):
    """
    Lấy thông tin quyền hạn của người dùng:
    - is_workspace_owner: True nếu user là owner của workspace.
    - project_role: vai trò trong project ('admin', 'member') hoặc None nếu không thuộc project.
    """
    db = get_db()
    ws_member = db.execute(
        """
        SELECT role FROM workspace_member
        WHERE workspace_id = ? AND user_id = ?
        """,
        (workspace_id, user_id),
    ).fetchone()
    is_workspace_owner = ws_member is not None and ws_member["role"] == "owner"

    proj_member = db.execute(
        """
        SELECT role FROM project_member
        WHERE project_id = ? AND workspace_id = ? AND user_id = ?
        """,
        (project_id, workspace_id, user_id),
    ).fetchone()
    project_role = proj_member["role"] if proj_member is not None else None

    return {
        "is_workspace_owner": is_workspace_owner,
        "project_role": project_role,
    }


def list_comments_by_task(task_id):
    """
    Lấy danh sách bình luận theo task_id, LEFT JOIN user để bảo toàn lịch sử
    ngay cả khi tác giả đã bị xóa (author_id = NULL).
    Sắp xếp theo created_at ASC, id ASC để thứ tự luôn ổn định.
    """
    db = get_db()
    return db.execute(
        """
        SELECT
            c.id,
            c.task_id,
            c.author_id,
            u.username AS author_username,
            c.content,
            c.created_at,
            c.updated_at,
            c.updated_by
        FROM comment c
        LEFT JOIN user u ON c.author_id = u.id
        WHERE c.task_id = ?
        ORDER BY c.created_at ASC, c.id ASC
        """,
        (task_id,),
    ).fetchall()


def get_comment_by_id(comment_id):
    """
    Lấy chi tiết một bình luận kèm thông tin task, project và workspace để xác thực quan hệ.
    """
    db = get_db()
    return db.execute(
        """
        SELECT
            c.id,
            c.task_id,
            c.author_id,
            u.username AS author_username,
            c.content,
            c.created_at,
            c.updated_at,
            c.updated_by,
            t.project_id,
            p.workspace_id
        FROM comment c
        LEFT JOIN user u ON c.author_id = u.id
        JOIN task t ON c.task_id = t.id
        JOIN project p ON t.project_id = p.id
        WHERE c.id = ?
        """,
        (comment_id,),
    ).fetchone()


def insert_comment(task_id, author_id, content):
    """
    Tạo comment mới với audit timestamps và người tạo.
    """
    cursor = get_db().execute(
        """
        INSERT INTO comment (task_id, author_id, content, created_at, updated_at, updated_by)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """,
        (task_id, author_id, content, author_id),
    )
    return cursor.lastrowid


def update_comment(comment_id, content, updated_by):
    """
    Cập nhật nội dung comment và thông tin audit updated_at, updated_by.
    """
    get_db().execute(
        """
        UPDATE comment
        SET content = ?,
            updated_at = CURRENT_TIMESTAMP,
            updated_by = ?
        WHERE id = ?
        """,
        (content, updated_by, comment_id),
    )


def delete_comment(comment_id):
    """
    Xóa comment theo ID.
    """
    get_db().execute("DELETE FROM comment WHERE id = ?", (comment_id,))
