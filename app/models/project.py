from app.db import get_db


def insert_project(workspace_id, name, description, created_by):
    cursor = get_db().execute(
        """INSERT INTO project (workspace_id, name, description, created_by)
           VALUES (?, ?, ?, ?)""",
        (workspace_id, name, description, created_by),
    )
    return cursor.lastrowid


def get_project_for_member(project_id, user_id):
    return get_db().execute(
        """SELECT p.id, p.workspace_id, p.name, p.description,
                  p.created_by, p.created_at, p.updated_at, pm.role
           FROM project AS p
           JOIN project_member AS pm ON pm.project_id = p.id
           WHERE p.id = ? AND pm.user_id = ?""",
        (project_id, user_id),
    ).fetchone()


def get_project_by_id(project_id):
    return get_db().execute(
        """SELECT id, workspace_id, name, description,
                  created_by, created_at, updated_at
           FROM project WHERE id = ?""",
        (project_id,),
    ).fetchone()


def get_projects_for_workspace_member(workspace_id, user_id):
    """Trả về tất cả project trong workspace mà user là thành viên."""
    return get_db().execute(
        """SELECT p.id, p.workspace_id, p.name, p.description,
                  p.created_by, p.created_at, p.updated_at, pm.role
           FROM project AS p
           JOIN project_member AS pm ON pm.project_id = p.id
           WHERE p.workspace_id = ? AND pm.user_id = ?
           ORDER BY p.created_at DESC, p.id DESC""",
        (workspace_id, user_id),
    ).fetchall()


def update_project(project_id, name, description, updated_by):
    get_db().execute(
        """UPDATE project
           SET name = ?, description = ?,
               updated_by = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (name, description, updated_by, project_id),
    )


def delete_project(project_id):
    get_db().execute("DELETE FROM project WHERE id = ?", (project_id,))


# --- Project member queries ---

def insert_project_member(project_id, workspace_id, user_id, role):
    get_db().execute(
        """INSERT INTO project_member (project_id, workspace_id, user_id, role)
           VALUES (?, ?, ?, ?)""",
        (project_id, workspace_id, user_id, role),
    )


def get_project_member(project_id, user_id):
    return get_db().execute(
        """SELECT project_id, user_id, role, joined_at
           FROM project_member
           WHERE project_id = ? AND user_id = ?""",
        (project_id, user_id),
    ).fetchone()


def get_project_members(project_id):
    return get_db().execute(
        """SELECT u.id, u.username, u.created_at, pm.role, pm.joined_at
           FROM project_member AS pm
           JOIN user AS u ON u.id = pm.user_id
           WHERE pm.project_id = ?
           ORDER BY pm.joined_at ASC, u.id ASC""",
        (project_id,),
    ).fetchall()


def update_project_member_role(project_id, user_id, role):
    get_db().execute(
        """UPDATE project_member SET role = ?
           WHERE project_id = ? AND user_id = ?""",
        (role, project_id, user_id),
    )


def delete_project_member(project_id, user_id):
    get_db().execute(
        "DELETE FROM project_member WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    )


def count_project_owners(project_id):
    row = get_db().execute(
        "SELECT COUNT(*) AS cnt FROM project_member WHERE project_id = ? AND role = 'owner'",
        (project_id,),
    ).fetchone()
    return row["cnt"] if row else 0
