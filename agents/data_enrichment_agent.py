"""
DataEnrichmentAgent: Enriches leads with firmographic and technographic data.
"""

from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from tools.apollo_api import ApolloAPI
from tools.openai_websearch import OpenAIWebSearch
from tools.hunter_api import HunterAPI
from configs.secrets_provider import SecretsProvider
from utils.detailed_logger import DetailedLogger
import time


class DataEnrichmentAgent(BaseAgent):
    """
    Agent that enriches leads with additional data.
    
    Enriches leads with:
    - LinkedIn URLs
    - Tech stack
    - Firmographics (founded year, headquarters, etc.)
    - Role details
    
    Uses 3-tier fallback:
    1. Apollo API (primary)
    2. Explorium API (if implemented)
    3. OpenAI Web Search (final fallback for missing fields)
    """
    
    def __init__(self, name: str, config: Dict[str, Any], secrets_provider: SecretsProvider, logger=None):
        """Initialize DataEnrichmentAgent."""
        super().__init__(name, config, secrets_provider, logger)
        
        # Initialize detailed logger for continuous monitoring
        self.detailed_logger = DetailedLogger()
        
        # Initialize API clients
        tool_config = config.get("tool_config", {})
        primary = tool_config.get("primary", "apollo_api")
        fallback = tool_config.get("fallback")

        self.apollo_api = None
        self.openai_websearch = None
        self.hunter_api = None

        if primary == "apollo_api" or fallback == "apollo_api" or fallback is None:
            apollo_key = secrets_provider.get_apollo_api_key()
            if apollo_key:
                self.apollo_api = ApolloAPI(apollo_key)
        
        # Initialize Hunter.io API for email finding
        hunter_key = secrets_provider.get_hunter_api_key()
        if hunter_key:
            self.hunter_api = HunterAPI(hunter_key)
            self.detailed_logger.log_agent_step("init", self.name, "Hunter.io API initialized for email finding", {
                "has_hunter": True
            })
        
        # Initialize OpenAI Web Search as final fallback
        openai_key = secrets_provider.get_openai_api_key()
        if openai_key:
            self.openai_websearch = OpenAIWebSearch(openai_key)
            self.detailed_logger.log_agent_step("init", self.name, "OpenAI Web Search initialized as final fallback", {
                "has_openai": True
            })
    
    def _process(
        self,
        input_data: Dict[str, Any],
        state: Dict[str, Any],
        run_id: str = None
    ) -> Dict[str, Any]:
        """
        Process lead enrichment.
        
        Args:
            input_data: Input data with leads array
            state: Current campaign state
            run_id: Run ID for logging
            
        Returns:
            Dictionary with enriched 'leads' array
        """
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

        # Ensure leads is a list
        if leads is None:
            leads = []
        elif not isinstance(leads, list):
            leads = list(leads) if leads else []
        
        tool_config = self.config.get("tool_config", {})
        primary = tool_config.get("primary", "apollo_api")
        fallback = tool_config.get("fallback", "apollo_api")
        
        enriched_leads = []
        emails_found_via_hunter = 0
        
        if not self.apollo_api:
            return {
                "leads": [],
                "total_enriched": 0,
                "enrichment_rate": 0,
                "status": "error",
                "message": "Apollo API key is not configured for enrichment"
            }

        # Handle empty leads list
        if not leads:
            return {
                "leads": [],
                "total_enriched": 0,
                "enrichment_rate": 0,
                "status": "no_leads",
                "message": "No leads to enrich"
            }
        
        for lead in leads:
            # Skip None or invalid leads
            if not lead or not isinstance(lead, dict):
                continue
                
            enriched_lead = lead.copy()
            domain = lead.get("domain")
            company_name = lead.get("company_name")
            email = lead.get("contact_email")
            contact_name = lead.get("contact_name", "")
            
            # Check if email is missing or invalid - use Hunter.io to find it
            email_missing_or_invalid = (
                not email or 
                email.strip() == "" or 
                "email_not_unlocked" in str(email) or 
                "@domain.com" in str(email)
            )
            
            # If domain is missing but we need it for Hunter.io, try to get it from Apollo first
            if email_missing_or_invalid and self.hunter_api and not domain and company_name and self.apollo_api:
                try:
                    # Try to get domain from Apollo company enrichment
                    temp_enrichment = self.apollo_api.enrich_company(company_name=company_name)
                    if temp_enrichment and temp_enrichment.get("domain"):
                        domain = temp_enrichment.get("domain")
                        # Clean domain
                        domain = domain.replace("http://", "").replace("https://", "").replace("www.", "").strip("/").split("/")[0]
                        enriched_lead["domain"] = domain
                        self.detailed_logger.log_agent_step(
                            run_id or "no_run_id",
                            self.name,
                            f"🔍 Extracted domain from Apollo for Hunter.io: {domain}",
                            {"company": company_name, "domain": domain}
                        )
                except Exception as e:
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"⚠️  Could not extract domain from Apollo for {company_name}: {str(e)}",
                        {"company": company_name}
                    )
            
            # Try Hunter.io to find missing emails
            if email_missing_or_invalid and self.hunter_api and contact_name:
                # Check if we have domain (required for Hunter.io)
                if not domain:
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"⚠️  Cannot use Hunter.io for {contact_name} @ {company_name}: domain is missing",
                        {
                            "contact": contact_name,
                            "company": company_name,
                            "has_email": bool(email),
                            "email": email
                        }
                    )
                elif domain:
                    try:
                        # Parse contact name to get first_name and last_name
                        name_parts = contact_name.strip().split()
                        first_name = name_parts[0] if name_parts else None
                        last_name = name_parts[-1] if len(name_parts) > 1 else None
                        
                        if first_name:
                            self.detailed_logger.log_agent_step(
                                run_id or "no_run_id",
                                self.name,
                                f"🔍 Using Hunter.io to find email for {contact_name} @ {company_name}",
                                {
                                    "domain": domain,
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "company": company_name
                                }
                            )
                            
                            # Find email using Hunter.io
                            hunter_result = self.hunter_api.find_email(
                                domain=domain,
                                first_name=first_name,
                                last_name=last_name,
                                company=company_name
                            )
                            
                            if hunter_result and hunter_result.get("email"):
                                found_email = hunter_result["email"]
                                email_score = hunter_result.get("score", 0)
                                
                                # Only use email if score is reasonable (>= 50)
                                if email_score >= 50:
                                    enriched_lead["contact_email"] = found_email
                                    email = found_email  # Update email variable for later use
                                    
                                    # Store Hunter.io metadata
                                    if not enriched_lead.get("enrichment"):
                                        enriched_lead["enrichment"] = {}
                                    enriched_lead["enrichment"]["hunter_data"] = {
                                        "email_score": email_score,
                                        "verification": hunter_result.get("verification", {}),
                                        "sources": hunter_result.get("sources", [])
                                    }
                                    
                                    emails_found_via_hunter += 1
                                    self.detailed_logger.log_agent_step(
                                        run_id or "no_run_id",
                                        self.name,
                                        f"✅ Hunter.io found email: {found_email} (score: {email_score})",
                                        {
                                            "email": found_email,
                                            "score": email_score,
                                            "verification_status": hunter_result.get("verification", {}).get("status")
                                        }
                                    )
                                else:
                                    self.detailed_logger.log_agent_step(
                                        run_id or "no_run_id",
                                        self.name,
                                        f"⚠️  Hunter.io found email but score too low: {email_score}",
                                        {
                                            "email": found_email,
                                            "score": email_score
                                        }
                                    )
                            else:
                                self.detailed_logger.log_agent_step(
                                    run_id or "no_run_id",
                                    self.name,
                                    f"❌ Hunter.io could not find email for {contact_name}",
                                    {
                                        "domain": domain,
                                        "first_name": first_name,
                                        "last_name": last_name
                                    }
                                )
                        else:
                            self.detailed_logger.log_agent_step(
                                run_id or "no_run_id",
                                self.name,
                                f"⚠️  Cannot parse contact name for Hunter.io: {contact_name}",
                                {
                                    "contact_name": contact_name,
                                    "company": company_name
                                }
                            )
                    except Exception as hunter_error:
                        self.detailed_logger.log_agent_error(
                            run_id or "no_run_id",
                            self.name,
                            hunter_error,
                            {
                                "step": "hunter_email_finder",
                                "contact": contact_name,
                                "company": company_name,
                                "domain": domain
                            }
                        )
                        # Continue with enrichment even if Hunter.io fails
            
            # Skip enrichment if email is locked/placeholder BUT keep the lead
            if email and ("email_not_unlocked" in str(email) or "@domain.com" in str(email)):
                # Email not revealed, try enrichment anyway with domain
                try:
                    if domain:
                        enrichment_data = self.apollo_api.enrich_company(domain=domain, company_name=company_name)
                        if enrichment_data:
                            enriched_lead["enrichment"] = enrichment_data
                            enriched_lead["enrichment_status"] = "enriched_via_domain"
                            
                            # Extract key fields to top level
                            if enrichment_data.get("industry"):
                                enriched_lead["industry"] = enrichment_data.get("industry")
                            if enrichment_data.get("revenue"):
                                enriched_lead["revenue"] = enrichment_data.get("revenue")
                            if enrichment_data.get("employee_count"):
                                enriched_lead["employee_count"] = enrichment_data.get("employee_count")
                        else:
                            enriched_lead["enrichment"] = {}
                            enriched_lead["enrichment_status"] = "enrichment_failed"
                    else:
                        enriched_lead["enrichment"] = {}
                        enriched_lead["enrichment_status"] = "skipped_no_domain"
                except Exception as e:
                    enriched_lead["enrichment"] = {}
                    enriched_lead["enrichment_status"] = "enrichment_error"
                    if run_id and self.logger:
                        self.logger.log_tool_call(
                            run_id=run_id,
                            agent_name=self.name,
                            tool_name="enrich_company",
                            tool_input={"domain": domain},
                            tool_output={"error": str(e)}
                        )
                enriched_leads.append(enriched_lead)
                continue
            
            enrichment_data = {}
            person_data = {}
            organization_data = {}
            apollo_success = False
            
            # STEP 1: Try Apollo Organization Enrichment FIRST to get correct domain
            # This is important because the domain might be wrong/auto-generated
            if self.apollo_api and domain:
                try:
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"🏢 Using Apollo Organization Enrichment for {company_name}",
                        {"domain": domain}
                    )
                    
                    organization_data = self.apollo_api.enrich_company(
                        domain=domain,
                        company_name=company_name
                    )
                    
                    if organization_data:
                        apollo_success = True
                        
                        # Update domain if organization enrichment returned a better one
                        org_domain = organization_data.get("domain")
                        original_domain = domain
                        if org_domain:
                            org_domain = org_domain.replace("http://", "").replace("https://", "").replace("www.", "").strip("/").split("/")[0]
                            if org_domain and org_domain != domain:
                                domain = org_domain
                                enriched_lead["domain"] = domain
                                self.detailed_logger.log_agent_step(
                                    run_id or "no_run_id",
                                    self.name,
                                    f"🔍 Updated domain from organization enrichment: {org_domain} (was: {original_domain})",
                                    {"original_domain": original_domain, "new_domain": org_domain}
                                )
                        
                        self.detailed_logger.log_agent_step(
                            run_id or "no_run_id",
                            self.name,
                            f"✅ Apollo Organization Enrichment successful for {company_name}",
                            {
                                "found_industry": bool(organization_data.get("industry")),
                                "found_revenue": bool(organization_data.get("revenue")),
                                "found_employees": bool(organization_data.get("employee_count")),
                                "found_tech_stack": bool(organization_data.get("tech_stack")),
                                "domain": domain
                            }
                        )
                except Exception as e:
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"⚠️  Apollo Organization Enrichment failed: {str(e)}",
                        {"domain": domain, "company": company_name}
                    )
            
            # STEP 2: Try Apollo People Enrichment (if we have person info)
            # Now we have the correct domain from organization enrichment
            if self.apollo_api:
                try:
                    # Parse contact name for person enrichment
                    contact_name = enriched_lead.get("contact_name", "")
                    name_parts = contact_name.strip().split() if contact_name else []
                    first_name = name_parts[0] if name_parts else None
                    last_name = name_parts[-1] if len(name_parts) > 1 else None
                    
                    # Try People Enrichment if we have person identifiers
                    if (email or (first_name and domain) or contact_name):
                        self.detailed_logger.log_agent_step(
                            run_id or "no_run_id",
                            self.name,
                            f"🔍 Using Apollo People Enrichment for {contact_name or 'contact'} @ {company_name}",
                            {
                                "has_email": bool(email),
                                "has_name": bool(contact_name),
                                "domain": domain
                            }
                        )
                        
                        person_data = self.apollo_api.enrich_person(
                            email=email,
                            domain=domain,
                            first_name=first_name,
                            last_name=last_name,
                            name=contact_name if contact_name and not (first_name and last_name) else None,
                            organization_name=company_name,
                            reveal_personal_emails=True
                        )
                        
                        if person_data:
                            apollo_success = True
                            
                            # If Apollo returned person data but no email, try additional methods
                            if not person_data.get("email") and (first_name and last_name):
                                # Try 1: Use match_person_reveal_email with current domain
                                if domain:
                                    try:
                                        revealed_email = self.apollo_api.match_person_reveal_email(
                                            first_name=first_name,
                                            last_name=last_name,
                                            domain=domain
                                        )
                                        if revealed_email:
                                            person_data["email"] = revealed_email
                                            self.detailed_logger.log_agent_step(
                                                run_id or "no_run_id",
                                                self.name,
                                                f"📧 Found email via Apollo match_person_reveal_email: {revealed_email}",
                                                {
                                                    "contact": contact_name,
                                                    "method": "match_person_reveal_email",
                                                    "domain": domain
                                                }
                                            )
                                    except Exception as e:
                                        pass  # Silently continue to next method
                            
                            self.detailed_logger.log_agent_step(
                                run_id or "no_run_id",
                                self.name,
                                f"✅ Apollo People Enrichment successful for {contact_name or 'contact'}",
                                {
                                    "found_email": bool(person_data.get("email")),
                                    "found_title": bool(person_data.get("title")),
                                    "found_linkedin": bool(person_data.get("linkedin_url"))
                                }
                            )
                            
                            # If Apollo didn't find email, try Hunter.io NOW with the correct domain
                            if not person_data.get("email") and self.hunter_api and domain and first_name and last_name:
                                try:
                                    self.detailed_logger.log_agent_step(
                                        run_id or "no_run_id",
                                        self.name,
                                        f"🔍 Apollo didn't find email, trying Hunter.io with correct domain: {domain}",
                                        {
                                            "contact": contact_name,
                                            "domain": domain,
                                            "first_name": first_name,
                                            "last_name": last_name
                                        }
                                    )
                                    
                                    hunter_result = self.hunter_api.find_email(
                                        domain=domain,
                                        first_name=first_name,
                                        last_name=last_name,
                                        company=company_name
                                    )
                                    
                                    if hunter_result and hunter_result.get("email"):
                                        found_email = hunter_result["email"]
                                        email_score = hunter_result.get("score", 0)
                                        
                                        if email_score >= 50:
                                            person_data["email"] = found_email
                                            enriched_lead["contact_email"] = found_email
                                            email = found_email
                                            
                                            if not enriched_lead.get("enrichment"):
                                                enriched_lead["enrichment"] = {}
                                            enriched_lead["enrichment"]["hunter_data"] = {
                                                "email_score": email_score,
                                                "verification": hunter_result.get("verification", {}),
                                                "sources": hunter_result.get("sources", [])
                                            }
                                            
                                            emails_found_via_hunter += 1
                                            self.detailed_logger.log_agent_step(
                                                run_id or "no_run_id",
                                                self.name,
                                                f"✅ Hunter.io found email after Apollo: {found_email} (score: {email_score})",
                                                {
                                                    "email": found_email,
                                                    "score": email_score,
                                                    "domain": domain
                                                }
                                            )
                                except Exception as e:
                                    self.detailed_logger.log_agent_step(
                                        run_id or "no_run_id",
                                        self.name,
                                        f"⚠️  Hunter.io fallback failed: {str(e)}",
                                        {"contact": contact_name}
                                    )
                except Exception as e:
                    self.detailed_logger.log_agent_step(
                        run_id or "no_run_id",
                        self.name,
                        f"⚠️  Apollo People Enrichment failed: {str(e)}",
                        {"contact": contact_name, "company": company_name}
                    )
            
            # STEP 3: Merge person and organization data for comprehensive enrichment
            # (Organization enrichment already done in STEP 1)
            if person_data or organization_data:
                # Start with organization data as base
                enrichment_data = organization_data.copy() if organization_data else {}
                
                # Merge person data (person data takes precedence for overlapping fields)
                if person_data:
                    # Update email if found in person data (CRITICAL: Apollo may return email even if input didn't have one)
                    found_email = person_data.get("email")
                    if found_email and found_email.strip() and "email_not_unlocked" not in str(found_email) and "@domain.com" not in str(found_email):
                        enrichment_data["email"] = found_email
                        enriched_lead["contact_email"] = found_email
                        # Log when we found an email that wasn't in the original lead
                        if not email or email != found_email:
                            self.detailed_logger.log_agent_step(
                                run_id or "no_run_id",
                                self.name,
                                f"📧 Apollo found email: {found_email} for {contact_name}",
                                {
                                    "original_email": email,
                                    "found_email": found_email,
                                    "contact": contact_name
                                }
                            )
                    
                    # Update title/role
                    if person_data.get("title"):
                        enrichment_data["title"] = person_data["title"]
                        enriched_lead["contact_title"] = person_data["title"]
                    
                    # Update LinkedIn URL
                    if person_data.get("linkedin_url"):
                        enrichment_data["linkedin_url"] = person_data["linkedin_url"]
                    
                    # Merge role details
                    if person_data.get("role_details"):
                        enrichment_data["role_details"] = person_data["role_details"]
                    
                    # Merge seniority
                    if person_data.get("seniority"):
                        enrichment_data["seniority"] = person_data["seniority"]
                    
                    # Merge firmographics (person data may have more detailed company info)
                    if person_data.get("firmographics"):
                        if not enrichment_data.get("firmographics"):
                            enrichment_data["firmographics"] = {}
                        enrichment_data["firmographics"].update(person_data["firmographics"])
                    
                    # Merge tech stack (combine both)
                    person_tech = person_data.get("tech_stack", [])
                    org_tech = enrichment_data.get("tech_stack", [])
                    if person_tech or org_tech:
                        combined_tech = list(set((person_tech or []) + (org_tech or [])))
                        enrichment_data["tech_stack"] = combined_tech
                
                # Ensure we have firmographics structure
                if not enrichment_data.get("firmographics"):
                    enrichment_data["firmographics"] = {}
            
            # Add enrichment data to lead
            if enrichment_data:
                enriched_lead["enrichment"] = enrichment_data
                enriched_lead["enrichment_source"] = "apollo" if apollo_success else "none"
                
                # Extract key fields to top level for database and scoring
                # Domain - preserve existing or use enriched domain
                if enrichment_data.get("domain") and not enriched_lead.get("domain"):
                    # Clean domain: remove http://, https://, www.
                    domain = enrichment_data.get("domain")
                    if domain:
                        domain = domain.replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
                        enriched_lead["domain"] = domain
                
                # Extract industry
                if enrichment_data.get("industry"):
                    enriched_lead["industry"] = enrichment_data.get("industry")
                
                # Extract revenue
                if enrichment_data.get("revenue"):
                    enriched_lead["revenue"] = enrichment_data.get("revenue")
                
                # Extract employee count
                if enrichment_data.get("employee_count"):
                    enriched_lead["employee_count"] = enrichment_data.get("employee_count")
                
                # Extract title/role
                if enrichment_data.get("title"):
                    enriched_lead["title"] = enrichment_data.get("title")
                    # Also update contact_title if not set
                    if not enriched_lead.get("contact_title"):
                        enriched_lead["contact_title"] = enrichment_data.get("title")
                
                # Extract seniority
                if enrichment_data.get("seniority"):
                    enriched_lead["seniority"] = enrichment_data.get("seniority")
                
                # Extract tech stack
                if enrichment_data.get("tech_stack"):
                    enriched_lead["tech_stack"] = enrichment_data.get("tech_stack")
                
                # Extract firmographics
                firmographics = enrichment_data.get("firmographics", {})
                if firmographics:
                    if not enriched_lead.get("firmographics"):
                        enriched_lead["firmographics"] = {}
                    enriched_lead["firmographics"].update(firmographics)
                    
                    # Extract description if available
                    if firmographics.get("description"):
                        if "description" not in enriched_lead["firmographics"]:
                            enriched_lead["firmographics"]["description"] = firmographics["description"]
            else:
                enriched_lead["enrichment"] = {}
                enriched_lead["enrichment_source"] = "none"
            
            # STEP 4: FINAL FALLBACK - OpenAI Web Search ONLY if Apollo failed
            if not apollo_success and self.openai_websearch:
                # Only use OpenAI if Apollo completely failed
                self.detailed_logger.log_agent_step(
                    run_id or "no_run_id",
                    self.name,
                    f"🌐 Apollo enrichment failed, using OpenAI Web Search fallback for {company_name}",
                    {
                        "apollo_person_success": bool(person_data),
                        "apollo_org_success": bool(organization_data)
                    }
                )
                
                # Check if critical fields are still missing
                has_missing_fields = (
                    not enriched_lead.get("industry") or
                    not enriched_lead.get("employee_count") or
                    not enriched_lead.get("revenue") or
                    (not enriched_lead.get("tech_stack") or len(enriched_lead.get("tech_stack", [])) == 0)
                )
                
                if has_missing_fields and company_name and domain:
                    try:
                        self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"🌐 Using OpenAI Web Search fallback for {company_name}", {
                            "missing_fields": [
                                k for k in ["industry", "revenue", "employee_count", "tech_stack"]
                                if not enriched_lead.get(k) or (k == "tech_stack" and len(enriched_lead.get(k, [])) == 0)
                            ]
                        })
                        
                        # Search for company data
                        web_data = self.openai_websearch.enrich_company_missing_fields(
                            company_name=company_name,
                            domain=domain,
                            current_data=enriched_lead
                        )
                        
                        if web_data:
                            # Merge web search results
                            if web_data.get("industry") and not enriched_lead.get("industry"):
                                enriched_lead["industry"] = web_data["industry"]
                            if web_data.get("revenue") and not enriched_lead.get("revenue"):
                                enriched_lead["revenue"] = web_data["revenue"]
                            if web_data.get("employee_count") and not enriched_lead.get("employee_count"):
                                enriched_lead["employee_count"] = web_data["employee_count"]
                            if web_data.get("tech_stack") and (not enriched_lead.get("tech_stack") or len(enriched_lead.get("tech_stack", [])) == 0):
                                enriched_lead["tech_stack"] = web_data["tech_stack"]
                            if web_data.get("description"):
                                if not enriched_lead.get("firmographics"):
                                    enriched_lead["firmographics"] = {}
                                if not enriched_lead["firmographics"].get("description"):
                                    enriched_lead["firmographics"]["description"] = web_data["description"]
                            
                            enriched_lead["enrichment_source"] = "apollo+websearch"
                            
                            self.detailed_logger.log_agent_step(run_id or "no_run_id", self.name, f"✅ OpenAI Web Search enriched {len(web_data)} fields", {
                                "fields_enriched": list(web_data.keys())
                            })
                        
                        # Search for person data if we have a contact
                        contact_name = enriched_lead.get("contact_name")
                        if contact_name and (not enriched_lead.get("title") or not enriched_lead.get("seniority")):
                            person_data = self.openai_websearch.enrich_person_missing_fields(
                                person_name=contact_name,
                                company_name=company_name,
                                current_data=enriched_lead
                            )
                            
                            if person_data:
                                if person_data.get("title") and not enriched_lead.get("title"):
                                    enriched_lead["title"] = person_data["title"]
                                if person_data.get("seniority") and not enriched_lead.get("seniority"):
                                    enriched_lead["seniority"] = person_data["seniority"]
                                if person_data.get("linkedin_url") and not enriched_lead.get("linkedin_url"):
                                    enriched_lead["linkedin_url"] = person_data["linkedin_url"]
                    
                    except Exception as websearch_error:
                        self.detailed_logger.log_agent_error(run_id or "no_run_id", self.name, websearch_error, {
                            "step": "openai_websearch_fallback",
                            "company": company_name
                        })
            
            enriched_leads.append(enriched_lead)
        
        return {
            "leads": enriched_leads,
            "total_enriched": len(enriched_leads),
            "enrichment_rate": len([l for l in enriched_leads if l.get("enrichment")]) / len(enriched_leads) if enriched_leads else 0,
            "emails_found_via_hunter": emails_found_via_hunter
        }

