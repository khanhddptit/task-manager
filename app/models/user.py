from app.db import get_db


def get_user_by_id(user_id):
    return get_db().execute(
        "SELECT id, username, created_at FROM user WHERE id = ?", (user_id,)
    ).fetchone()


def get_user_by_username(username):
    return get_db().execute(
        "SELECT id, username, password_hash FROM user WHERE username = ?",
        (username,),
    ).fetchone()


def create_user(username, password_hash):
    db = get_db()
    with db:
        cursor = db.execute(
            "INSERT INTO user (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
    return cursor.lastrowid
