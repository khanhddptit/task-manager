from app.db import get_db


def insert_workspace(name, description, created_by):
    cursor = get_db().execute(
        """INSERT INTO workspace (name, description, created_by)
           VALUES (?, ?, ?)""",
        (name, description, created_by),
    )
    return cursor.lastrowid


def insert_workspace_member(workspace_id, user_id, role):
    get_db().execute(
        """INSERT INTO workspace_member (workspace_id, user_id, role)
           VALUES (?, ?, ?)""",
        (workspace_id, user_id, role),
    )


def get_workspace_for_member(workspace_id, user_id):
    return get_db().execute(
        """SELECT w.id, w.name, w.description, w.created_by, w.created_at,
                  w.updated_at, wm.role
           FROM workspace AS w
           JOIN workspace_member AS wm ON wm.workspace_id = w.id
           WHERE w.id = ? AND wm.user_id = ?""",
        (workspace_id, user_id),
    ).fetchone()
