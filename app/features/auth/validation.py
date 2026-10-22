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


def _validate_email(value):
    if not isinstance(value, str):
        raise ValidationError({"email": "Email là bắt buộc và phải là chuỗi."})
    email = value.strip().lower()
    if len(email) > 254 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
        raise ValidationError({"email": "Email không hợp lệ."})
    return email


def _validate_display_name(value, field="display_name"):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({field: "Tên hiển thị không được để trống."})
    display_name = value.strip()
    if len(display_name) > 80:
        raise ValidationError({field: "Tên hiển thị không được vượt quá 80 ký tự."})
    return display_name


def validate_registration(data):
    try:
        username, password = validate_credentials(data, registration=True)
    except ValidationError as error:
        errors = dict(error.fields)
        if "email" not in data:
            errors["email"] = "Email là bắt buộc và phải là chuỗi."
        raise ValidationError(errors) from None
    email = _validate_email(data.get("email"))
    display_name = _validate_display_name(data.get("display_name", username))
    return username, password, display_name, email


def validate_profile_update(data, current_user):
    allowed = {"display_name", "email"}
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in set(data) - allowed
    }
    if not data:
        errors["profile"] = "Cần cung cấp ít nhất một trường cần cập nhật."
    display_name = current_user["display_name"] or current_user["username"]
    email = current_user["email"]
    try:
        if "display_name" in data:
            display_name = _validate_display_name(data["display_name"])
        if "email" in data:
            email = _validate_email(data["email"])
        elif not email:
            errors["email"] = "Email là bắt buộc để hoàn thiện hồ sơ."
    except ValidationError as error:
        errors.update(error.fields)
    if errors:
        raise ValidationError(errors)
    return display_name, email


def validate_google_profile(userinfo):
    errors = {}
    subject = userinfo.get("sub") if isinstance(userinfo, dict) else None
    if not isinstance(subject, str) or not subject.strip():
        errors["sub"] = "Google không trả về định danh hợp lệ."

    email_verified = userinfo.get("email_verified") if isinstance(userinfo, dict) else None
    if email_verified is not True:
        errors["email"] = "Cần dùng email Google đã được xác minh."

    try:
        email = _validate_email(userinfo.get("email") if isinstance(userinfo, dict) else None)
    except ValidationError as error:
        errors.update(error.fields)
        email = None

    display_name = None
    if email:
        name = userinfo.get("name") if isinstance(userinfo, dict) else None
        try:
            display_name = _validate_display_name(name or email.split("@", 1)[0])
        except ValidationError as error:
            errors.update(error.fields)

    if errors:
        raise ValidationError(errors)
    return subject.strip(), email, display_name


def validate_password_reset_request(data):
    allowed = {"email"}
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in set(data) - allowed
    }
    try:
        email = _validate_email(data.get("email"))
    except ValidationError as error:
        errors.update(error.fields)
    if errors:
        raise ValidationError(errors)
    return email


def validate_password_reset_complete(data):
    allowed = {"token", "new_password", "confirm_password"}
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in set(data) - allowed
    }
    token = data.get("token")
    if not isinstance(token, str) or not 1 <= len(token) <= 200:
        errors["token"] = "Token đặt lại mật khẩu không hợp lệ."
    new_password = data.get("new_password")
    confirmation = data.get("confirm_password")
    if not isinstance(new_password, str) or not 8 <= len(new_password) <= 128:
        errors["new_password"] = "Mật khẩu mới phải từ 8 đến 128 ký tự."
    if not isinstance(confirmation, str):
        errors["confirm_password"] = "Vui lòng xác nhận mật khẩu mới."
    elif confirmation != new_password:
        errors["confirm_password"] = "Mật khẩu xác nhận không khớp."
    if errors:
        raise ValidationError(errors)
    return token, new_password


def validate_password_change(data, require_current_password=True):
    allowed = {"current_password", "new_password", "confirm_password"}
    errors = {
        field: "Trường này không được hỗ trợ."
        for field in set(data) - allowed
    }
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    confirmation = data.get("confirm_password")
    if require_current_password:
        if not isinstance(current_password, str) or not 1 <= len(current_password) <= 128:
            errors["current_password"] = "Mật khẩu hiện tại phải từ 1 đến 128 ký tự."
    elif current_password in (None, ""):
        current_password = None
    elif not isinstance(current_password, str) or len(current_password) > 128:
        errors["current_password"] = "Mật khẩu hiện tại không hợp lệ."
    if not isinstance(new_password, str) or not 8 <= len(new_password) <= 128:
        errors["new_password"] = "Mật khẩu mới phải từ 8 đến 128 ký tự."
    if not isinstance(confirmation, str):
        errors["confirm_password"] = "Vui lòng xác nhận mật khẩu mới."
    elif confirmation != new_password:
        errors["confirm_password"] = "Mật khẩu xác nhận không khớp."
    if errors:
        raise ValidationError(errors)
    return current_password, new_password
