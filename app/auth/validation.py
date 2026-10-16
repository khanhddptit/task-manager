import re


class ValidationError(ValueError):
    def __init__(self, fields):
        super().__init__("Dữ liệu không hợp lệ.")
        self.fields = fields


def validate_credentials(data, *, registration=False):
    errors = {}
    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str):
        errors["username"] = "Tên đăng nhập phải là chuỗi ký tự."
    else:
        username = username.strip()
        minimum = 3 if registration else 1
        if not minimum <= len(username) <= 32:
            errors["username"] = f"Tên đăng nhập từ {minimum} đến 32 ký tự."
        elif registration and re.fullmatch(r"[A-Za-z0-9_.-]+", username) is None:
            errors["username"] = "Chỉ dùng chữ không dấu, số, dấu chấm, gạch dưới hoặc gạch ngang."

    if not isinstance(password, str):
        errors["password"] = "Mật khẩu phải là chuỗi ký tự."
    else:
        minimum = 8 if registration else 1
        if not minimum <= len(password) <= 128:
            errors["password"] = f"Mật khẩu từ {minimum} đến 128 ký tự."

    if registration:
        confirmation = data.get("confirm_password")
        if not isinstance(confirmation, str):
            errors["confirm_password"] = "Vui lòng xác nhận mật khẩu bằng chuỗi ký tự."
        elif confirmation != password:
            errors["confirm_password"] = "Mật khẩu xác nhận không khớp."

    if errors:
        raise ValidationError(errors)
    return username, password
