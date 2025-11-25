"""
Overrides Manager: Handles applying approved recommendations to overrides.json.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class OverridesManager:
    """
    Manages workflow configuration overrides.
    
    Handles:
    - Loading overrides.json
    - Applying recommendations
    - Merging overrides with workflow.json
    """
    
    def __init__(self, overrides_path: str = "./configs/overrides.json"):
        """
        Initialize overrides manager.
        
        Args:
            overrides_path: Path to overrides.json file
        """
        self.overrides_path = Path(overrides_path)
        self.overrides = self._load_overrides()
    
    def _load_overrides(self) -> Dict[str, Any]:
        """
        Load overrides.json file.
        
        Returns:
            Overrides dictionary
        """
        if not self.overrides_path.exists():
            return {
                "workflow_name": "prospect_to_lead_v1",
                "applied_at": None,
                "overrides": {}
            }
        
        try:
            with open(self.overrides_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load overrides.json: {str(e)}")
    
    def save_overrides(self) -> None:
        """Save overrides to file."""
        try:
            self.overrides_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.overrides_path, 'w', encoding='utf-8') as f:
                json.dump(self.overrides, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"Failed to save overrides.json: {str(e)}")
    
    def apply_recommendation(
        self,
        field: str,
        new_value: Any,
        agent_name: Optional[str] = None
    ) -> None:
        """
        Apply a recommendation to overrides.
        
        Args:
            field: Field path (e.g., "scoring.weights.fit_score")
            new_value: New value to apply
            agent_name: Optional agent name (if not in field path)
        """
        # Parse field path (e.g., "scoring.weights.fit_score")
        parts = field.split('.')
        
        # Initialize overrides structure
        if "overrides" not in self.overrides:
            self.overrides["overrides"] = {}
        
        # Determine agent name from field or parameter
        if not agent_name:
            # Try to extract from field path (first part is usually agent name)
            agent_name = parts[0] if len(parts) > 0 else None
        
        if not agent_name:
            raise ValueError(f"Cannot determine agent name from field: {field}")
        
        # Initialize agent override if needed
        if agent_name not in self.overrides["overrides"]:
            self.overrides["overrides"][agent_name] = {}
        
        # Build nested structure
        current = self.overrides["overrides"][agent_name]
        
        # Skip first part (agent name) if it's in the path
        path_parts = parts[1:] if parts[0] == agent_name else parts
        
        # Navigate/create nested structure
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the value
        final_key = path_parts[-1] if path_parts else parts[-1]
        current[final_key] = new_value
        
        # Update timestamp
        from datetime import datetime
        self.overrides["applied_at"] = datetime.utcnow().isoformat()
        
        # Save to file
        self.save_overrides()
    
    def get_overrides(self) -> Dict[str, Any]:
        """Get current overrides."""
        return self.overrides
    
    def clear_overrides(self) -> None:
        """Clear all overrides."""
        self.overrides = {
            "workflow_name": "prospect_to_lead_v1",
            "applied_at": None,
            "overrides": {}
        }
        self.save_overrides()
    
    def get_agent_overrides(self, agent_name: str) -> Dict[str, Any]:
        """
        Get overrides for a specific agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Agent overrides dictionary
        """
        return self.overrides.get("overrides", {}).get(agent_name, {})

