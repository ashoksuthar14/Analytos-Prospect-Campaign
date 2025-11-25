"""
ProspectSearchAgent: Discovers B2B prospects matching ICP criteria.
"""

from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from tools.apollo_api import ApolloAPI
from tools.explorium_api import ExporiumAPI
from configs.secrets_provider import SecretsProvider
from utils.detailed_logger import DetailedLogger
import time


class ProspectSearchAgent(BaseAgent):
    """
    Agent that discovers prospects using Apollo API.
    
    Searches for companies/contacts matching ICP criteria:
    - Industry, location, revenue range
    - Employee count
    - Tech stack
    - Signals (recent funding, hiring, etc.)
    
    Note: Uses Apollo API with email reveal enabled to get actual email addresses.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize ProspectSearchAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize detailed logger for continuous monitoring
        self.detailed_logger = DetailedLogger()
        
        # Initialize Apollo API as primary
        self.apollo_api = None
        apollo_key = secrets_provider.get_apollo_api_key()
        if apollo_key:
            self.apollo_api = ApolloAPI(apollo_key)
        else:
            raise ValueError("Apollo API key is required. Please set APOLLO_API_KEY in .env file")
        
        # Initialize Explorium API as fallback for email enrichment
        self.explorium_api = None
        explorium_key = secrets_provider.get_explorium_api_key()
        if explorium_key:
            self.explorium_api = ExporiumAPI(explorium_key)
            self.detailed_logger.log_agent_step("init", self.name, "Explorium API initialized as fallback", {
                "has_explorium": True
            })
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process prospect search.
        
        Args:
            input_data: Input data with ICP criteria
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with 'leads' array
        """
        start_time = time.time()
        
        # Log agent start
        self.detailed_logger.log_agent_start(run_id or "no_run_id", self.name, input_data)
        
        icp = input_data.get("icp", {})
        tool_config = self.config.get("tool_config", {})
        max_results = tool_config.get("max_results", 50)
        
        # Extract ICP parameters
        industry = icp.get("industry", [])
        location = icp.get("location")
        
        # Handle revenue - check both 'revenue' and 'revenue_range' keys for compatibility
        revenue_range = icp.get("revenue", icp.get("revenue_range", {}))
        
        # Handle employee count
        employee_count = icp.get("employee_count", {})
        
        tech_stack = icp.get("tech_stack", [])
        
        # Get signals - check both in input_data directly and within icp for compatibility
        signals = input_data.get("signals", icp.get("signals", {}))
        
        # Log search parameters
        self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, "Extracted ICP criteria", {
            "industry": industry,
            "location": location,
            "max_results": max_results,
            "has_revenue_range": bool(revenue_range),
            "has_employee_count": bool(employee_count),
            "signals": signals,
            "revenue_min": revenue_range.get("min"),
            "revenue_max": revenue_range.get("max"),
            "employee_min": employee_count.get("min"),
            "employee_max": employee_count.get("max")
        })
        
        # Print to console for easy debugging
        print(f"\n{'='*80}")
        print(f"🎯 ICP CRITERIA FROM FORM:")
        print(f"  Industry: {industry}")
        print(f"  Location: {location}")
        print(f"  Employees: {employee_count.get('min')} - {employee_count.get('max')}")
        print(f"  Revenue: ${revenue_range.get('min'):,} - ${revenue_range.get('max'):,}")
        print(f"  Max Results: {max_results}")
        print(f"{'='*80}\n")
        
        leads = []
        error = None
        
        # Use Apollo API only (Clay removed)
        if not self.apollo_api:
            return {
                "leads": [],
                "status": "error",
                "error": "Apollo API not initialized. Please check APOLLO_API_KEY in .env file"
            }
        
        try:
            # Step 1: Search for people (this finds them but doesn't reveal emails)
            # Fetch MORE leads initially (5x target) to ensure we have enough with emails after strict filtering
            fetch_multiplier = 5  # Fetch 5x the target to account for leads without emails + strict ICP filtering
            initial_fetch_count = max_results * fetch_multiplier
            
            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, "Calling Apollo search", {
                "endpoint": "/mixed_people/search",
                "target_leads": max_results,
                "fetching_leads": initial_fetch_count,
                "reason": "Fetching extra leads to filter for valid emails"
            })
            
            leads = self.apollo_api.search_companies(
                industry=industry if isinstance(industry, list) else [industry] if industry else None,
                location=location,
                revenue_min=revenue_range.get("min"),
                revenue_max=revenue_range.get("max"),
                employee_min=employee_count.get("min"),
                employee_max=employee_count.get("max"),
                tech_stack=tech_stack,
                signals=signals,
                max_results=initial_fetch_count  # Fetch more initially
            )
            
            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, "Apollo search completed", {
                "leads_found": len(leads),
                "target_leads": max_results,
                "sample_lead": leads[0].get("company_name") if leads else None
            })
            
            # Step 2: Reveal real emails using /people/match endpoint
            # Apollo search doesn't reveal emails - we need to match separately
            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, "Starting email reveal process", {
                "total_leads": len(leads),
                "target_leads_with_emails": max_results
            })
            
            enriched_leads = []
            leads_with_emails = []  # Track leads that have valid emails
            for idx, lead in enumerate(leads, 1):
                email = lead.get("contact_email", "")
                
                # Check if email is already valid
                email_is_valid = (
                    email and 
                    email.strip() and 
                    "email_not_unlocked" not in str(email) and 
                    "@domain.com" not in str(email) and
                    "@" in email and 
                    "." in email.split("@")[1]
                )
                
                # If email is already valid, add to leads_with_emails and continue
                if email_is_valid:
                    leads_with_emails.append(lead)
                    enriched_leads.append(lead)
                    self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Lead {idx} already has valid email", {
                        "contact_name": lead.get("contact_name"),
                        "email": email[:20] + "...",
                        "leads_with_emails": len(leads_with_emails)
                    })
                    
                    # If we have enough leads with emails, stop processing
                    if len(leads_with_emails) >= max_results:
                        self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Reached target of {max_results} leads with emails", {
                            "leads_with_emails": len(leads_with_emails),
                            "processed_leads": idx,
                            "skipped_leads": len(leads) - idx
                        })
                        break
                    continue
                
                # If email is locked, try to match person and reveal email
                if not email or "email_not_unlocked" in str(email) or "@domain.com" in str(email):
                    try:
                        # Parse name into first/last
                        contact_name = lead.get("contact_name", "")
                        domain = lead.get("domain", "")
                        
                        self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"Attempting email reveal for lead {idx}", {
                            "contact_name": contact_name,
                            "domain": domain,
                            "current_email": str(email)[:30]
                        })
                        
                        if contact_name and domain:
                            # Split name
                            name_parts = contact_name.strip().split()
                            first_name = name_parts[0] if len(name_parts) > 0 else ""
                            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else name_parts[0] if len(name_parts) == 1 else ""
                            
                            # Use the CORRECT endpoint to reveal email
                            real_email = self.apollo_api.match_person_reveal_email(
                                first_name=first_name,
                                last_name=last_name,
                                domain=domain
                            )
                            
                            if real_email:
                                lead["contact_email"] = real_email
                                lead["email_source"] = "apollo_match_revealed"
                                
                                self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Email revealed for lead {idx}", {
                                    "contact_name": contact_name,
                                    "revealed_email": real_email[:20] + "...",
                                    "source": "apollo",
                                    "leads_with_emails": len(leads_with_emails) + 1
                                })
                                
                                if run_id and self.logger:
                                    self.logger.log_tool_call(
                                        run_id=run_id,
                                        agent_name=self.name,
                                        tool_name="match_person_reveal_email",
                                        tool_input={"name": contact_name, "domain": domain},
                                        tool_output={"email": real_email[:20] + "..."}
                                    )
                                
                                # Add to leads_with_emails list
                                leads_with_emails.append(lead)
                                
                                # If we have enough leads with emails, we can stop early
                                if len(leads_with_emails) >= max_results:
                                    self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Reached target of {max_results} leads with emails", {
                                        "leads_with_emails": len(leads_with_emails),
                                        "processed_leads": idx,
                                        "skipped_leads": len(leads) - idx
                                    })
                                    break
                            else:
                                # Apollo failed, try Explorium as fallback
                                self.detailed_logger.log_decision(run_id or "no_run_id", self.name, f"❌ Apollo email reveal returned None for lead {idx}", 
                                    f"Apollo API returned None for {contact_name} @ {domain}")
                                
                                if self.explorium_api:
                                    try:
                                        self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"🔄 Trying Explorium fallback for lead {idx}", {
                                            "contact_name": contact_name,
                                            "domain": domain
                                        })
                                        
                                        # Clean domain safely (handle None)
                                        clean_domain = ""
                                        if domain and isinstance(domain, str):
                                            clean_domain = domain.replace("www.", "").replace("http://", "").replace("https://", "").strip()
                                        
                                        # Skip if no valid domain
                                        if not clean_domain:
                                            self.detailed_logger.log_decision(run_id or "no_run_id", self.name, f"⚠️ Skipping Explorium for lead {idx}", 
                                                f"No valid domain found for {contact_name}")
                                            continue
                                        
                                        # Try Explorium to match and reveal email
                                        explorium_data = self.explorium_api.match_prospect(
                                            first_name=first_name,
                                            last_name=last_name,
                                            company_domain=clean_domain
                                        )
                                        
                                        if explorium_data and explorium_data.get("email"):
                                            explorium_email = explorium_data.get("email")
                                            lead["contact_email"] = explorium_email
                                            lead["email_source"] = "explorium_fallback"
                                            
                                            # Also add any additional data from Explorium
                                            if explorium_data.get("title"):
                                                lead["title"] = explorium_data.get("title")
                                            if explorium_data.get("linkedin_url"):
                                                lead["linkedin_url"] = explorium_data.get("linkedin_url")
                                            
                                            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Explorium revealed email for lead {idx}", {
                                                "contact_name": contact_name,
                                                "revealed_email": explorium_email[:20] + "...",
                                                "source": "explorium",
                                                "leads_with_emails": len(leads_with_emails) + 1
                                            })
                                            
                                            # Add to leads_with_emails list
                                            leads_with_emails.append(lead)
                                            
                                            # If we have enough leads with emails, we can stop early
                                            if len(leads_with_emails) >= max_results:
                                                self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Reached target of {max_results} leads with emails", {
                                                    "leads_with_emails": len(leads_with_emails),
                                                    "processed_leads": idx,
                                                    "skipped_leads": len(leads) - idx
                                                })
                                                break
                                        else:
                                            self.detailed_logger.log_decision(run_id or "no_run_id", self.name, f"❌ Explorium also returned None for lead {idx}", 
                                                f"Both Apollo and Explorium failed for {contact_name} @ {domain}")
                                    except Exception as explorium_error:
                                        self.detailed_logger.log_agent_error(run_id or "no_run_id", self.name, explorium_error, {
                                            "step": "explorium_fallback",
                                            "lead": contact_name
                                        })
                    except Exception as enrich_error:
                        # Log but continue with lead
                        self.detailed_logger.log_agent_error(run_id or "no_run_id", self.name, enrich_error, {
                            "step": "email_reveal",
                            "lead": lead.get("company_name"),
                            "contact": lead.get("contact_name")
                        })
                        
                        if run_id and self.logger:
                            self.logger.log_tool_call(
                                run_id=run_id,
                                agent_name=self.name,
                                tool_name="match_person_reveal_email",
                                tool_input={"lead": lead.get("company_name")},
                                tool_output={"error": str(enrich_error)}
                            )
                
                # Check final email status after all attempts
                final_email = lead.get("contact_email", "")
                email_is_valid = (
                    final_email and 
                    final_email.strip() and 
                    "email_not_unlocked" not in str(final_email) and 
                    "@domain.com" not in str(final_email) and
                    "@" in final_email and 
                    "." in final_email.split("@")[1]
                )
                
                if email_is_valid:
                    # Lead has valid email, add it
                    enriched_leads.append(lead)
                    if lead not in leads_with_emails:
                        leads_with_emails.append(lead)
                    
                    # If we have enough leads with emails, stop processing
                    if len(leads_with_emails) >= max_results:
                        self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ Reached target of {max_results} leads with emails", {
                            "leads_with_emails": len(leads_with_emails),
                            "processed_leads": idx,
                            "skipped_leads": len(leads) - idx
                        })
                        break
                else:
                    # Lead doesn't have valid email, skip it
                    self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"⚠️ Skipping lead {idx} - no valid email after all attempts", {
                        "contact_name": lead.get("contact_name"),
                        "company": lead.get("company_name"),
                        "email": final_email[:30] if final_email else "None",
                        "email_status": "missing_or_invalid"
                    })
            
            # Filter to only keep leads with valid emails, up to max_results
            leads = leads_with_emails[:max_results]
            
            # Log how many leads were filtered out
            filtered_out = len(enriched_leads) - len(leads)
            if filtered_out > 0:
                self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"Filtered out {filtered_out} leads without valid emails", {
                    "original_count": len(enriched_leads),
                    "final_count": len(leads),
                    "filtered_out": filtered_out
                })
            
            # Log email reveal summary with source breakdown
            apollo_emails = sum(1 for l in leads if l.get("email_source") == "apollo_match_revealed")
            explorium_emails = sum(1 for l in leads if l.get("email_source") == "explorium_fallback")
            original_emails = sum(1 for l in leads if not l.get("email_source"))  # Leads that already had emails
            total_emails_revealed = apollo_emails + explorium_emails
            
            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, "Email reveal completed", {
                "total_leads_with_emails": len(leads),
                "target_leads": max_results,
                "emails_revealed": total_emails_revealed,
                "original_emails": original_emails,
                "apollo_success": apollo_emails,
                "explorium_success": explorium_emails,
                "all_leads_have_emails": len(leads) > 0 and all(l.get("contact_email") for l in leads)
            })
            
        except Exception as e:
            error = str(e)
            self.detailed_logger.log_agent_error(run_id or "no_run_id", self.name, e, {
                "step": "apollo_search",
                "icp": icp
            })
            
            if run_id and self.logger:
                self.logger.log_agent_error(
                    run_id=run_id,
                    agent_name=self.name,
                    error_data={"type": type(e).__name__, "message": str(e)}
                )
            # Return error details
            return {
                "leads": [],
                "status": "error",
                "error": f"Apollo API search failed: {error}"
            }
        
        duration_ms = (time.time() - start_time) * 1000
        
        if leads and leads[0].get("source") == "sample_dataset":
            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, "Using sample dataset leads fallback", {
                "leads_count": len(leads)
            })
        elif not leads:
            # Return empty results with warning
            self.detailed_logger.log_agent_complete(run_id or "no_run_id", self.name, {
                "leads_count": 0,
                "status": "no_results"
            }, duration_ms)
            
            return {
                "leads": [],
                "status": "no_results",
                "message": "No leads found with given criteria. Try adjusting ICP filters."
            }
        
        # Log successful completion
        self.detailed_logger.log_agent_complete(run_id or "no_run_id", self.name, {
            "leads_count": len(leads),
            "source": "apollo_api",
            "enriched": True
        }, duration_ms)
        
        # Store ICP in state for downstream agents (like scoring)
        if state is not None and isinstance(state, dict):
            state["icp"] = icp
        
        return {
            "leads": leads,
            "total_found": len(leads),
            "source": "apollo_api",
            "enriched": True,
            "icp": icp  # Pass ICP to downstream agents
        }

