"""A capable, dependency-free command-line task manager."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

APP_DIR = Path.home() / ".todo-cli"
DEFAULT_DB = APP_DIR / "tasks.db"
PRIORITIES = {"low", "medium", "high"}


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        priority TEXT NOT NULL DEFAULT 'medium',
        due_date TEXT,
        tags TEXT NOT NULL DEFAULT '[]',
        completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )""")
    conn.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    return conn


def parse_legacy_tasks(db_path: Path, conn: sqlite3.Connection) -> None:
    """Import old text-file tasks once, when creating a fresh database."""
    if conn.execute("SELECT 1 FROM app_meta WHERE key='legacy_imported'").fetchone():
        return
    candidates = [Path.cwd() / "tasks.txt", Path.cwd() / "task.txt", db_path.parent / "tasks.txt"]
    source = next((p for p in candidates if p.exists() and p.resolve() != db_path.resolve()), None)
    if source is not None:
        now = datetime.now().isoformat(timespec="seconds")
        with source.open(encoding="utf-8") as file:
            for line in file:
                item = line.strip()
                # The old project included a captured, numbered console output in task.txt.
                match = re.match(r"^\s*\d+\.\s+(.+)$", item)
                if match:
                    item = match.group(1).strip()
                if not item or item.lower().startswith("your to-do list"):
                    continue
                conn.execute("INSERT INTO tasks(title, created_at, updated_at) VALUES(?,?,?)", (item, now, now))
    conn.execute("INSERT INTO app_meta(key,value) VALUES('legacy_imported','1')")
    conn.commit()


def valid_due(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("Due date must use YYYY-MM-DD format.") from exc


def tags_value(value: str | None) -> list[str]:
    if not value:
        return []
    return list(dict.fromkeys(tag.strip().lstrip("#") for tag in value.split(",") if tag.strip()))


def add_task(conn: sqlite3.Connection, title: str, description: str = "", priority: str = "medium",
             due: str | None = None, tags: str | None = None) -> int:
    title = title.strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    if priority not in PRIORITIES:
        raise ValueError("Priority must be low, medium, or high.")
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute("INSERT INTO tasks(title,description,priority,due_date,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                       (title, description.strip(), priority, valid_due(due), json.dumps(tags_value(tags)), now, now))
    conn.commit()
    return int(cur.lastrowid)


def get_task(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"No task found with ID {task_id}.")
    return row


def update_task(conn: sqlite3.Connection, task_id: int, args: argparse.Namespace) -> None:
    row = get_task(conn, task_id)
    fields = {"title": args.title, "description": args.description, "priority": args.priority,
              "due_date": args.due, "tags": args.tags}
    values = {}
    for key, val in fields.items():
        if val is not None:
            values[key] = json.dumps(tags_value(val)) if key == "tags" else (None if key == "due_date" and val == "" else val)
    if "title" in values and not values["title"].strip():
        raise ValueError("Task title cannot be empty.")
    if "priority" in values and values["priority"] not in PRIORITIES:
        raise ValueError("Priority must be low, medium, or high.")
    if "due_date" in values:
        values["due_date"] = valid_due(values["due_date"])
    if not values:
        raise ValueError("Provide at least one field to update.")
    values["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{key}=?" for key in values)
    conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*values.values(), task_id))
    conn.commit()


def list_tasks(conn: sqlite3.Connection, status: str = "all", priority: str | None = None,
               tag: str | None = None, query: str | None = None, sort: str = "created") -> list[sqlite3.Row]:
    clauses, params = [], []
    if status == "open": clauses.append("completed=0")
    elif status == "done": clauses.append("completed=1")
    if priority:
        if priority not in PRIORITIES: raise ValueError("Priority must be low, medium, or high.")
        clauses.append("priority=?"); params.append(priority)
    if tag:
        clauses.append("tags LIKE ?"); params.append(f'%"{tag.lstrip("#")}"%')
    if query:
        clauses.append("(title LIKE ? OR description LIKE ?)"); params.extend([f"%{query}%", f"%{query}%"])
    order = {"created": "created_at DESC", "due": "due_date IS NULL, due_date ASC", "priority": "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at DESC", "title": "title COLLATE NOCASE"}[sort]
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return conn.execute(f"SELECT * FROM tasks{where} ORDER BY {order}", params).fetchall()


def task_label(row: sqlite3.Row) -> str:
    done = "✓" if row["completed"] else " "
    due = row["due_date"] or "no due date"
    if row["due_date"] and row["due_date"] < date.today().isoformat() and not row["completed"]:
        due += " OVERDUE"
    tags = " ".join("#" + t for t in json.loads(row["tags"]))
    return f"[{done}] #{row['id']} [{row['priority'].upper():6}] {row['title']}  (due: {due})" + (f"  {tags}" if tags else "")


