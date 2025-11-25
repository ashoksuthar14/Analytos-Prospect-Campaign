"""
Agent Factory: Creates agent instances from configuration.
"""

from typing import Dict, Any, Type, Optional
from agents.base_agent import BaseAgent
from configs.secrets_provider import SecretsProvider


# Agent registry - maps agent class names to actual classes
AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}


def register_agent(class_name: str, agent_class: Type[BaseAgent]) -> None:
    """
    Register an agent class in the registry.
    
    Args:
        class_name: Agent class name
        agent_class: Agent class
    """
    AGENT_REGISTRY[class_name] = agent_class


def create_agent(
    agent_name: str,
    agent_config: Dict[str, Any],
    secrets_provider: SecretsProvider,
    logger: Optional[Any] = None
) -> BaseAgent:
    """
    Create an agent instance from configuration.
    
    Args:
        agent_name: Agent name
        agent_config: Agent configuration from workflow.json
        secrets_provider: SecretsProvider instance
        logger: RunLogger instance (optional)
        
    Returns:
        Agent instance
        
    Raises:
        ValueError: If agent class not found in registry
    """
    class_name = agent_config.get("class")
    if not class_name:
        raise ValueError(f"Agent {agent_name} missing 'class' in configuration")
    
    agent_class = AGENT_REGISTRY.get(class_name)
    if not agent_class:
        raise ValueError(
            f"Agent class {class_name} not found in registry. "
            f"Available: {list(AGENT_REGISTRY.keys())}"
        )
    
    # Create agent instance
    agent = agent_class(
        name=agent_name,
        config=agent_config,
        secrets_provider=secrets_provider,
        logger=logger
    )
    
    return agent


def get_agent_registry() -> Dict[str, Type[BaseAgent]]:
    """Get the agent registry."""
    return AGENT_REGISTRY.copy()

