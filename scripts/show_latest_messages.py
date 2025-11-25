"""
Script to view messages from the most recent run.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "prospect_workflow.db"

def show_latest_messages():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get the most recent run
    cur.execute("SELECT run_id, started_at FROM runs ORDER BY started_at DESC LIMIT 1")
    run = cur.fetchone()
    
    if not run:
        print("No runs found.")
        conn.close()
        return
    
    run_id, started_at = run
    print(f"\nMost Recent Run: {run_id}")
    print(f"Started: {started_at}\n")
    
    # Get messages for this run
    cur.execute("""
        SELECT subject, body, created_at
        FROM messages
        WHERE run_id = ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (run_id,))
    
    messages = cur.fetchall()
    
    if not messages:
        print("No messages found for this run.")
    else:
        print(f"Found {len(messages)} messages:\n")
        print("="*100)
        
        for i, (subject, body, created_at) in enumerate(messages, 1):
            print(f"\nMESSAGE #{i}")
            print(f"Created: {created_at}")
            print(f"\nSUBJECT: {subject}")
            print(f"\nBODY:\n{body}")
            print("\n" + "="*100)
    
    conn.close()

if __name__ == "__main__":
    show_latest_messages()

