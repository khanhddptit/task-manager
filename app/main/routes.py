from flask import Blueprint, g, redirect, render_template, url_for


bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    if g.user is not None:
        return redirect(url_for("tasks.my_tasks_page"))
    return redirect(url_for("main.login"))


@bp.get("/login")
def login():
    return render_template("login.html")


@bp.get("/register")
def register():
    return render_template("register.html")


@bp.get("/password-reset")
def password_reset():
    from flask import make_response

    response = make_response(render_template("password_reset.html"))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@bp.get("/settings")
def user_settings():
    return render_template("settings.html")


@bp.get("/sprints/")
def sprints():
    return render_template("sprints/index.html")


@bp.get("/sprints/progress")
def sprint_progress():
    return render_template("sprints/progress.html")


@bp.get("/members")
def member_directory():
    from flask import url_for

    return render_template(
        "members/directory.html",
        workspaces_url=url_for("workspaces.index"),
    )


@bp.get("/workspaces/<int:workspace_id>/members/page")
def workspace_members_page(workspace_id):
    from flask import url_for

    return render_template(
        "members/index.html",
        scope="workspace",
        scope_name="Workspace",
        members_url=url_for("workspaces.members", workspace_id=workspace_id),
        invitations_url=url_for(
            "workspaces.member_invitations", workspace_id=workspace_id
        ),
        invitation_collection_url=url_for(
            "workspaces.create_member_invite", workspace_id=workspace_id
        ),
        workspace_id=workspace_id,
        project_id="",
    )


@bp.get("/workspaces/<int:workspace_id>/projects/<int:project_id>/members/page")
def project_members_page(workspace_id, project_id):
    from flask import url_for

    return render_template(
        "members/index.html",
        scope="project",
        scope_name="Project",
        members_url=url_for(
            "projects.members", workspace_id=workspace_id, project_id=project_id
        ),
        invitations_url=url_for(
            "projects.member_invitations",
            workspace_id=workspace_id,
            project_id=project_id,
        ),
        invitation_collection_url=url_for(
            "projects.create_member_invite",
            workspace_id=workspace_id,
            project_id=project_id,
        ),
        workspace_id=workspace_id,
        project_id=project_id,
    )


@bp.get("/invite/accept")
def invitation_accept_page():
    from flask import make_response

    response = make_response(render_template("members/accept.html"))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
