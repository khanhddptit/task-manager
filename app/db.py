import sqlite3
from contextlib import contextmanager

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@contextmanager
def write_transaction():
    db = get_db()
    if db.in_transaction:
        raise RuntimeError("Nested write transactions are not supported.")
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    db = get_db()

    # 1. Tạo bảng còn thiếu (CREATE TABLE IF NOT EXISTS)
    with current_app.open_resource("schema.sql") as schema:
        db.executescript(schema.read().decode("utf-8"))

    # 2. Thêm cột audit còn thiếu trên DB cũ
    from app.migrations import apply_migrations
    apply_migrations(db)

    # 3. Tạo index còn thiếu (CREATE INDEX IF NOT EXISTS)
    with current_app.open_resource("indexes.sql") as indexes:
        db.executescript(indexes.read().decode("utf-8"))


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create missing tables, apply migrations, and create indexes without deleting existing data."""
    init_db()
    click.echo("Database initialized (existing data preserved).")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)