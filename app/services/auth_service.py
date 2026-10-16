import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from app.models.user import create_user, get_user_by_username


class UsernameTakenError(ValueError):
    pass


def register_user(username, password):
    password_hash = generate_password_hash(password)
    try:
        return create_user(username, password_hash)
    except sqlite3.IntegrityError:
        if get_user_by_username(username) is not None:
            raise UsernameTakenError("Tên đăng nhập đã được sử dụng.") from None
        raise


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if user is None:
        # Spend password-hashing work even when the username does not exist.
        generate_password_hash(password)
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user
