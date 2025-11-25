"""
ApolloContactSyncAgent: Syncs scored leads to Apollo as contacts.
"""

from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent
from tools.apollo_api import ApolloAPI
from configs.secrets_provider import SecretsProvider
from utils.detailed_logger import DetailedLogger
import time


class ApolloContactSyncAgent(BaseAgent):
    """
    Agent that syncs leads to Apollo as contacts.
    
    This agent:
    - Takes scored leads as input
    - Creates contacts in Apollo for each lead
    - Stores Apollo contact IDs
    - Handles deduplication
    - Provides detailed logging
    
    Runs after ScoringAgent to ensure we only sync qualified leads.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize ApolloContactSyncAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize detailed logger for continuous monitoring
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
            raise ValueError("Apollo API key is required for contact sync")
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process lead sync to Apollo.
        
        This agent can operate in two modes:
        1. Initial sync: Creates contacts with basic lead data
        2. Message sync: Updates existing contacts with outreach message data
        
        Args:
            input_data: Input data with leads array
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with synced leads and sync results
        """
        start_time = time.time()
        
        # Log agent start
        self.detailed_logger.log_agent_start(run_id or "no_run_id", self.name, input_data)
        
        # Check if we're updating with message data
        messages = state.get("outreach_content_output", {}).get("messages", [])
        
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
                "synced_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "sync_results": [],
                "status": "no_leads",
                "message": "No leads to sync to Apollo"
            }
        
        tool_config = self.config.get("tool_config", {})
        min_score = tool_config.get("min_score_threshold", 0)  # Minimum score to sync
        max_leads = tool_config.get("max_leads_to_sync", None)  # Limit number of syncs
        
        # Filter leads by score if threshold is set
        filtered_leads = []
        for lead in leads:
            if not lead or not isinstance(lead, dict):
                continue
            
            score = lead.get("score", lead.get("fit_score", 0))
            if score >= min_score:
                filtered_leads.append(lead)
        
        # Limit number of leads if max_leads is set
        if max_leads and len(filtered_leads) > max_leads:
            filtered_leads = filtered_leads[:max_leads]
        
        self.detailed_logger.log_agent_step(
            run_id or "no_run_id",
            self.name,
            f"Syncing {len(filtered_leads)} leads to Apollo (filtered from {len(leads)})",
            {
                "total_leads": len(leads),
                "filtered_leads": len(filtered_leads),
                "min_score": min_score,
                "max_leads": max_leads
            }
        )
        
        # Sync each lead to Apollo
        synced_leads = []
        sync_results = []
        synced_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Build message lookup dictionary for quick access
        message_map = {}
        if messages and isinstance(messages, list):
            for msg in messages:
                lead_id = msg.get("lead_id")
                if lead_id:
                    message_map[lead_id] = msg
        
        for i, lead in enumerate(filtered_leads, 1):
            try:
                # Parse contact name
                contact_name = lead.get("contact_name", "")
                first_name, last_name = self._parse_name(contact_name)
                
                # Get required fields
                company_name = lead.get("company_name", "")
                email = lead.get("contact_email")
                lead_id = lead.get("lead_id")
                
                # Skip if missing required fields
                if not company_name or not first_name:
                    skipped_count += 1
                    sync_results.append({
                        "lead_id": lead_id,
                        "company_name": company_name,
                        "status": "skipped",
                        "reason": "Missing required fields (company_name or first_name)"
                    })
                    synced_leads.append(lead)  # Keep lead in output even if skipped
                    continue
                
                # Get message for this lead (if available)
                message_data = message_map.get(lead_id)
                
                # Prepare contact data (with message data if available)
                contact_data = self._prepare_contact_data(lead, first_name, last_name, message_data)
                
                self.detailed_logger.log_agent_step(
                    run_id or "no_run_id",
                    self.name,
                    f"Syncing lead {i}/{len(filtered_leads)}: {first_name} {last_name} @ {company_name}",
                    {
                        "lead_id": lead_id,
                        "company": company_name,
                        "email": email,
                        "has_email": bool(email),
                        "has_message": bool(message_data),
                        "has_apollo_id": bool(lead.get("apollo_contact_id"))
                    }
                )
                
                # Check if contact already exists (has apollo_contact_id from previous sync)
                existing_apollo_id = lead.get("apollo_contact_id")
                
                if existing_apollo_id and message_data:
                    # Update existing contact with message data
                    try:
                        typed_custom_fields = contact_data.get("typed_custom_fields", {})
                        if typed_custom_fields:
                            response = self.apollo_api.update_contact(
                                contact_id=existing_apollo_id,
                                typed_custom_fields=typed_custom_fields
                            )
                            
                            self.detailed_logger.log_agent_step(
                                run_id or "no_run_id",
                                self.name,
                                f"✅ Updated contact {existing_apollo_id} with message data",
                                {
                                    "apollo_contact_id": existing_apollo_id,
                                    "subject_length": len(message_data.get("subject", "")),
                                    "body_length": len(message_data.get("body", ""))
                                }
                            )
                    except Exception as update_error:
                        self.detailed_logger.log_agent_step(
                            run_id or "no_run_id",
                            self.name,
                            f"⚠️ Failed to update contact {existing_apollo_id}, will try full sync",
                            {"error": str(update_error)}
                        )
                        existing_apollo_id = None  # Fall through to create/sync
                
                # Create or sync contact in Apollo
                if not existing_apollo_id:
                    response = self.apollo_api.create_contact(**contact_data)
                else:
                    # Already updated above, just use existing data
                    response = {"contact": {"id": existing_apollo_id}}
                
                # Extract contact info from response
                if response and response.get("contact"):
                    apollo_contact = response.get("contact", {})
                    apollo_contact_id = apollo_contact.get("id")
                    
                    # Add Apollo contact ID to lead
                    lead_with_apollo_id = lead.copy()
                    lead_with_apollo_id["apollo_contact_id"] = apollo_contact_id
                    lead_with_apollo_id["apollo_synced_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    lead_with_apollo_id["apollo_sync_status"] = "success"
                    
                    synced_leads.append(lead_with_apollo_id)
                    synced_count += 1
                    
                    sync_results.append({
                        "lead_id": lead.get("lead_id"),
                        "company_name": company_name,
                        "contact_name": f"{first_name} {last_name}",
                        "apollo_contact_id": apollo_contact_id,
                        "status": "success"
                    })
                    
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"✅ Successfully synced: {first_name} {last_name}",
                        {
                            "apollo_contact_id": apollo_contact_id,
                            "email_status": apollo_contact.get("email_status")
                        }
                    )
                else:
                    # Unexpected response format
                    failed_count += 1
                    lead_copy = lead.copy()
                    lead_copy["apollo_sync_status"] = "failed"
                    lead_copy["apollo_sync_error"] = "Unexpected API response"
                    synced_leads.append(lead_copy)
                    
                    sync_results.append({
                        "lead_id": lead.get("lead_id"),
                        "company_name": company_name,
                        "status": "failed",
                        "error": "Unexpected API response format"
                    })
                
                # Rate limiting: small delay between requests
                time.sleep(0.5)
                
            except Exception as e:
                # Log error but continue with other leads
                error_msg = str(e)
                failed_count += 1
                
                lead_copy = lead.copy()
                lead_copy["apollo_sync_status"] = "failed"
                lead_copy["apollo_sync_error"] = error_msg
                synced_leads.append(lead_copy)
                
                sync_results.append({
                    "lead_id": lead.get("lead_id"),
                    "company_name": lead.get("company_name"),
                    "status": "failed",
                    "error": error_msg
                })
                
                self.detailed_logger.log_agent_error(
                    run_id or "no_run_id",
                    self.name,
                    e,
                    {
                        "lead_id": lead.get("lead_id"),
                        "company": lead.get("company_name"),
                        "step": "create_contact"
                    }
                )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Prepare output data
        output_data = {
            "leads": synced_leads,
            "synced_count": synced_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "total_processed": len(filtered_leads),
            "sync_results": sync_results,
            "status": "completed",
            "message": f"Synced {synced_count}/{len(filtered_leads)} leads to Apollo"
        }
        
        # Log completion
        self.detailed_logger.log_agent_complete(
            run_id or "no_run_id",
            self.name,
            output_data,
            duration_ms=duration_ms
        )
        
        # Return output data (already prepared above)
        return output_data
    
    def _parse_name(self, full_name: str) -> tuple:
        """
        Parse full name into first and last name.
        
        Args:
            full_name: Full name string
            
        Returns:
            Tuple of (first_name, last_name)
        """
        if not full_name:
            return ("Unknown", "Contact")
        
        parts = full_name.strip().split()
        if len(parts) == 0:
            return ("Unknown", "Contact")
        elif len(parts) == 1:
            return (parts[0], "Contact")
        else:
            return (parts[0], " ".join(parts[1:]))
    
    def _prepare_contact_data(
        self, 
        lead: Dict[str, Any], 
        first_name: str, 
        last_name: str,
        message_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare contact data for Apollo API.
        
        Args:
            lead: Lead dictionary
            first_name: Contact's first name
            last_name: Contact's last name
            message_data: Optional outreach message data with subject and body
            
        Returns:
            Dictionary with contact creation parameters
        """
        contact_data = {
            "first_name": first_name,
            "last_name": last_name,
            "organization_name": lead.get("company_name", ""),
            "run_dedupe": True  # Prevent duplicates
        }
        
        # Add optional fields
        email = lead.get("contact_email")
        if email:
            contact_data["email"] = email
        
        title = lead.get("contact_title") or lead.get("title")
        if title:
            contact_data["title"] = title
        
        # Build website URL from domain
        domain = lead.get("domain")
        if domain:
            domain = domain.replace("http://", "").replace("https://", "").replace("www.", "").strip("/")
            if domain:
                contact_data["website_url"] = f"https://{domain}"
        
        # Location
        location = lead.get("location")
        if location:
            contact_data["present_raw_address"] = location
        
        # Add message data to custom fields if available
        if message_data:
            typed_custom_fields = {}
            
            subject = message_data.get("subject")
            if subject:
                # Apollo custom fields format: {field_id: value}
                # We'll use descriptive keys that Apollo will create as custom fields
                typed_custom_fields["outreach_subject"] = subject
            
            body = message_data.get("body")
            if body:
                typed_custom_fields["outreach_body"] = body
            
            if typed_custom_fields:
                contact_data["typed_custom_fields"] = typed_custom_fields
                
                self.detailed_logger.log_agent_step(
                    "no_run_id",
                    self.name,
                    f"Adding message data to contact: subject={len(subject) if subject else 0} chars, body={len(body) if body else 0} chars",
                    {"has_subject": bool(subject), "has_body": bool(body)}
                )
        
        return contact_data

