import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    with current_app.open_resource("schema.sql") as schema:
        connection = get_db()
        statement = ""
        indexes = []
        for line in schema.read().decode("utf-8").splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                if statement.lstrip().upper().startswith("CREATE INDEX"):
                    indexes.append(statement)
                else:
                    connection.execute(statement)
                statement = ""
    from app.migrations import apply_migrations

    apply_migrations(connection)
    for index in indexes:
        connection.execute(index)
    connection.commit()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create missing tables and apply migrations without deleting existing data."""
    init_db()
    click.echo("Database initialized (existing data preserved).")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
