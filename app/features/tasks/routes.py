from datetime import date

from flask import g, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.features.auth.decorators import login_required
from app.features.auth.responses import api_error
from app.features.auth.validation import ValidationError
from app.services.my_tasks_service import list_my_tasks
from app.services.task_service import (
    InsufficientRoleError,
    InvalidAssigneeError,
    InvalidTaskDataError,
    NotAProjectMemberError,
    ProjectNotFoundError,
    TaskNotFoundError,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    reorder_tasks,
    update_task,
)
from app.features.tasks import bp, page_bp


TASK_FIELDS = {
    "title", "description", "status", "priority", "assignee_id", "sprint_id",
    "due_date", "position",
}
TASK_STATUSES = {"todo", "in_progress", "review", "done"}
TASK_PRIORITIES = {"low", "medium", "high"}
MAX_ID = 9223372036854775807


def read_json_object():
    if not request.is_json:
        raise UnsupportedMediaType()
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest()
    return data


def validate_task_payload(data, partial=False):
    errors = {}
    allowed_fields = TASK_FIELDS if partial else TASK_FIELDS - {"position"}
    unknown_fields = set(data) - allowed_fields
    if unknown_fields:
        errors.update({
            field: "Trường này không được hỗ trợ."
            for field in unknown_fields
        })
    if not partial and "title" not in data:
        errors["title"] = "Tiêu đề task là bắt buộc."
    if partial and not (set(data) & TASK_FIELDS):
        errors["task"] = "Cần cung cấp ít nhất một trường cần cập nhật."

    values = {}
    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            errors["title"] = "Tiêu đề task phải là chuỗi không được để trống."
        elif len(title.strip()) > 255:
            errors["title"] = "Tiêu đề task không được vượt quá 255 ký tự."
        else:
            values["title"] = title.strip()

    if "description" in data:
        description = data["description"]
        if not isinstance(description, str):
            errors["description"] = "Mô tả task phải là chuỗi ký tự."
        else:
            values["description"] = description.strip()

    if "status" in data:
        status = data["status"]
        if not isinstance(status, str) or status not in TASK_STATUSES:
            errors["status"] = "Trạng thái task không hợp lệ."
        else:
            values["status"] = status

    if "priority" in data:
        priority = data["priority"]
        if not isinstance(priority, str) or priority not in TASK_PRIORITIES:
            errors["priority"] = "Mức ưu tiên task không hợp lệ."
        else:
            values["priority"] = priority

    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None and (
            type(assignee_id) is not int
            or not 0 < assignee_id <= MAX_ID
        ):
            errors["assignee_id"] = (
                "ID người được giao phải là số nguyên dương hoặc null."
            )
        else:
            values["assignee_id"] = assignee_id

    if "position" in data:
        position = data["position"]
        if type(position) is not int or not 0 <= position <= MAX_ID:
            errors["position"] = "Vị trí task phải là số nguyên không âm."
        else:
            values["position"] = position

    if "sprint_id" in data:
        sprint_id = data["sprint_id"]
        if sprint_id is not None and (
            type(sprint_id) is not int or not 0 < sprint_id <= MAX_ID
        ):
            errors["sprint_id"] = "ID Sprint phải là số nguyên dương hoặc null."
        else:
            values["sprint_id"] = sprint_id

    if "due_date" in data:
        due_date = data["due_date"]
        if due_date is None:
            values["due_date"] = None
        elif isinstance(due_date, str):
            due_date = due_date.strip()
            try:
                parsed_date = date.fromisoformat(due_date)
            except ValueError:
                errors["due_date"] = "Hạn hoàn thành phải có định dạng YYYY-MM-DD."
            else:
                if parsed_date.isoformat() != due_date:
                    errors["due_date"] = (
                        "Hạn hoàn thành phải có định dạng YYYY-MM-DD."
                    )
                else:
                    values["due_date"] = due_date
        else:
            errors["due_date"] = (
                "Hạn hoàn thành phải là ngày YYYY-MM-DD hoặc null."
            )

    if errors:
        raise ValidationError(errors)
    return values


