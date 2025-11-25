"""
WorkflowLoader: Validates and loads workflow.json configuration.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class WorkflowLoader:
    """
    Loads and validates workflow.json configuration.
    
    Handles:
    - Parsing workflow.json
    - Validating required keys
    - Merging overrides.json
    - Loading agent configurations
    """
    
    def __init__(self, config_dir: str = "./configs"):
        """
        Initialize the workflow loader.
        
        Args:
            config_dir: Directory containing workflow.json and overrides.json
        """
        self.config_dir = Path(config_dir)
        self.workflow_path = self.config_dir / "workflow.json"
        self.overrides_path = self.config_dir / "overrides.json"
        self.workflow: Optional[Dict[str, Any]] = None
        self.overrides: Optional[Dict[str, Any]] = None
    
    def load_workflow(self) -> Dict[str, Any]:
        """
        Load and parse workflow.json.
        
        Returns:
            Parsed workflow configuration dictionary
            
        Raises:
            FileNotFoundError: If workflow.json doesn't exist
            json.JSONDecodeError: If workflow.json is invalid JSON
        """
        if not self.workflow_path.exists():
            raise FileNotFoundError(
                f"Workflow configuration not found at {self.workflow_path}"
            )
        
        with open(self.workflow_path, 'r', encoding='utf-8') as f:
            self.workflow = json.load(f)
        
        return self.workflow
    
    def load_overrides(self) -> Dict[str, Any]:
        """
        Load and parse overrides.json if it exists.
        
        Returns:
            Parsed overrides configuration dictionary, or empty dict if not found
        """
        if not self.overrides_path.exists():
            self.overrides = {}
            return self.overrides
        
        with open(self.overrides_path, 'r', encoding='utf-8') as f:
            self.overrides = json.load(f)
        
        return self.overrides
    
    def validate_workflow(self, workflow: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate workflow.json has required keys.
        
        Args:
            workflow: Workflow dict to validate (uses self.workflow if None)
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        if workflow is None:
            workflow = self.workflow
        
        if workflow is None:
            raise ValueError("No workflow loaded. Call load_workflow() first.")
        
        required_keys = ["workflow_name", "agents"]
        
        for key in required_keys:
            if key not in workflow:
                raise ValueError(f"Missing required key in workflow.json: {key}")
        
        # Validate agents structure
        if not isinstance(workflow["agents"], list):
            raise ValueError("'agents' must be a list")
        
        if len(workflow["agents"]) == 0:
            raise ValueError("Workflow must have at least one agent")
        
        # Validate each agent has required fields
        agent_required_fields = ["name", "class", "dependencies"]
        
        for i, agent in enumerate(workflow["agents"]):
            for field in agent_required_fields:
                if field not in agent:
                    raise ValueError(
                        f"Agent {i} ({agent.get('name', 'unknown')}) missing required field: {field}"
                    )
        
        return True
    
    def merge_overrides(self) -> Dict[str, Any]:
        """
        Merge overrides.json into workflow.json.
        
        Returns:
            Merged workflow configuration
        """
        if self.workflow is None:
            self.load_workflow()
        
        if self.overrides is None:
            self.load_overrides()
        
        merged = self.workflow.copy()
        
        # Apply overrides at agent level
        if "overrides" in self.overrides and self.overrides["overrides"]:
            agent_overrides = self.overrides["overrides"]
            
            # Create a map of agent names to indices
            agent_map = {agent["name"]: i for i, agent in enumerate(merged["agents"])}
            
            # Apply overrides to matching agents
            for agent_name, override_config in agent_overrides.items():
                if agent_name in agent_map:
                    agent_idx = agent_map[agent_name]
                    # Deep merge override config into agent config
                    merged["agents"][agent_idx] = self._deep_merge(
                        merged["agents"][agent_idx],
                        override_config
                    )
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_workflow(self, apply_overrides: bool = True) -> Dict[str, Any]:
        """
        Get the complete workflow configuration.
        
        Args:
            apply_overrides: Whether to merge overrides.json
            
        Returns:
            Complete workflow configuration
        """
        if self.workflow is None:
            self.load_workflow()
        
        if apply_overrides:
            workflow = self.merge_overrides()
        else:
            workflow = self.workflow
        
        self.validate_workflow(workflow)
        
        return workflow
    
    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent configuration dictionary, or None if not found
        """
        workflow = self.get_workflow()
        
        for agent in workflow["agents"]:
            if agent["name"] == agent_name:
                return agent
        
        return None
    
    def get_agent_order(self) -> list[str]:
        """
        Get ordered list of agent names based on dependencies.
        
        Returns:
            List of agent names in execution order
        """
        workflow = self.get_workflow()
        agents = workflow["agents"]
        
        # Build dependency graph
        agent_map = {agent["name"]: agent for agent in agents}
        visited = set()
        result = []
        
        def visit(agent_name: str):
            """Topological sort helper."""
            if agent_name in visited:
                return
            
            agent = agent_map.get(agent_name)
            if agent:
                for dep in agent.get("dependencies", []):
                    visit(dep)
            
            visited.add(agent_name)
            result.append(agent_name)
        
        for agent in agents:
            visit(agent["name"])
        
        return result

