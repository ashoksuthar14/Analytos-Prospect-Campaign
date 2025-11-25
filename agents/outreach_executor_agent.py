"""
OutreachExecutorAgent: Sends outreach emails via SendGrid or Apollo.
"""

from typing import Dict, Any, List
from datetime import datetime
from uuid import uuid4
from agents.base_agent import BaseAgent
from tools.sendgrid_api import SendGridAPI
from tools.apollo_api import ApolloAPI
from configs.secrets_provider import SecretsProvider
from database.db_service import DatabaseService


class OutreachExecutorAgent(BaseAgent):
    """
    Agent that sends outreach emails.
    
    Supports:
    - SendGrid API
    - Apollo Send API (fallback)
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize OutreachExecutorAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize API clients
        tool_config = config.get("tool_config", {})
        primary = tool_config.get("primary", "sendgrid_api")
        fallback = tool_config.get("fallback", "apollo_send_api")
        
        self.sendgrid_api = None
        self.apollo_api = None
        
        if primary == "sendgrid_api" or fallback == "sendgrid_api":
            sendgrid_key = secrets_provider.get_sendgrid_api_key()
            from_email = secrets_provider.get_sendgrid_from_email()
            from_name = secrets_provider.get_sendgrid_from_name()
            if sendgrid_key and from_email:
                try:
                    self.sendgrid_api = SendGridAPI(sendgrid_key, from_email, from_name or "Outreach Team")
                except ImportError:
                    # SendGrid not installed
                    pass
        
        if primary == "apollo_send_api" or fallback == "apollo_send_api":
            apollo_key = secrets_provider.get_apollo_api_key()
            if apollo_key:
                self.apollo_api = ApolloAPI(apollo_key)
        
        self.db_service = DatabaseService()
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process email sending.
        
        Args:
            input_data: Input data with messages array
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with sent 'messages' array
        """
        messages = input_data.get("messages")
        if isinstance(messages, dict):
            messages = messages.get("messages", [])
        if messages is None:
            messages = []
        elif not isinstance(messages, list):
            messages = []

        tool_config = self.config.get("tool_config", {})
        primary = tool_config.get("primary", "sendgrid_api")
        fallback = tool_config.get("fallback", "apollo_send_api")

        # Get leads from state to map lead_id to email
        leads = self._get_leads_from_state(state)

        # Surface human-in-the-loop decision if provided
        review_input = self._extract_human_review(state)
        review_notes = review_input.get("notes") if isinstance(review_input, dict) else None
        approval = review_input.get("approval") if isinstance(review_input, dict) else None

        if approval is False:
            failed_messages = [
                {
                    "message": message,
                    "error": "Send blocked by human reviewer"
                }
                for message in messages
            ]

            result = {
                "messages": [],
                "total_sent": 0,
                "total_failed": len(failed_messages),
                "failed_messages": failed_messages,
                "status": "blocked"
            }

            if review_notes:
                result["review_notes"] = review_notes

            return result

        if not messages:
            result = {
                "messages": [],
                "total_sent": 0,
                "total_failed": 0,
                "failed_messages": [],
                "status": "no_messages"
            }
            if review_notes:
                result["review_notes"] = review_notes
            return result

        sent_messages = []
        failed_messages = []

        for message in messages:
            lead_id = message.get("lead_id")
            lead = self._find_lead(leads, lead_id)
            
            if not lead:
                failed_messages.append({
                    "message": message,
                    "error": "Lead not found"
                })
                continue
            
            to_email = lead.get("contact_email")
            if not to_email:
                failed_messages.append({
                    "message": message,
                    "error": "No email address"
                })
                continue
            message_id = message.get("message_id") or str(uuid4())
            message["message_id"] = message_id
            draft_payload = {
                "message_id": message_id,
                "subject": message.get("subject", ""),
                "body": message.get("body", ""),
                "personalization_used": message.get("personalization_used", []),
                "status": "draft",
                "provider": primary
            }
            self.db_service.create_message(run_id, lead_id, draft_payload)

            # Try primary API first
            result = None
            error = None
            
            try:
                if primary == "sendgrid_api" and self.sendgrid_api:
                    result = self.sendgrid_api.send_email(
                        to_email=to_email,
                        subject=message.get("subject", ""),
                        body=message.get("body", ""),
                        from_email=tool_config.get("from_email"),
                        from_name=tool_config.get("from_name")
                    )
                elif primary == "apollo_send_api" and self.apollo_api:
                    result = self.apollo_api.send_email(
                        to_email=to_email,
                        subject=message.get("subject", ""),
                        body=message.get("body", ""),
                        from_email=tool_config.get("from_email"),
                        from_name=tool_config.get("from_name")
                    )
            except Exception as e:
                error = str(e)
                if run_id and self.logger:
                    self.logger.log_tool_call(
                        run_id=run_id,
                        agent_name=self.name,
                        tool_name=primary,
                        tool_input={"to_email": to_email},
                        tool_output={"error": error}
                    )
            
            # Try fallback if primary failed
            if not result and error:
                try:
                    if fallback == "sendgrid_api" and self.sendgrid_api:
                        result = self.sendgrid_api.send_email(
                            to_email=to_email,
                            subject=message.get("subject", ""),
                            body=message.get("body", "")
                        )
                    elif fallback == "apollo_send_api" and self.apollo_api:
                        result = self.apollo_api.send_email(
                            to_email=to_email,
                            subject=message.get("subject", ""),
                            body=message.get("body", "")
                        )
                except Exception as e:
                    error = str(e)
            
            if result:
                provider_message_id = result.get("message_id")
                sent_at_dt = datetime.utcnow()
                self.db_service.update_message_status(
                    message_id=message_id,
                    status="sent",
                    provider_message_id=provider_message_id,
                    sent_at=sent_at_dt
                )
                sent_messages.append({
                    "message_id": message_id,
                    "lead_id": lead_id,
                    "subject": message.get("subject", ""),
                    "body": message.get("body", ""),
                    "personalization_used": message.get("personalization_used", []),
                    "status": result.get("status", "sent"),
                    "sent_at": sent_at_dt.isoformat(),
                    "provider": result.get("provider", primary)
                })
            else:
                self.db_service.update_message_status(
                    message_id=message_id,
                    status="failed"
                )
                failed_messages.append({
                    "message": message,
                    "error": error or "Unknown error"
                })
        
        status_value = "completed"
        if failed_messages and sent_messages:
            status_value = "partial"
        elif failed_messages and not sent_messages:
            status_value = "failed"

        result = {
            "messages": sent_messages,
            "total_sent": len(sent_messages),
            "total_failed": len(failed_messages),
            "failed_messages": failed_messages,
            "status": status_value
        }

        if review_notes:
            result["review_notes"] = review_notes

        return result
    
    def _get_leads_from_state(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get leads from campaign state."""
        # Check prospect_search output
        prospect_output = state.get("prospect_search_output", {})
        if prospect_output.get("leads"):
            return prospect_output["leads"]
        
        # Prefer scoring output (has scores + IDs)
        scoring_output = state.get("scoring_output", {})
        if scoring_output.get("leads"):
            return scoring_output["leads"]
        if scoring_output.get("ranked_leads"):
            return scoring_output["ranked_leads"]
        
        # Check data_enrichment output
        enrichment_output = state.get("data_enrichment_output", {})
        if enrichment_output.get("leads"):
            return enrichment_output["leads"]
        
        return []
    
    def _find_lead(self, leads: List[Dict[str, Any]], lead_id: str) -> Dict[str, Any]:
        """Find lead by lead_id."""
        if not lead_id:
            return {}
        
        lead_id_lower = str(lead_id).lower()
        
        for lead in leads:
            db_lead_id = str(lead.get("lead_id") or "").lower()
            company_name = (lead.get("company_name") or "").lower()
            email = (lead.get("contact_email") or "").lower()
            expected_id = f"{company_name}_{email}" if company_name or email else ""
            
            if db_lead_id and db_lead_id == lead_id_lower:
                return lead
            if expected_id and lead_id_lower == expected_id:
                return lead
            if company_name and lead_id_lower == company_name:
                return lead
            if email and lead_id_lower == email:
                return lead
            if company_name and lead_id_lower in company_name:
                return lead
            if email and lead_id_lower in email:
                return lead
        
        return {}

    def _extract_human_review(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract human-in-the-loop payload for this agent."""
        human_inputs = state.get("human_inputs", {})
        if not isinstance(human_inputs, dict):
            return {}

        review_payload = human_inputs.get(self.name)
        if isinstance(review_payload, dict):
            payload = review_payload.get("input") if isinstance(review_payload.get("input"), dict) else review_payload
            return payload if isinstance(payload, dict) else {}

        return {}

