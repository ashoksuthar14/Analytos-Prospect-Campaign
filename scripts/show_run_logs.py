"""
Script to view run logs from the database.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "prospect_workflow.db"

def show_run_logs():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get the most recent run
    cur.execute("SELECT run_id, workflow_name, status, started_at FROM runs ORDER BY started_at DESC LIMIT 1")
    run = cur.fetchone()
    
    if not run:
        print("No runs found in database.")
        conn.close()
        return
    
    run_id, workflow_name, status, started_at = run
    print(f"\nMost Recent Run:")
    print(f"  Run ID: {run_id}")
    print(f"  Workflow: {workflow_name}")
    print(f"  Status: {status}")
    print(f"  Started: {started_at}")
    
    # Get logs for outreach_content agent
    print(f"\n{'='*100}")
    print("OUTREACH_CONTENT AGENT LOGS")
    print(f"{'='*100}\n")
    
    cur.execute("""
        SELECT agent_name, step, input_data, output_data, error_data, timestamp
        FROM run_logs
        WHERE run_id = ? AND agent_name = 'outreach_content'
        ORDER BY timestamp ASC
    """, (run_id,))
    
    logs = cur.fetchall()
    
    if not logs:
        print("No logs found for outreach_content agent.")
    
    for log in logs:
        agent_name, step, input_data, output_data, error_data, timestamp = log
        print(f"\n[{timestamp}] {agent_name} - {step}")
        
        if error_data and error_data != 'null':
            print(f"  ❌ ERROR: {error_data[:500]}")
        
        if output_data and output_data != 'null':
            print(f"  ✅ OUTPUT (preview): {output_data[:200]}...")
    
    conn.close()

if __name__ == "__main__":
    show_run_logs()

