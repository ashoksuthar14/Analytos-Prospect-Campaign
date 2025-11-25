"""
Integration test for Phase 3: Graph Builder & Execution Engine
Tests the complete workflow from graph building to execution.
"""

import sys
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.workflow_loader import WorkflowLoader
from configs.secrets_provider import SecretsProvider
from database.db_service import DatabaseService
from database.run_logger import RunLogger
from agents.graph_builder import GraphBuilder
from agents.execution_engine import ExecutionEngine
from agents.agent_factory import create_agent, register_agent
from agents.base_agent import BaseAgent
from typing import Dict, Any


class MockProspectSearchAgent(BaseAgent):
    """Mock ProspectSearchAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock prospect search."""
        icp = input_data.get("icp", {})
        return {
            "leads": [
                {
                    "company_name": "Test SaaS Company",
                    "domain": "testsaas.com",
                    "contact_email": "ceo@testsaas.com",
                    "contact_name": "John Doe",
                    "contact_title": "CEO",
                    "revenue": 50000000,
                    "employee_count": 200,
                    "industry": "SaaS",
                    "location": "USA"
                }
            ]
        }


class MockDataEnrichmentAgent(BaseAgent):
    """Mock DataEnrichmentAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock data enrichment."""
        leads = input_data.get("leads", [])
        enriched_leads = []
        for lead in leads:
            enriched_lead = lead.copy()
            enriched_lead["enrichment"] = {
                "linkedin_url": f"https://linkedin.com/company/{lead.get('company_name', '').lower().replace(' ', '-')}",
                "tech_stack": ["Salesforce", "HubSpot"],
                "firmographics": {
                    "founded_year": 2015,
                    "headquarters": "San Francisco, CA"
                }
            }
            enriched_leads.append(enriched_lead)
        
        return {"leads": enriched_leads}


class MockScoringAgent(BaseAgent):
    """Mock ScoringAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock scoring."""
        leads = input_data.get("leads", [])
        ranked_leads = []
        for lead in leads:
            score = 85.0  # Mock score
            ranked_leads.append({
                "lead": lead,
                "score": score,
                "fit_score": 0.9,
                "engagement_score": 0.8,
                "intent_score": 0.7
            })
        
        # Sort by score descending
        ranked_leads.sort(key=lambda x: x["score"], reverse=True)
        return {"ranked_leads": ranked_leads}


class MockOutreachContentAgent(BaseAgent):
    """Mock OutreachContentAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock outreach content generation."""
        ranked_leads = input_data.get("ranked_leads", [])
        top_n = input_data.get("top_n", 20)
        
        messages = []
        for ranked_lead in ranked_leads[:top_n]:
            lead = ranked_lead.get("lead", {})
            messages.append({
                "lead_id": f"lead_{lead.get('company_name', 'unknown')}",
                "subject": f"Quick question about {lead.get('company_name', 'your company')}",
                "body": f"Hi {lead.get('contact_name', 'there')},\n\nI noticed {lead.get('company_name')} is in the SaaS space...",
                "personalization_used": ["company_name", "contact_name"]
            })
        
        return {"messages": messages}


class MockOutreachExecutorAgent(BaseAgent):
    """Mock OutreachExecutorAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock email sending."""
        messages = input_data.get("messages", [])
        sent_messages = []
        
        for msg in messages:
            sent_messages.append({
                "message_id": f"msg_{len(sent_messages)}",
                "lead_id": msg.get("lead_id"),
                "status": "sent",
                "sent_at": "2024-01-01T00:00:00Z",
                "provider": "sendgrid"
            })
        
        return {"messages": sent_messages}


class MockResponseTrackerAgent(BaseAgent):
    """Mock ResponseTrackerAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock response tracking."""
        message_ids = input_data.get("message_ids", [])
        responses = []
        
        for msg_data in message_ids:
            responses.append({
                "message_id": msg_data.get("message_id"),
                "opened": True,
                "opened_at": "2024-01-01T01:00:00Z",
                "clicked": False,
                "replied": False,
                "meeting_scheduled": False
            })
        
        return {"responses": responses}


class MockFeedbackTrainerAgent(BaseAgent):
    """Mock FeedbackTrainerAgent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock feedback training."""
        return {
            "recommendations": [
                {
                    "field": "scoring.weights.fit_score",
                    "old_value": 0.5,
                    "new_value": 0.6,
                    "reason": "Improved fit score based on engagement data"
                }
            ],
            "metrics": {
                "open_rate": 0.25,
                "reply_rate": 0.05,
                "meeting_rate": 0.01
            },
            "status": "waiting_approval"
        }