def show_tasks(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No matching tasks.")
        return
    for row in rows:
        print(task_label(row))
        if row["description"]:
            print(f"    {row['description']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A local task manager with priorities, due dates, tags, and search.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database file (default: {DEFAULT_DB})")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("add", help="create a task")
    p.add_argument("title"); p.add_argument("-d", "--description", default=""); p.add_argument("-p", "--priority", choices=sorted(PRIORITIES), default="medium"); p.add_argument("--due", help="YYYY-MM-DD"); p.add_argument("-t", "--tags", help="comma-separated tags")
    p = sub.add_parser("list", aliases=["ls"], help="list tasks")
    p.add_argument("--status", choices=["all", "open", "done"], default="all"); p.add_argument("--priority", choices=sorted(PRIORITIES)); p.add_argument("--tag"); p.add_argument("--search", "-s"); p.add_argument("--sort", choices=["created", "due", "priority", "title"], default="created")
    p = sub.add_parser("done", help="mark a task complete"); p.add_argument("id", type=int)
    p = sub.add_parser("undo", help="reopen a completed task"); p.add_argument("id", type=int)
    p = sub.add_parser("edit", help="edit task fields"); p.add_argument("id", type=int); p.add_argument("--title"); p.add_argument("--description"); p.add_argument("--priority", choices=sorted(PRIORITIES)); p.add_argument("--due", help="YYYY-MM-DD (use --due '' to clear)"); p.add_argument("--tags", help="comma-separated tags")
    p = sub.add_parser("delete", help="delete a task"); p.add_argument("id", type=int)
    p = sub.add_parser("search", help="search titles and descriptions"); p.add_argument("query")
    sub.add_parser("stats", help="show task totals")
    sub.add_parser("interactive", aliases=["i"], help="open the interactive menu")
    return parser


def interactive(conn: sqlite3.Connection) -> None:
    print("\nTask Manager — enter a menu number, or Ctrl+C to quit.")
    while True:
        print("\n1 List   2 Add   3 Complete   4 Reopen   5 Search   6 Stats   0 Exit")
        choice = input("> ").strip()
        if choice == "0": return
        try:
            if choice == "1": show_tasks(list_tasks(conn))
            elif choice == "2":
                title = input("Title: "); description = input("Description (optional): "); priority = input("Priority [low/medium/high, default medium]: ").strip() or "medium"; due = input("Due date YYYY-MM-DD (optional): ").strip() or None; tags = input("Tags, comma separated (optional): ")
                task_id = add_task(conn, title, description, priority, due, tags); print(f"Created task #{task_id}.")
            elif choice in {"3", "4"}:
                task_id = int(input("Task ID: ")); get_task(conn, task_id)
                completed = choice == "3"; conn.execute("UPDATE tasks SET completed=?, completed_at=?, updated_at=? WHERE id=?", (int(completed), datetime.now().isoformat(timespec="seconds") if completed else None, datetime.now().isoformat(timespec="seconds"), task_id)); conn.commit(); print("Task updated.")
            elif choice == "5": show_tasks(list_tasks(conn, query=input("Search: ")))
            elif choice == "6": print_stats(conn)
            else: print("Choose one of the listed options.")
        except (ValueError, sqlite3.Error) as exc: print(f"Error: {exc}")


def print_stats(conn: sqlite3.Connection) -> None:
    total, done = conn.execute("SELECT COUNT(*), COALESCE(SUM(completed),0) FROM tasks").fetchone()
    overdue = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed=0 AND due_date < ?", (date.today().isoformat(),)).fetchone()[0]
    print(f"Tasks: {total} total | {total-done} open | {done} completed | {overdue} overdue")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    conn = connect(args.db)
    try:
        parse_legacy_tasks(args.db, conn)
        if args.command in (None, "interactive", "i"):
            interactive(conn)
        elif args.command == "add":
            task_id = add_task(conn, args.title, args.description, args.priority, args.due, args.tags); print(f"Created task #{task_id}.")
        elif args.command in ("list", "ls"):
            show_tasks(list_tasks(conn, args.status, args.priority, args.tag, args.search, args.sort))
        elif args.command == "search": show_tasks(list_tasks(conn, query=args.query))
        elif args.command in {"done", "undo"}:
            row = get_task(conn, args.id); completed = args.command == "done"; now = datetime.now().isoformat(timespec="seconds")
            conn.execute("UPDATE tasks SET completed=?, completed_at=?, updated_at=? WHERE id=?", (int(completed), now if completed else None, now, args.id)); conn.commit(); print(f"{'Completed' if completed else 'Reopened'}: {row['title']}")
        elif args.command == "edit": update_task(conn, args.id, args); print(f"Updated task #{args.id}.")
        elif args.command == "delete":
            row = get_task(conn, args.id); conn.execute("DELETE FROM tasks WHERE id=?", (args.id,)); conn.commit(); print(f"Deleted: {row['title']}")
        elif args.command == "stats": print_stats(conn)
        return 0
    except (ValueError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
