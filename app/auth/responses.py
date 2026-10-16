from flask import jsonify


def api_error(code, message, status, fields=None):
    error = {"code": code, "message": message}
    if fields is not None:
        error["fields"] = fields
    return jsonify(error=error), status
