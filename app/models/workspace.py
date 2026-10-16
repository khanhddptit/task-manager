from app.db import get_db


def insert_workspace(name, description):
    cursor = get_db().execute(
        "INSERT INTO workspace (name, description) VALUES (?, ?)",
        (name, description),
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
        """SELECT w.id, w.name, w.description, w.created_at, w.updated_at, wm.role
           FROM workspace AS w
           JOIN workspace_member AS wm ON wm.workspace_id = w.id
           WHERE w.id = ? AND wm.user_id = ?""",
        (workspace_id, user_id),
    ).fetchone()


def get_workspaces_for_user(user_id):
    return get_db().execute(
        """SELECT w.id, w.name, w.description, w.created_at, w.updated_at, wm.role
           FROM workspace AS w
           JOIN workspace_member AS wm ON wm.workspace_id = w.id
           WHERE wm.user_id = ?
           ORDER BY w.created_at DESC, w.id DESC""",
        (user_id,),
    ).fetchall()