def validate_task_filters():
    errors = {
        field: "Tham số này không được hỗ trợ."
        for field in set(request.args) - {"status", "assignee_id"}
    }
    filters = {}
    if "status" in request.args:
        status = request.args["status"]
        if status not in TASK_STATUSES:
            errors["status"] = "Trạng thái task không hợp lệ."
        else:
            filters["status"] = status
    if "assignee_id" in request.args:
        raw_assignee_id = request.args["assignee_id"]
        normalized_id = raw_assignee_id.lstrip("0")
        if (
            not raw_assignee_id.isdecimal()
            or not normalized_id
            or len(normalized_id) > 19
            or int(normalized_id) > MAX_ID
        ):
            errors["assignee_id"] = "ID người được giao phải là số nguyên dương."
        else:
            filters["assignee_id"] = int(normalized_id)
    if errors:
        raise ValidationError(errors)
    return filters


@bp.errorhandler(ValidationError)
def validation_error(error):
    return api_error("validation_error", str(error), 400, error.fields)


@bp.errorhandler(ProjectNotFoundError)
def project_not_found(error):
    return api_error("project_not_found", str(error), 404)


@bp.errorhandler(TaskNotFoundError)
def task_not_found(error):
    return api_error("task_not_found", str(error), 404)


@bp.errorhandler(NotAProjectMemberError)
def not_project_member(error):
    return api_error("permission_denied", str(error), 403)


@bp.errorhandler(InsufficientRoleError)
def insufficient_role(error):
    return api_error("permission_denied", str(error), 403)


@bp.errorhandler(InvalidTaskDataError)
def invalid_task_data(error):
    return api_error("validation_error", str(error), 400)


@bp.errorhandler(InvalidAssigneeError)
def invalid_assignee(error):
    return api_error("invalid_assignee", str(error), 422)


@bp.get("")
@login_required
def index(workspace_id, project_id):
    filters = validate_task_filters()
    tasks = list_tasks(
        workspace_id, project_id, g.user["id"], **filters
    )
    return jsonify(tasks=[dict(task) for task in tasks]), 200


@bp.post("/reorder")
@login_required
def reorder(workspace_id, project_id):
    data = read_json_object()
    if set(data) != {"columns"} or not isinstance(data["columns"], dict):
        raise ValidationError({"columns": "Cần cung cấp thứ tự task theo từng cột."})
    tasks = reorder_tasks(
        workspace_id, project_id, g.user["id"], data["columns"]
    )
    return jsonify(tasks=[dict(task) for task in tasks]), 200


@bp.post("")
@login_required
def create(workspace_id, project_id):
    values = validate_task_payload(read_json_object())
    task = create_task(
        workspace_id,
        project_id,
        g.user["id"],
        values["title"],
        description=values.get("description", ""),
        assignee_id=values.get("assignee_id"),
        status=values.get("status", "todo"),
        due_date=values.get("due_date"),
        priority=values.get("priority", "medium"),
        sprint_id=values.get("sprint_id"),
    )
    return jsonify(task=dict(task)), 201


@bp.get("/<int:task_id>")
@login_required
def detail(workspace_id, project_id, task_id):
    task = get_task(workspace_id, project_id, g.user["id"], task_id)
    return jsonify(task=dict(task)), 200


@bp.patch("/<int:task_id>")
@login_required
def update(workspace_id, project_id, task_id):
    values = validate_task_payload(read_json_object(), partial=True)
    task = update_task(
        workspace_id, project_id, g.user["id"], task_id, **values
    )
    return jsonify(task=dict(task)), 200


@bp.delete("/<int:task_id>")
@login_required
def delete(workspace_id, project_id, task_id):
    delete_task(workspace_id, project_id, g.user["id"], task_id)
    return jsonify(message="Task đã được xóa."), 200


@page_bp.after_request
def no_store_my_tasks_api(response):
    if request.path == "/tasks/api/my":
        response.headers["Cache-Control"] = "no-store"
    return response


@page_bp.get("/my")
@login_required
def my_tasks_page():
    return render_template("tasks/my.html")


@page_bp.get("/api/my")
@login_required
def my_tasks_api():
    avatar_url = "/auth/me/avatar" if g.user["avatar_path"] else None
    response = jsonify(tasks=list_my_tasks(g.user["id"], avatar_url))
    response.headers["Cache-Control"] = "no-store"
    return response, 200
