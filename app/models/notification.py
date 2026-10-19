import json

from app.db import get_db


def insert_notification(
    recipient_id, actor_id, event_type, title, message, metadata, link_path
):
    cursor = get_db().execute(
        """INSERT INTO notification
               (recipient_id, actor_id, event_type, title, message, metadata, link_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            recipient_id,
            actor_id,
            event_type,
            title,
            message,
            json.dumps(metadata, separators=(",", ":"), sort_keys=True),
            link_path,
        ),
    )
    return cursor.lastrowid


def list_notifications(recipient_id, limit):
    rows = get_db().execute(
        """SELECT id, actor_id, event_type, title, message, metadata,
                  link_path, read_at, created_at
           FROM notification
           WHERE recipient_id = ?
           ORDER BY created_at DESC, id DESC
           LIMIT ?""",
        (recipient_id, limit),
    ).fetchall()
    return [
        {
            **dict(row),
            "metadata": json.loads(row["metadata"]),
            "is_read": row["read_at"] is not None,
        }
        for row in rows
    ]


def count_unread_notifications(recipient_id):
    row = get_db().execute(
        """SELECT COUNT(*) AS unread_count FROM notification
           WHERE recipient_id = ? AND read_at IS NULL""",
        (recipient_id,),
    ).fetchone()
    return row["unread_count"]


def get_notification_for_recipient(notification_id, recipient_id):
    return get_db().execute(
        """SELECT id, actor_id, event_type, title, message, metadata,
                  link_path, read_at, created_at
           FROM notification
           WHERE id = ? AND recipient_id = ?""",
        (notification_id, recipient_id),
    ).fetchone()


def mark_notification_read(notification_id, recipient_id):
    get_db().execute(
        """UPDATE notification SET read_at = CURRENT_TIMESTAMP
           WHERE id = ? AND recipient_id = ? AND read_at IS NULL""",
        (notification_id, recipient_id),
    )
    return get_notification_for_recipient(notification_id, recipient_id)


def mark_all_notifications_read(recipient_id):
    cursor = get_db().execute(
        """UPDATE notification SET read_at = CURRENT_TIMESTAMP
           WHERE recipient_id = ? AND read_at IS NULL""",
        (recipient_id,),
    )
    return cursor.rowcount


def clear_read_notifications(recipient_id):
    cursor = get_db().execute(
        """DELETE FROM notification
           WHERE recipient_id = ? AND read_at IS NOT NULL""",
        (recipient_id,),
    )
    return cursor.rowcount


def get_project_notification_recipients(project_id):
    rows = get_db().execute(
        """SELECT user_id FROM project_member WHERE project_id = ?
           UNION
           SELECT wm.user_id FROM workspace_member AS wm
           JOIN project AS p ON p.workspace_id = wm.workspace_id
           WHERE p.id = ? AND wm.role = 'owner'""",
        (project_id, project_id),
    ).fetchall()
    return {row["user_id"] for row in rows}


def get_task_notification_context(task_id):
    return get_db().execute(
        """SELECT t.id, t.project_id, t.created_by, t.assignee_id, t.title,
                  p.workspace_id
           FROM task AS t
           JOIN project AS p ON p.id = t.project_id
           WHERE t.id = ?""",
        (task_id,),
    ).fetchone()


def get_project_mention_members(project_id, usernames):
    if not usernames:
        return []
    placeholders = ", ".join("?" for _ in usernames)
    return get_db().execute(
        f"""SELECT u.id, u.username
            FROM project_member AS pm
            JOIN user AS u ON u.id = pm.user_id
            WHERE pm.project_id = ?
              AND u.username COLLATE NOCASE IN ({placeholders})
            ORDER BY u.id""",
        (project_id, *usernames),
    ).fetchall()


def get_username(user_id):
    row = get_db().execute(
        "SELECT username FROM user WHERE id = ?", (user_id,)
    ).fetchone()
    return row["username"] if row is not None else None
