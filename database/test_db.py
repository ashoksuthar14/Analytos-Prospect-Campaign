"""
Simple test script to verify database service functionality.
Run this to test database operations.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_service import DatabaseService
from database.run_logger import RunLogger


def test_database_service():
    """Test database service operations."""
    print("Testing DatabaseService...")
    
    # Use test database
    db_service = DatabaseService(db_path="./database/test_workflow.db")
    
    try:
        # Test 1: Create run
        print("\n1. Creating a test run...")
        run_id = db_service.create_run(
            workflow_name="test_workflow",
            config_snapshot={"test": "config"}
        )
        print(f"   ✓ Run created: {run_id}")
        
        # Test 2: Update run status
        print("\n2. Updating run status...")
        db_service.update_run_status(run_id, "running")
        run = db_service.get_run(run_id)
        print(f"   ✓ Run status: {run['status']}")
        
        # Test 3: Create leads
        print("\n3. Creating test leads...")
        lead_data = {
            "company_name": "Test Company",
            "domain": "test.com",
            "contact_email": "test@test.com",
            "contact_name": "Test User",
            "contact_title": "CEO",
            "revenue": 50000000,
            "employee_count": 200,
            "industry": "SaaS",
            "location": "USA",
            "score": 85.5,
            "fit_score": 0.9,
            "engagement_score": 0.8,
            "intent_score": 0.7
        }
        lead_id = db_service.create_lead(run_id, lead_data)
        print(f"   ✓ Lead created: {lead_id}")
        
        # Test 4: Get leads by run
        print("\n4. Retrieving leads...")
        leads = db_service.get_leads_by_run(run_id)
        print(f"   ✓ Found {len(leads)} leads")
        
        # Test 5: Create message
        print("\n5. Creating test message...")
        message_data = {
            "subject": "Test Subject",
            "body": "Test body content",
            "personalization_used": ["company_name", "role"],
            "provider": "sendgrid",
            "status": "sent"
        }
        message_id = db_service.create_message(run_id, lead_id, message_data)
        print(f"   ✓ Message created: {message_id}")
        
        # Test 6: Create response
        print("\n6. Creating test response...")
        response_id = db_service.create_response(message_id)
        print(f"   ✓ Response created: {response_id}")
        
        # Test 7: Update response
        print("\n7. Updating response...")
        from datetime import datetime
        db_service.update_response(
            response_id,
            opened=True,
            opened_at=datetime.utcnow(),
            clicked=True,
            clicked_at=datetime.utcnow()
        )
        print("   ✓ Response updated")
        
        # Test 8: Create recommendation
        print("\n8. Creating test recommendation...")
        rec_id = db_service.create_recommendation(
            run_id=run_id,
            field="scoring.weights.fit_score",
            old_value=0.5,
            new_value=0.6,
            reason="Improved fit score based on engagement data"
        )
        print(f"   ✓ Recommendation created: {rec_id}")
        
        # Test 9: Get pending recommendations
        print("\n9. Getting pending recommendations...")
        pending = db_service.get_pending_recommendations(run_id)
        print(f"   ✓ Found {len(pending)} pending recommendations")
        
        # Test 10: Complete run
        print("\n10. Completing run...")
        metrics = {
            "total_leads": 1,
            "messages_sent": 1,
            "replies": 0
        }
        db_service.update_run_status(run_id, "completed", metrics=metrics)
        run = db_service.get_run(run_id)
        print(f"   ✓ Run completed: {run['status']}")
        
        print("\n✅ All database service tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: delete test database
        import os
        test_db_path = "./database/test_workflow.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print(f"\n🧹 Cleaned up test database: {test_db_path}")


def test_run_logger():
    """Test run logger functionality."""
    print("\n\nTesting RunLogger...")
    
    db_service = DatabaseService(db_path="./database/test_workflow.db")
    logger = RunLogger(db_service, log_dir="./logs", enable_full_traces=True)
    
    try:
        # Create a test run
        run_id = db_service.create_run("test_workflow")
        print(f"\n1. Created test run: {run_id}")
        
        # Test logging
        print("\n2. Logging agent start...")
        logger.log_agent_start(run_id, "prospect_search", {"input": "test"})
        print("   ✓ Agent start logged")
        
        print("\n3. Logging tool call...")
        logger.log_tool_call(
            run_id, "prospect_search", "clay_api",
            tool_input={"query": "test"},
            tool_output={"results": []},
            duration_ms=150
        )
        print("   ✓ Tool call logged")
        
        print("\n4. Logging agent output...")
        logger.log_agent_output(run_id, "prospect_search", {"output": "test"}, duration_ms=200)
        print("   ✓ Agent output logged")
        
        # Test export
        print("\n5. Exporting run logs...")
        log_file = logger.export_run_logs(run_id)
        if log_file:
            print(f"   ✓ Logs exported to: {log_file}")
        
        # Test summary
        print("\n6. Getting run summary...")
        summary = logger.get_run_summary(run_id)
        print(f"   ✓ Summary: {json.dumps(summary, indent=2)}")
        
        print("\n✅ All run logger tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success1 = test_database_service()
    success2 = test_run_logger()
    
    if success1 and success2:
        print("\n\n🎉 All tests passed!")
    else:
        print("\n\n⚠️  Some tests failed!")

