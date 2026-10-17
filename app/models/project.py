from app.db import get_db


def insert_project(workspace_id, name, description, created_by):
    cursor = get_db().execute(
        """INSERT INTO project (workspace_id, name, description, created_by)
           VALUES (?, ?, ?, ?)""",
        (workspace_id, name, description, created_by),
    )
    return cursor.lastrowid


def get_project_by_id(project_id):
    return get_db().execute(
        """SELECT id, workspace_id, name, description, created_by,
                  created_at, updated_at
           FROM project
           WHERE id = ?""",
        (project_id,),
    ).fetchone()
