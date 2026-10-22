def _has_column(connection, table, column):
    return any(
        row["name"] == column
        for row in connection.execute(f"PRAGMA table_info({table})")
    )


def _add_column(connection, table, column, definition):
    if not _has_column(connection, table, column):
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def _add_workspace_project_creators(connection):
    _add_column(
        connection,
        "workspace",
        "created_by",
        "INTEGER REFERENCES user (id) ON DELETE SET NULL",
    )
    _add_column(
        connection,
        "project",
        "created_by",
        "INTEGER REFERENCES user (id) ON DELETE SET NULL",
    )


def _migrate_project_member_roles(connection):
    connection.execute("""
        CREATE TABLE project_member_new (
            project_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member'
                CHECK (role IN ('admin', 'member')),
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (project_id, workspace_id)
                REFERENCES project (id, workspace_id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id, user_id)
                REFERENCES workspace_member (workspace_id, user_id)
                ON DELETE CASCADE
        )
    """)
    connection.execute("""
        INSERT INTO project_member_new
            (project_id, workspace_id, user_id, role, joined_at)
        SELECT project_id, workspace_id, user_id,
               CASE role WHEN 'owner' THEN 'admin' ELSE role END,
               joined_at
        FROM project_member
    """)
    connection.execute("DROP TABLE project_member")
    connection.execute(
        "ALTER TABLE project_member_new RENAME TO project_member"
    )


def _add_audit_columns(connection):
    # Thêm cột updated_at cho user (nếu chưa có)
    _add_column(connection, "user", "updated_at", "TEXT")

    # Điền giá trị mặc định cho các bản ghi cũ còn NULL
    connection.execute(
        "UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
    )

    # Trigger tự động set updated_at khi INSERT (IF NOT EXISTS để an toàn khi chạy lại)
    connection.execute("""
        CREATE TRIGGER IF NOT EXISTS set_user_updated_at_after_insert
        AFTER INSERT ON user
        WHEN NEW.updated_at IS NULL
        BEGIN
            UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """)

    # Thêm cột updated_by cho các bảng audit
    for table in ("workspace", "project", "task", "comment"):
        _add_column(
            connection,
            table,
            "updated_by",
            "INTEGER REFERENCES user (id) ON DELETE SET NULL",
        )


