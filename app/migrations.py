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


MIGRATIONS = {
    1: _add_workspace_project_creators,
    2: _add_audit_columns,
    3: _migrate_project_member_roles,
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
