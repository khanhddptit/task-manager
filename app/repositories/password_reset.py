from app.core.db import get_db


def find_password_reset_user(email):
    return get_db().execute(
        """SELECT id, email FROM user
           WHERE email = ? COLLATE NOCASE AND password_login_enabled = 1""",
        (email,),
    ).fetchone()


def delete_active_password_resets(user_id):
    get_db().execute(
        "DELETE FROM password_reset_token WHERE user_id = ? AND consumed_at IS NULL",
        (user_id,),
    )


def create_password_reset(user_id, token_hash, expires_at):
    get_db().execute(
        """INSERT INTO password_reset_token (user_id, token_hash, expires_at)
           VALUES (?, ?, ?)""",
        (user_id, token_hash, expires_at),
    )


def consume_password_reset(token_hash, now):
    db = get_db()
    updated = db.execute(
        """UPDATE password_reset_token SET consumed_at = ?
           WHERE token_hash = ? AND consumed_at IS NULL AND expires_at > ?""",
        (now, token_hash, now),
    )
    if updated.rowcount != 1:
        return None
    return db.execute(
        "SELECT user_id FROM password_reset_token WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
