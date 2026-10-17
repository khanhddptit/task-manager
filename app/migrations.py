def _has_column(connection, table, column):
    return any(
        row["name"] == column
        for row in connection.execute(f"PRAGMA table_info({table})")
    )


def _add_workspace_project_creators(connection):
    if not _has_column(connection, "workspace", "created_by"):
        connection.execute(
            """ALTER TABLE workspace ADD COLUMN created_by INTEGER
               REFERENCES user (id) ON DELETE SET NULL"""
        )
    if not _has_column(connection, "project", "created_by"):
        connection.execute(
            """ALTER TABLE project ADD COLUMN created_by INTEGER
               REFERENCES user (id) ON DELETE SET NULL"""
        )


def _add_audit_columns(connection):
    if not _has_column(connection, "user", "updated_at"):
        connection.execute("ALTER TABLE user ADD COLUMN updated_at TEXT")
        connection.execute(
            "UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
        )
        connection.execute("""
            CREATE TRIGGER user_updated_at_default
            AFTER INSERT ON user
            FOR EACH ROW WHEN NEW.updated_at IS NULL
            BEGIN
                UPDATE user SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)

    for table in ("workspace", "project", "task", "comment"):
        column = "updated_by"
        if not _has_column(connection, table, column):
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} "
                "INTEGER REFERENCES user (id) ON DELETE SET NULL"
            )


MIGRATIONS = {
    1: _add_workspace_project_creators,
    2: _add_audit_columns,
}


def apply_migrations(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
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
        connection.commit()
    except Exception:
        connection.rollback()
        raise
