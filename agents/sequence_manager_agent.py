"""
SequenceManagerAgent: Manages adding contacts to Apollo sequences.
"""

from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent
from tools.apollo_api import ApolloAPI
from configs.secrets_provider import SecretsProvider
from utils.detailed_logger import DetailedLogger
import time


class SequenceManagerAgent(BaseAgent):
    """
    Agent that manages Apollo sequences and adds contacts to them.
    
    This agent:
    - Searches for available sequences in Apollo
    - Adds synced contacts to selected sequences
    - Handles sequence membership rules
    - Provides detailed logging
    
    Runs after contacts are synced to Apollo.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize SequenceManagerAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize detailed logger
        self.detailed_logger = DetailedLogger()
        
        # Initialize Apollo API
        self.apollo_api = None
        apollo_key = secrets_provider.get_apollo_api_key()
        if apollo_key:
            self.apollo_api = ApolloAPI(apollo_key)
            self.detailed_logger.log_agent_step("init", self.name, "Apollo API initialized", {
                "has_apollo": True
            })
        else:
            raise ValueError("Apollo API key is required for sequence management")
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process adding contacts to sequences.
        
        Args:
            input_data: Input data with leads array (must have apollo_contact_id)
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with sequence assignment results
        """
        start_time = time.time()
        
        # Log agent start
        self.detailed_logger.log_agent_start(run_id or "no_run_id", self.name, input_data)
        
        leads = input_data.get("leads")
        
        # Unwrap common containers
        if isinstance(leads, dict):
            for candidate_key in ("leads", "ranked_leads", "results", "data"):
                candidate = leads.get(candidate_key)
                if isinstance(candidate, list):
                    leads = candidate
                    break
            else:
                leads = []
        
        # Handle None or empty leads
        if leads is None or not isinstance(leads, list):
            leads = list(leads) if leads else []
        
        if not leads:
            return {
                "leads": [],
                "sequence_id": None,
                "added_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "status": "no_leads",
                "message": "No leads to add to sequence"
            }
        
        tool_config = self.config.get("tool_config", {})
        sequence_id = tool_config.get("sequence_id")  # Can be set in campaign config
        auto_add = tool_config.get("auto_add_to_sequence", False)  # Auto-add if sequence_id is set
        
        # If no sequence_id configured, return leads without adding to sequence
        if not sequence_id:
            self.detailed_logger.log_agent_step(
                run_id or "no_run_id",
                self.name,
                "No sequence_id configured, skipping sequence assignment",
                {"auto_add": auto_add}
            )
            return {
                "leads": leads,
                "sequence_id": None,
                "added_count": 0,
                "failed_count": 0,
                "skipped_count": len(leads),
                "status": "skipped",
                "message": "No sequence configured for auto-add"
            }
        
        # Extract contact IDs from leads
        contact_ids = []
        lead_map = {}  # Map contact_id to lead
        
        for lead in leads:
            apollo_contact_id = lead.get("apollo_contact_id")
            if apollo_contact_id:
                contact_ids.append(apollo_contact_id)
                lead_map[apollo_contact_id] = lead
        
        if not contact_ids:
            return {
                "leads": leads,
                "sequence_id": sequence_id,
                "added_count": 0,
                "failed_count": 0,
                "skipped_count": len(leads),
                "status": "no_contact_ids",
                "message": "No contacts with apollo_contact_id found"
            }
        
        self.detailed_logger.log_agent_step(
            run_id or "no_run_id",
            self.name,
            f"Adding {len(contact_ids)} contacts to sequence {sequence_id}",
            {
                "sequence_id": sequence_id,
                "contact_count": len(contact_ids),
                "auto_add": auto_add
            }
        )
        
        # Add contacts to sequence
        try:
            # Get sequence behavior settings from config
            sequence_settings = tool_config.get("sequence_settings", {})
            
            response = self.apollo_api.add_contacts_to_sequence(
                sequence_id=sequence_id,
                contact_ids=contact_ids,
                sequence_active_in_other_campaigns=sequence_settings.get("allow_active_in_other", False),
                sequence_finished_in_other_campaigns=sequence_settings.get("allow_finished_in_other", True),
                sequence_no_email=sequence_settings.get("allow_no_email", False),
                sequence_unsubscribed_email=sequence_settings.get("allow_unsubscribed", False)
            )
            
            # Process response
            added_contacts = response.get("contacts", [])
            emailer_campaign = response.get("emailer_campaign", {})
            
            added_count = 0
            failed_count = 0
            results = []
            
            for contact in added_contacts:
                contact_id = contact.get("id")
                status = contact.get("status", "unknown")
                lead = lead_map.get(contact_id, {})
                
                if status == "added" or status == "success":
                    added_count += 1
                    results.append({
                        "contact_id": contact_id,
                        "company_name": lead.get("company_name"),
                        "contact_email": lead.get("contact_email"),
                        "status": "added",
                        "sequence_id": sequence_id
                    })
                    
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"✅ Added contact to sequence: {lead.get('contact_name')}",
                        {"contact_id": contact_id, "sequence_id": sequence_id}
                    )
                else:
                    failed_count += 1
                    error_msg = contact.get("error", "Unknown error")
                    results.append({
                        "contact_id": contact_id,
                        "company_name": lead.get("company_name"),
                        "contact_email": lead.get("contact_email"),
                        "status": "failed",
                        "error": error_msg
                    })
                    
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"❌ Failed to add contact: {error_msg}",
                        {"contact_id": contact_id, "error": error_msg}
                    )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            output_data = {
                "leads": leads,
                "sequence_id": sequence_id,
                "sequence_name": emailer_campaign.get("name"),
                "added_count": added_count,
                "failed_count": failed_count,
                "skipped_count": 0,
                "results": results,
                "status": "completed",
                "message": f"Added {added_count}/{len(contact_ids)} contacts to sequence"
            }
            
            self.detailed_logger.log_agent_complete(
                run_id or "no_run_id",
                self.name,
                output_data,
                duration_ms=duration_ms
            )
            
            return output_data
            
        except Exception as e:
            error_msg = str(e)
            failed_count = len(contact_ids)
            
            self.detailed_logger.log_agent_error(
                run_id or "no_run_id",
                self.name,
                e,
                {
                    "sequence_id": sequence_id,
                    "contact_count": len(contact_ids),
                    "step": "add_to_sequence"
                }
            )
            
            return {
                "leads": leads,
                "sequence_id": sequence_id,
                "added_count": 0,
                "failed_count": failed_count,
                "skipped_count": 0,
                "status": "failed",
                "error": error_msg,
                "message": f"Failed to add contacts to sequence: {error_msg}"
            }
    
    def search_sequences(self, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for available sequences in Apollo.
        
        Args:
            search_query: Optional keyword to filter sequences
            
        Returns:
            List of sequence dictionaries
        """
        try:
            response = self.apollo_api.search_sequences(q_name=search_query, per_page=100)
            sequences = response.get("emailer_campaigns", [])
            
            # Simplify sequence data for frontend
            simplified = []
            for seq in sequences:
                simplified.append({
                    "id": seq.get("id"),
                    "name": seq.get("name"),
                    "active": seq.get("active", False),
                    "num_contacts": seq.get("num_contacts", 0),
                    "num_steps": seq.get("num_steps", 0),
                    "created_at": seq.get("created_at")
                })
            
            return simplified
            
        except Exception as e:
            self.detailed_logger.log_agent_error(
                "no_run_id",
                self.name,
                e,
                {"step": "search_sequences"}
            )
            return []

