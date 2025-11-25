"""
Simple test script to verify workflow loader functionality.
Run this to test the configuration loading and validation.
"""

from workflow_loader import WorkflowLoader


def test_workflow_loader():
    """Test workflow loading and validation."""
    print("Testing WorkflowLoader...")
    
    try:
        loader = WorkflowLoader(config_dir="./configs")
        
        # Load workflow
        print("\n1. Loading workflow.json...")
        workflow = loader.load_workflow()
        print(f"   ✓ Workflow loaded: {workflow.get('workflow_name')}")
        print(f"   ✓ Version: {workflow.get('version')}")
        print(f"   ✓ Agents: {len(workflow.get('agents', []))}")
        
        # Validate workflow
        print("\n2. Validating workflow...")
        loader.validate_workflow()
        print("   ✓ Workflow validation passed")
        
        # Load overrides
        print("\n3. Loading overrides.json...")
        overrides = loader.load_overrides()
        print(f"   ✓ Overrides loaded: {len(overrides.get('overrides', {}))} overrides")
        
        # Get agent order
        print("\n4. Calculating agent execution order...")
        agent_order = loader.get_agent_order()
        print(f"   ✓ Agent order: {' -> '.join(agent_order)}")
        
        # Get agent configs
        print("\n5. Testing agent config retrieval...")
        for agent_name in agent_order[:3]:  # Test first 3
            agent_config = loader.get_agent_config(agent_name)
            if agent_config:
                print(f"   ✓ {agent_name}: {agent_config.get('class')}")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_workflow_loader()

