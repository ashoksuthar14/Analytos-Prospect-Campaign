"""
Database migration utilities.
"""

import sqlite3
from pathlib import Path
from typing import Optional


def run_migrations(db_path: str = "./database/prospect_workflow.db") -> None:
    """
    Run database migrations.
    
    Args:
        db_path: Path to database file
    """
    db_file = Path(db_path)
    schema_file = Path(__file__).parent / "schema.sql"
    
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    
    conn = sqlite3.connect(str(db_file))
    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            conn.executescript(schema_sql)
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_database_version(db_path: str = "./database/prospect_workflow.db") -> Optional[str]:
    """
    Check database version (if versioning is implemented).
    
    Args:
        db_path: Path to database file
        
    Returns:
        Database version string or None
    """
    # For now, we'll just check if tables exist
    # In the future, we can add a version table
    db_file = Path(db_path)
    
    if not db_file.exists():
        return None
    
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        )
        if cursor.fetchone():
            return "1.0.0"  # Current version
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    # Run migrations when executed directly
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "./database/prospect_workflow.db"
    print(f"Running migrations for database: {db_path}")
    run_migrations(db_path)
    print("Migrations completed successfully!")

