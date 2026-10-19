from app.db import get_db


def create_member_invitation(
    workspace_id, project_id, email, token_hash, expires_at, created_by
):
    cursor = get_db().execute(
        """INSERT INTO member_invitation
               (workspace_id, project_id, email, token_hash, expires_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (workspace_id, project_id, email, token_hash, expires_at, created_by),
    )
    return cursor.lastrowid


def get_member_invitation_by_hash(token_hash):
    return get_db().execute(
        """SELECT i.id, i.workspace_id, i.project_id, i.email, i.role,
                  i.expires_at, i.accepted_at, i.revoked_at,
                  w.name AS workspace_name, p.name AS project_name
           FROM member_invitation AS i
           JOIN workspace AS w ON w.id = i.workspace_id
           LEFT JOIN project AS p ON p.id = i.project_id
           WHERE i.token_hash = ?""",
        (token_hash,),
    ).fetchone()


def has_workspace_member_email(workspace_id, email):
    return get_db().execute(
        """SELECT 1 FROM workspace_member AS wm
           JOIN user AS u ON u.id = wm.user_id
           WHERE wm.workspace_id = ? AND lower(u.email) = ? LIMIT 1""",
        (workspace_id, email),
    ).fetchone() is not None


def has_project_member_email(project_id, email):
    return get_db().execute(
        """SELECT 1 FROM project AS p
           JOIN workspace_member AS wm ON wm.workspace_id = p.workspace_id
           JOIN user AS u ON u.id = wm.user_id
           LEFT JOIN project_member AS pm
             ON pm.project_id = p.id AND pm.user_id = wm.user_id
           WHERE p.id = ? AND lower(u.email) = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)
           LIMIT 1""",
        (project_id, email),
    ).fetchone() is not None


def get_pending_invitation(workspace_id, project_id, email):
    if project_id is None:
        project_clause = "project_id IS NULL"
        parameters = (workspace_id, email)
    else:
        project_clause = "project_id = ?"
        parameters = (workspace_id, project_id, email)
    return get_db().execute(
        f"""SELECT id FROM member_invitation
            WHERE workspace_id = ? AND {project_clause} AND lower(email) = ?
              AND accepted_at IS NULL AND revoked_at IS NULL
              AND expires_at > CURRENT_TIMESTAMP
            LIMIT 1""",
        parameters,
    ).fetchone()


def list_pending_member_invitations(workspace_id, project_id):
    if project_id is None:
        project_clause = "project_id IS NULL"
        parameters = (workspace_id,)
    else:
        project_clause = "project_id = ?"
        parameters = (workspace_id, project_id)
    return get_db().execute(
        f"""SELECT id, email, role, expires_at, created_at
            FROM member_invitation
            WHERE workspace_id = ? AND {project_clause}
              AND accepted_at IS NULL AND revoked_at IS NULL
              AND expires_at > CURRENT_TIMESTAMP
            ORDER BY created_at DESC, id DESC""",
        parameters,
    ).fetchall()


def get_pending_member_invitation_for_resend(
    invitation_id, workspace_id, project_id
):
    if project_id is None:
        project_clause = "project_id IS NULL"
        parameters = (workspace_id, invitation_id)
    else:
        project_clause = "project_id = ?"
        parameters = (workspace_id, project_id, invitation_id)
    return get_db().execute(
        f"""SELECT id, email FROM member_invitation
            WHERE workspace_id = ? AND {project_clause} AND id = ?
              AND accepted_at IS NULL AND revoked_at IS NULL
              AND expires_at > CURRENT_TIMESTAMP""",
        parameters,
    ).fetchone()


def revoke_member_invitation(invitation_id, workspace_id, project_id):
    if project_id is None:
        project_clause = "project_id IS NULL"
        parameters = (workspace_id, invitation_id)
    else:
        project_clause = "project_id = ?"
        parameters = (workspace_id, project_id, invitation_id)
    return get_db().execute(
        f"""UPDATE member_invitation
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE workspace_id = ? AND {project_clause} AND id = ?
              AND accepted_at IS NULL AND revoked_at IS NULL""",
        parameters,
    ).rowcount


def accept_member_invitation(invitation_id, user_id):
    return get_db().execute(
        """UPDATE member_invitation
           SET accepted_at = CURRENT_TIMESTAMP, accepted_user_id = ?
           WHERE id = ? AND accepted_at IS NULL AND revoked_at IS NULL
             AND expires_at > CURRENT_TIMESTAMP""",
        (user_id, invitation_id),
    ).rowcount
