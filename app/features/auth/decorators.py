from functools import wraps

from flask import g

from app.features.auth.responses import api_error


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return api_error("authentication_required", "Vui lòng đăng nhập để tiếp tục.", 401)
        return view(*args, **kwargs)

    return wrapped_view
