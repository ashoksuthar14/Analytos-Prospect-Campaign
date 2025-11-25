import sqlite3
from pathlib import Path
from typing import List, Tuple


def list_tables(db_path: Path) -> List[str]:
    """Return a sorted list of table names in the SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows: List[Tuple[str]] = cursor.fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def main() -> None:
    db_path = Path("database") / "prospect_workflow.db"

    try:
        tables = list_tables(db_path)
    except FileNotFoundError as exc:
        print(exc)
        return

    if not tables:
        print("No tables found in the database.")
        return

    print("Tables in prospect_workflow.db:")
    for name in tables:
        print(f"- {name}")


if __name__ == "__main__":
    main()

