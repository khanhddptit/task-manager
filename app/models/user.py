from app.db import get_db


def get_user_by_id(user_id):
    return get_db().execute(
        """SELECT u.id, u.username, u.display_name, u.email, u.avatar_path,
                  u.auth_version, u.password_login_enabled, u.created_at,
                  EXISTS (
                      SELECT 1 FROM oauth_identity AS oi
                      WHERE oi.user_id = u.id AND oi.provider = 'google'
                  ) AS google_connected
           FROM user AS u WHERE u.id = ?""",
        (user_id,),
    ).fetchone()


def get_user_for_auth(user_id):
    return get_db().execute(
        """SELECT id, username, password_hash, auth_version,
                  password_login_enabled FROM user WHERE id = ?""",
        (user_id,),
    ).fetchone()


def get_user_by_username(username):
    return get_db().execute(
        """SELECT id, username, password_hash, auth_version,
                  password_login_enabled
           FROM user WHERE username = ?""",
        (username,),
    ).fetchone()


def get_user_by_email(email):
    return get_db().execute(
        "SELECT id, email FROM user WHERE email = ? COLLATE NOCASE",
        (email,),
    ).fetchone()


def create_user(
    username, password_hash, display_name=None, email=None,
    password_login_enabled=True,
):
    db = get_db()
    with db:
        cursor = db.execute(
            """INSERT INTO user
                   (username, display_name, email, password_hash,
                    password_login_enabled)
               VALUES (?, ?, ?, ?, ?)""",
            (
                username,
                display_name or username,
                email,
                password_hash,
                int(password_login_enabled),
            ),
        )
    return cursor.lastrowid


def create_google_user(username, password_hash, display_name, email):
    cursor = get_db().execute(
        """INSERT INTO user
               (username, display_name, email, password_hash, password_login_enabled)
           VALUES (?, ?, ?, ?, 0)""",
        (username, display_name, email, password_hash),
    )
    return cursor.lastrowid


def get_oauth_identity(provider, subject):
    return get_db().execute(
        """SELECT id, user_id, provider, subject, email
           FROM oauth_identity WHERE provider = ? AND subject = ?""",
        (provider, subject),
    ).fetchone()


def get_user_oauth_identity(user_id, provider):
    return get_db().execute(
        """SELECT id, user_id, provider, subject, email
           FROM oauth_identity WHERE user_id = ? AND provider = ?""",
        (user_id, provider),
    ).fetchone()


def insert_oauth_identity(user_id, provider, subject, email):
    get_db().execute(
        """INSERT INTO oauth_identity (user_id, provider, subject, email)
           VALUES (?, ?, ?, ?)""",
        (user_id, provider, subject, email),
    )


def update_user_profile(user_id, display_name, email):
    return get_db().execute(
        """UPDATE user
           SET display_name = ?, email = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (display_name, email, user_id),
    ).rowcount


def update_user_password(user_id, password_hash):
    get_db().execute(
        """UPDATE user
           SET password_hash = ?, password_login_enabled = 1,
               auth_version = auth_version + 1, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (password_hash, user_id),
    )
    return get_user_for_auth(user_id)["auth_version"]


def update_user_avatar(user_id, avatar_path):
    db = get_db()
    old_path = db.execute(
        "SELECT avatar_path FROM user WHERE id = ?", (user_id,)
    ).fetchone()["avatar_path"]
    db.execute(
        "UPDATE user SET avatar_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (avatar_path, user_id),
    )
    return old_path