def _enforce_single_workspace_owner(connection):
    _require_workspace_owners(connection)

    duplicate = connection.execute("""
        SELECT workspace_id
        FROM workspace_member
        WHERE role = 'owner'
        GROUP BY workspace_id
        HAVING COUNT(*) > 1
        LIMIT 1
    """).fetchone()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot enforce single Workspace Owner: "
            f"workspace {duplicate['workspace_id']} has multiple Workspace Owners."
        )
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_single_owner
        ON workspace_member (workspace_id)
        WHERE role = 'owner'
    """)


def _require_workspace_owners(connection):
    ownerless = connection.execute("""
        SELECT w.id AS workspace_id
        FROM workspace AS w
        LEFT JOIN workspace_member AS wm
          ON wm.workspace_id = w.id AND wm.role = 'owner'
        GROUP BY w.id
        HAVING COUNT(wm.user_id) = 0
        LIMIT 1
    """).fetchone()
    if ownerless is not None:
        raise RuntimeError(
            "Cannot enforce Workspace Owner: "
            f"workspace {ownerless['workspace_id']} has no Workspace Owner."
        )


def _remove_project_owner_role(connection):
    connection.execute("""
        CREATE TABLE project_member_new (
            project_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member'
                CHECK (role IN ('admin', 'member')),
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (project_id, workspace_id)
                REFERENCES project (id, workspace_id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id, user_id)
                REFERENCES workspace_member (workspace_id, user_id)
                ON DELETE CASCADE
        )
    """)
    connection.execute("""
        INSERT INTO project_member_new
            (project_id, workspace_id, user_id, role, joined_at)
        SELECT project_id, workspace_id, user_id,
               CASE role WHEN 'owner' THEN 'admin' ELSE role END,
               joined_at
        FROM project_member
    """)
    connection.execute("DROP TABLE project_member")
    connection.execute(
        "ALTER TABLE project_member_new RENAME TO project_member"
    )


def _ensure_project_member_roles(connection):
    definition = connection.execute("""
        SELECT sql FROM sqlite_master
        WHERE type = 'table' AND name = 'project_member'
    """).fetchone()["sql"]
    has_legacy_owner_role = connection.execute(
        "SELECT 1 FROM project_member WHERE role = 'owner' LIMIT 1"
    ).fetchone()
    if "owner" in definition.lower() or has_legacy_owner_role is not None:
        _remove_project_owner_role(connection)


def _migrate_task_review_priority(connection):
    task_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(task)")
    }
    definition = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task'"
    ).fetchone()["sql"].lower()
    if "priority" in task_columns and "review" in definition:
        return

    unsupported_status = connection.execute(
        "SELECT status FROM task "
        "WHERE status NOT IN ('todo', 'in_progress', 'review', 'done') LIMIT 1"
    ).fetchone()
    if unsupported_status is not None:
        raise RuntimeError(
            "Cannot migrate task status outside todo/in_progress/review/done."
        )
    priority_expression = "priority" if "priority" in task_columns else "'medium'"
    invalid_priority = connection.execute(
        f"SELECT {priority_expression} FROM task "
        f"WHERE {priority_expression} NOT IN ('low', 'medium', 'high') LIMIT 1"
    ).fetchone()
    if invalid_priority is not None:
        raise RuntimeError(
            "Cannot migrate task priority outside low/medium/high."
        )

    connection.execute("""
        CREATE TABLE task_new (
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
            due_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
            FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL,
            FOREIGN KEY (project_id, assignee_id)
                REFERENCES project_member (project_id, user_id) ON DELETE NO ACTION
        )
    """)
    connection.execute(f"""
        INSERT INTO task_new
            (id, project_id, created_by, assignee_id, updated_by, title,
             description, status, priority, due_date, created_at, updated_at)
        SELECT id, project_id, created_by, assignee_id, updated_by, title,
               description, status, {priority_expression}, due_date,
               created_at, updated_at
        FROM task
    """)
    connection.execute("DROP TABLE task")
    connection.execute("ALTER TABLE task_new RENAME TO task")


def _migrate_user_profile_fields(connection):
    _add_column(connection, "user", "display_name", "TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "user", "email", "TEXT")
    _add_column(connection, "user", "avatar_path", "TEXT")
    _add_column(
        connection,
        "user",
        "auth_version",
        "INTEGER NOT NULL DEFAULT 0 CHECK (auth_version >= 0)",
    )
    connection.execute(
        "UPDATE user SET display_name = username "
        "WHERE display_name IS NULL OR length(trim(display_name)) = 0"
    )


def _migrate_google_identity(connection):
    _add_column(
        connection,
        "user",
        "password_login_enabled",
        "INTEGER NOT NULL DEFAULT 1 CHECK (password_login_enabled IN (0, 1))",
    )
    connection.execute("""
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
        )
    """)


def _migrate_sprint_model(connection):
    connection.execute("""
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
        )
    """)

    task_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(task)")
    }
    task_definition = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task'"
    ).fetchone()["sql"].lower()
    has_sprint_constraint = "references sprint (id, project_id)" in task_definition
    sprint_expression = "sprint_id" if "sprint_id" in task_columns else "NULL"

    if "sprint_id" not in task_columns or not has_sprint_constraint:
        invalid_sprint = connection.execute(f"""
            SELECT t.id FROM task AS t
            LEFT JOIN sprint AS s ON s.id = {sprint_expression}
            WHERE {sprint_expression} IS NOT NULL
              AND (s.id IS NULL OR s.project_id != t.project_id)
            LIMIT 1
        """).fetchone()
        if invalid_sprint is not None:
            raise RuntimeError(
                "Cannot migrate task with sprint from a different project."
            )

        connection.execute("""
            CREATE TABLE task_new (
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
                due_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project (id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES user (id) ON DELETE SET NULL,
                FOREIGN KEY (updated_by) REFERENCES user (id) ON DELETE SET NULL,
                FOREIGN KEY (project_id, assignee_id)
                    REFERENCES project_member (project_id, user_id) ON DELETE NO ACTION,
                FOREIGN KEY (sprint_id, project_id)
                    REFERENCES sprint (id, project_id) ON DELETE RESTRICT
            )
        """)
        connection.execute(f"""
            INSERT INTO task_new
                (id, project_id, created_by, assignee_id, updated_by, title,
                 description, status, priority, sprint_id, due_date, created_at,
                 updated_at)
            SELECT id, project_id, created_by, assignee_id, updated_by, title,
                   description, status, priority, {sprint_expression}, due_date,
                   created_at, updated_at
            FROM task
        """)
        connection.execute("DROP TABLE task")
        connection.execute("ALTER TABLE task_new RENAME TO task")

    connection.execute("""
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
        )
    """)


def _create_notification_table(connection):
    connection.execute("""
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
        )
    """)


def _create_member_invitation_table(connection):
    connection.execute("""
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
        )
    """)


def _migrate_task_positions(connection):
    if not _has_column(connection, "task", "position"):
        connection.execute(
            "ALTER TABLE task ADD COLUMN position INTEGER NOT NULL DEFAULT 0 "
            "CHECK (position >= 0)"
        )
        connection.execute("""
            WITH ranked_tasks AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY project_id, status
                           ORDER BY created_at, id
                       ) - 1 AS task_position
                FROM task
            )
            UPDATE task
            SET position = (
                SELECT task_position FROM ranked_tasks
                WHERE ranked_tasks.id = task.id
            )
        """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_project_status_position
        ON task (project_id, status, position, id)
    """)


def _create_password_reset_tables(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_token (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            consumed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_attempt (
            id INTEGER PRIMARY KEY,
            email_hash TEXT NOT NULL,
            ip_hash TEXT NOT NULL,
            requested_at TEXT NOT NULL
        )
    """)


MIGRATIONS = {
    1: _add_workspace_project_creators,
    2: _add_audit_columns,
    3: _migrate_project_member_roles,
    4: _enforce_single_workspace_owner,
    5: _require_workspace_owners,
    6: _ensure_project_member_roles,
    7: _migrate_task_review_priority,
    8: _migrate_user_profile_fields,
    9: _migrate_google_identity,
    10: _migrate_sprint_model,
    11: _create_member_invitation_table,
    12: _create_notification_table,
    13: _create_password_reset_tables,
    14: _migrate_task_positions,
}


def apply_migrations(connection):
    if connection.in_transaction:
        raise RuntimeError("Database migrations require an idle connection.")

    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migration (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for version, migrate in MIGRATIONS.items():
            applied = connection.execute(
                "SELECT 1 FROM schema_migration WHERE version = ?",
                (version,),
            ).fetchone()
            if applied is None:
                migrate(connection)
                connection.execute(
                    "INSERT INTO schema_migration (version) VALUES (?)",
                    (version,),
                )
        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_errors:
            raise RuntimeError(
                "Database foreign-key check failed after migrations: "
                f"{[tuple(row) for row in foreign_key_errors]}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
