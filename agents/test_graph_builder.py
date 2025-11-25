"""
Simple test script to verify graph builder functionality.
Run this to test graph building and execution.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.workflow_loader import WorkflowLoader
from configs.secrets_provider import SecretsProvider
from agents.graph_builder import GraphBuilder
from agents.agent_factory import create_agent
from agents.base_agent import BaseAgent


class MockAgent(BaseAgent):
    """Mock agent for testing."""
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """Mock process method."""
        return {
            "output": f"Mock output from {self.name}",
            "input_received": input_data
        }


def test_graph_builder():
    """Test graph builder functionality."""
    print("Testing GraphBuilder...")
    
    try:
        # Initialize components
        print("\n1. Initializing components...")
        workflow_loader = WorkflowLoader(config_dir="./configs")
        secrets_provider = SecretsProvider()
        
        # Register mock agent
        from agents.agent_factory import register_agent
        register_agent("MockAgent", MockAgent)
        register_agent("ProspectSearchAgent", MockAgent)  # For testing
        register_agent("DataEnrichmentAgent", MockAgent)
        register_agent("ScoringAgent", MockAgent)
        register_agent("OutreachContentAgent", MockAgent)
        register_agent("OutreachExecutorAgent", MockAgent)
        register_agent("ResponseTrackerAgent", MockAgent)
        register_agent("FeedbackTrainerAgent", MockAgent)
        
        print("   ✓ Components initialized")
        
        # Create graph builder
        print("\n2. Creating graph builder...")
        graph_builder = GraphBuilder(
            workflow_loader=workflow_loader,
            agent_factory=create_agent,
            secrets_provider=secrets_provider,
            logger=None
        )
        print("   ✓ Graph builder created")
        
        # Build graph
        print("\n3. Building graph from workflow.json...")
        graph = graph_builder.build_graph(apply_overrides=True)
        print("   ✓ Graph built successfully")
        
        # Get agent order
        print("\n4. Getting agent execution order...")
        agent_order = workflow_loader.get_agent_order()
        print(f"   ✓ Agent order: {' -> '.join(agent_order)}")
        
        # Test getting agents
        print("\n5. Testing agent retrieval...")
        for agent_name in agent_order[:3]:  # Test first 3
            agent = graph_builder.get_agent(agent_name)
            if agent:
                print(f"   ✓ Agent {agent_name}: {agent.__class__.__name__}")
        
        print("\n✅ All graph builder tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_graph_builder()