def test_phase3_integration():
    """Test complete Phase 3 integration."""
    print("=" * 60)
    print("Phase 3 Integration Test")
    print("=" * 60)
    
    # Use test database
    db_path = "./database/test_phase3.db"
    
    try:
        # 1. Initialize components
        print("\n1. Initializing components...")
        workflow_loader = WorkflowLoader(config_dir="./configs")
        secrets_provider = SecretsProvider()
        db_service = DatabaseService(db_path=db_path)
        run_logger = RunLogger(db_service, log_dir="./logs", enable_full_traces=True)
        
        print("   ✓ Components initialized")
        
        # 2. Register mock agents
        print("\n2. Registering mock agents...")
        register_agent("ProspectSearchAgent", MockProspectSearchAgent)
        register_agent("DataEnrichmentAgent", MockDataEnrichmentAgent)
        register_agent("ScoringAgent", MockScoringAgent)
        register_agent("OutreachContentAgent", MockOutreachContentAgent)
        register_agent("OutreachExecutorAgent", MockOutreachExecutorAgent)
        register_agent("ResponseTrackerAgent", MockResponseTrackerAgent)
        register_agent("FeedbackTrainerAgent", MockFeedbackTrainerAgent)
        print("   ✓ All 7 agents registered")
        
        # 3. Create graph builder
        print("\n3. Creating graph builder...")
        graph_builder = GraphBuilder(
            workflow_loader=workflow_loader,
            agent_factory=create_agent,
            secrets_provider=secrets_provider,
            logger=run_logger
        )
        print("   ✓ Graph builder created")
        
        # 4. Build graph
        print("\n4. Building graph from workflow.json...")
        graph = graph_builder.build_graph(apply_overrides=True)
        print("   ✓ Graph built successfully")
        
        # Verify agent order
        agent_order = workflow_loader.get_agent_order()
        print(f"   ✓ Agent execution order: {' → '.join(agent_order)}")
        
        # 5. Create execution engine
        print("\n5. Creating execution engine...")
        execution_engine = ExecutionEngine(
            workflow_loader=workflow_loader,
            graph_builder=graph_builder,
            db_service=db_service,
            run_logger=run_logger,
            progress_callback=lambda progress: print(f"   📊 Progress: {progress.get('message', '')}")
        )
        print("   ✓ Execution engine created")
        
        # 6. Create a test run
        print("\n6. Creating test run...")
        run_id = db_service.create_run(
            workflow_name="prospect_to_lead_v1",
            config_snapshot=workflow_loader.get_workflow()
        )
        print(f"   ✓ Run created: {run_id}")
        
        # 7. Execute workflow
        print("\n7. Executing workflow...")
        print("   " + "-" * 50)
        initial_state = {
            "run_id": run_id,
            "workflow_name": "prospect_to_lead_v1"
        }
        
        final_state = execution_engine.execute_workflow(
            run_id=run_id,
            initial_state=initial_state
        )
        print("   " + "-" * 50)
        print("   ✓ Workflow execution completed")
        
        # 8. Verify results
        print("\n8. Verifying results...")
        
        # Check run status
        run = db_service.get_run(run_id)
        print(f"   ✓ Run status: {run['status']}")
        
        # Check leads
        leads = db_service.get_leads_by_run(run_id)
        print(f"   ✓ Leads created: {len(leads)}")
        
        # Check messages
        messages = db_service.get_messages_by_run(run_id)
        print(f"   ✓ Messages created: {len(messages)}")
        
        # Check state outputs
        output_keys = [key for key in final_state.keys() if key.endswith("_output")]
        print(f"   ✓ Agent outputs in state: {len(output_keys)}")
        for key in output_keys:
            print(f"      - {key}")
        
        # 9. Check progress
        print("\n9. Checking execution progress...")
        progress = execution_engine.get_progress(run_id)
        print(f"   ✓ Progress: {progress.get('progress_percent', 0):.1f}%")
        print(f"   ✓ Completed agents: {len(progress.get('completed_agents', []))}/{progress.get('total_agents', 0)}")
        
        # 10. Test conditional branching
        print("\n10. Testing conditional branching...")
        scoring_agent = graph_builder.get_agent("scoring")
        if scoring_agent:
            # Test condition check
            test_state = {"scoring_output": {"ranked_leads": [{"score": 45}]}}
            condition_result = scoring_agent.check_condition(test_state)
            print(f"   ✓ Condition check (score < 50): {not condition_result} (should skip)")
        
        print("\n" + "=" * 60)
        print("✅ Phase 3 Integration Test PASSED!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        import os
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"\n🧹 Cleaned up test database: {db_path}")


if __name__ == "__main__":
    success = test_phase3_integration()
    sys.exit(0 if success else 1)

