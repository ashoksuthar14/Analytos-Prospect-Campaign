"""
ResponseTrackerAgent: Tracks email opens, clicks, replies, and meeting bookings.
"""

from typing import Dict, Any, List
from datetime import datetime
from agents.base_agent import BaseAgent
from tools.sendgrid_api import SendGridAPI
from tools.apollo_api import ApolloAPI
from configs.secrets_provider import SecretsProvider


class ResponseTrackerAgent(BaseAgent):
    """
    Agent that tracks email engagement.
    
    Tracks:
    - Opens
    - Clicks
    - Replies
    - Meeting bookings
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize ResponseTrackerAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize API clients
        tool_config = config.get("tool_config", {})
        self.sendgrid_api = None
        self.apollo_api = None
        
        sendgrid_key = secrets_provider.get_sendgrid_api_key()
        from_email = secrets_provider.get_sendgrid_from_email()
        from_name = secrets_provider.get_sendgrid_from_name()
        if sendgrid_key and from_email:
            try:
                self.sendgrid_api = SendGridAPI(sendgrid_key, from_email, from_name or "Outreach Team")
            except ImportError:
                pass
        
        apollo_key = secrets_provider.get_apollo_api_key()
        if apollo_key:
            self.apollo_api = ApolloAPI(apollo_key)
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process response tracking.
        
        Args:
            input_data: Input data with message_ids array
            state: Current workflow state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with 'responses' array
        """
        message_ids = input_data.get("message_ids", [])
        tool_config = self.config.get("tool_config", {})
        poll_interval_hours = tool_config.get("poll_interval_hours", 24)
        
        responses = []
        
        for msg_data in message_ids:
            # Handle both dict and string inputs
            if isinstance(msg_data, dict):
                message_id = msg_data.get("message_id")
                provider = msg_data.get("provider", "sendgrid")
            elif isinstance(msg_data, str):
                # If it's a string, treat it as the message_id
                message_id = msg_data
                provider = "sendgrid"
            else:
                # Skip invalid data types
                continue
            
            response_data = {
                "message_id": message_id,
                "opened": False,
                "opened_at": None,
                "clicked": False,
                "clicked_at": None,
                "replied": False,
                "replied_at": None,
                "meeting_scheduled": False,
                "meeting_at": None
            }
            
            # Track based on provider
            try:
                if provider == "sendgrid" and self.sendgrid_api:
                    # Get SendGrid stats
                    stats = self.sendgrid_api.get_email_stats(message_id=message_id)
                    if stats.get("opens", 0) > 0:
                        response_data["opened"] = True
                        response_data["opened_at"] = datetime.utcnow().isoformat()
                    if stats.get("clicks", 0) > 0:
                        response_data["clicked"] = True
                        response_data["clicked_at"] = datetime.utcnow().isoformat()
                
                elif provider == "apollo" and self.apollo_api:
                    # Apollo tracking would be done via webhooks or API
                    # For now, we'll use a placeholder
                    # In production, you'd set up webhooks to track these events
                    pass
                
            except Exception as e:
                # Log error but continue
                if run_id and self.logger:
                    self.logger.log_tool_call(
                        run_id=run_id,
                        agent_name=self.name,
                        tool_name=f"{provider}_tracking",
                        tool_input={"message_id": message_id},
                        tool_output={"error": str(e)}
                    )
            
            # Note: Replies and meetings would typically come from:
            # - Webhook callbacks from email providers
            # - Calendar integration (Calendly, etc.)
            # - Manual input
            # For now, we'll leave these as False
            
            responses.append(response_data)
        
        # Calculate metrics
        total = len(responses)
        opens = sum(1 for r in responses if r["opened"])
        clicks = sum(1 for r in responses if r["clicked"])
        replies = sum(1 for r in responses if r["replied"])
        meetings = sum(1 for r in responses if r["meeting_scheduled"])
        
        return {
            "responses": responses,
            "total": total,
            "opens": opens,
            "clicks": clicks,
            "replies": replies,
            "meetings": meetings,
            "open_rate": opens / total if total > 0 else 0,
            "reply_rate": replies / total if total > 0 else 0,
            "meeting_rate": meetings / total if total > 0 else 0
        }

