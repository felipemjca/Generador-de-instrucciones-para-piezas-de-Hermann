from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import click
from flask import Flask, current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    output_filename TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db() -> None:
    database = get_db()
    database.executescript(SCHEMA)
    database.commit()


def list_instructions() -> list[dict]:
    rows = get_db().execute(
        "SELECT id, title, output_filename, created_at, updated_at "
        "FROM instructions ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_instruction(instruction_id: int) -> dict | None:
    row = get_db().execute(
        "SELECT * FROM instructions WHERE id = ?", (instruction_id,)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json"))
    return result


def save_instruction(payload: dict, instruction_id: int | None = None) -> int:
    database = get_db()
    now = utc_now()
    title = payload.get("general", {}).get("operation_short") or "Nueva instrucción"
    serialized = json.dumps(payload, ensure_ascii=False)
    if instruction_id is None:
        cursor = database.execute(
            "INSERT INTO instructions "
            "(title, payload_json, output_filename, created_at, updated_at) "
            "VALUES (?, ?, NULL, ?, ?)",
            (title, serialized, now, now),
        )
        instruction_id = int(cursor.lastrowid)
    else:
        database.execute(
            "UPDATE instructions SET title = ?, payload_json = ?, updated_at = ? "
            "WHERE id = ?",
            (title, serialized, now, instruction_id),
        )
    database.commit()
    return instruction_id


def update_payload(instruction_id: int, payload: dict) -> None:
    database = get_db()
    database.execute(
        "UPDATE instructions SET payload_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(payload, ensure_ascii=False), utc_now(), instruction_id),
    )
    database.commit()


def set_output(instruction_id: int, filename: str) -> None:
    database = get_db()
    database.execute(
        "UPDATE instructions SET output_filename = ?, updated_at = ? WHERE id = ?",
        (filename, utc_now(), instruction_id),
    )
    database.commit()


def delete_instruction(instruction_id: int) -> None:
    database = get_db()
    database.execute("DELETE FROM instructions WHERE id = ?", (instruction_id,))
    database.commit()


@click.command("init-db")
def init_db_command() -> None:
    init_db()
    click.echo("Base de datos inicializada.")


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    with app.app_context():
        init_db()
