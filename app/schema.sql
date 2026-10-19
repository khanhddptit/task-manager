CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE CHECK (length(trim(username)) > 0),
    display_name TEXT NOT NULL DEFAULT '',
    email TEXT,
    avatar_path TEXT,
    auth_version INTEGER NOT NULL DEFAULT 0 CHECK (auth_version >= 0),
    password_login_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (password_login_enabled IN (0, 1)),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oauth_identity (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL CHECK (provider = 'google'),
    subject TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, subject),
    UNIQUE (user_id, provider),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT NOT NULL DEFAULT '',
    created_by INTEGER,
    updated_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS workspace_member (
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id),
    FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT NOT NULL DEFAULT '',
    created_by INTEGER,
    updated_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, workspace_id),
    FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS project_member (
    project_id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id),
    -- Composite keys prevent membership in a project from another workspace.
    FOREIGN KEY (project_id, workspace_id)
        REFERENCES project (id, workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, user_id)
        REFERENCES workspace_member (workspace_id, user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member_invitation (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    project_id INTEGER,
    email TEXT NOT NULL COLLATE NOCASE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role = 'member'),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TEXT,
    accepted_user_id INTEGER,
    revoked_at TEXT,
    CHECK ((project_id IS NULL) OR (project_id > 0)),
    FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, workspace_id)
        REFERENCES project (id, workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (accepted_user_id) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sprint (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    goal TEXT NOT NULL DEFAULT '',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'active', 'completed')),
    created_by INTEGER,
    updated_by INTEGER,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, project_id),
    UNIQUE (project_id, name),
    CHECK (end_date >= start_date),
    FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    created_by INTEGER,
    assignee_id INTEGER,
    updated_by INTEGER,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'in_progress', 'review', 'done')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    sprint_id INTEGER,
    position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
    due_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL,
    -- Unassign or reassign tasks before removing an assigned member.
    FOREIGN KEY (project_id, assignee_id)
        REFERENCES project_member (project_id, user_id) ON DELETE NO ACTION,
    FOREIGN KEY (sprint_id, project_id)
        REFERENCES sprint (id, project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS sprint_task_history (
    id INTEGER PRIMARY KEY,
    sprint_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('added', 'status_changed', 'removed')),
    status TEXT NOT NULL
        CHECK (status IN ('todo', 'in_progress', 'review', 'done')),
    changed_by INTEGER,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sprint_id) REFERENCES sprint (id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task (id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS password_reset_token (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consumed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_reset_attempt (
    id INTEGER PRIMARY KEY,
    email_hash TEXT NOT NULL,
    ip_hash TEXT NOT NULL,
    requested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY,
    recipient_id INTEGER NOT NULL,
    actor_id INTEGER,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'task_assigned', 'task_reassigned', 'task_status_changed',
        'task_commented', 'task_mentioned'
    )),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    message TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata)),
    link_path TEXT NOT NULL CHECK (
        substr(link_path, 1, 12) = '/workspaces/'
        AND instr(link_path, '//') = 0
        AND instr(link_path, ':') = 0
        AND instr(link_path, char(92)) = 0
        AND instr(link_path, char(10)) = 0
        AND instr(link_path, char(13)) = 0
    ),
    read_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recipient_id) REFERENCES user (id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS comment (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL,
    author_id INTEGER,
    updated_by INTEGER,
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task (id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL
);
