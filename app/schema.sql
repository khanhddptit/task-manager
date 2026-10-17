CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE CHECK (length(trim(username)) > 0),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workspace (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT NOT NULL DEFAULT '',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL
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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, workspace_id),
    FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS project_member (
    project_id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id),
    -- Composite keys prevent membership in a project from another workspace.
    FOREIGN KEY (project_id, workspace_id)
        REFERENCES project (id, workspace_id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, user_id)
        REFERENCES workspace_member (workspace_id, user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    created_by INTEGER,
    assignee_id INTEGER,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'in_progress', 'done')),
    due_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
    -- Unassign or reassign tasks before removing an assigned member.
    FOREIGN KEY (project_id, assignee_id)
        REFERENCES project_member (project_id, user_id) ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS comment (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL,
    author_id INTEGER,
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES task (id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES user (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_workspace_member_user ON workspace_member (user_id);
CREATE INDEX IF NOT EXISTS idx_project_workspace ON project (workspace_id);
CREATE INDEX IF NOT EXISTS idx_project_member_workspace_user
    ON project_member (workspace_id, user_id);
CREATE INDEX IF NOT EXISTS idx_project_member_user ON project_member (user_id);
CREATE INDEX IF NOT EXISTS idx_task_project_status ON task (project_id, status);
CREATE INDEX IF NOT EXISTS idx_task_project_assignee ON task (project_id, assignee_id);
CREATE INDEX IF NOT EXISTS idx_task_creator ON task (created_by);
CREATE INDEX IF NOT EXISTS idx_comment_task_created ON comment (task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comment_author ON comment (author_id);
