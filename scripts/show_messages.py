"""
Script to view messages from the database.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "prospect_workflow.db"

def show_messages():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Count messages
    cur.execute("SELECT COUNT(*) FROM messages")
    total = cur.fetchone()[0]
    print(f"\nTotal messages in database: {total}\n")
    
    if total == 0:
        print("No messages found in database.")
        conn.close()
        return
    
    # Get recent messages
    cur.execute("""
        SELECT m.message_id, m.lead_id, m.subject, m.body, m.status, m.created_at,
               l.company_name, l.contact_name, l.contact_email
        FROM messages m
        LEFT JOIN leads l ON m.lead_id = l.lead_id
        ORDER BY m.created_at DESC
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    
    print("=" * 100)
    print("RECENT OUTREACH MESSAGES")
    print("=" * 100)
    
    for i, row in enumerate(rows, 1):
        msg_id, lead_id, subject, body, status, created_at, company, contact, email = row
        
        print(f"\n{'='*100}")
        print(f"MESSAGE #{i}")
        print(f"{'='*100}")
        print(f"Message ID: {msg_id}")
        print(f"Lead ID: {lead_id}")
        print(f"Company: {company or 'N/A'}")
        print(f"Contact: {contact or 'N/A'}")
        print(f"Email: {email or 'N/A'}")
        print(f"Status: {status}")
        print(f"Created: {created_at}")
        print(f"\n--- SUBJECT ---")
        print(subject or "(No subject)")
        print(f"\n--- BODY ---")
        print(body or "(No body)")
        print(f"\n{'='*100}\n")
    
    conn.close()

if __name__ == "__main__":
    show_messages()

