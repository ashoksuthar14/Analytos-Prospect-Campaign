"""
Apollo API integration tool.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from tools.base_tool import BaseTool


class ApolloAPI(BaseTool):
    """
    Apollo API client for prospecting and email sending.
    
    Documentation: https://apolloio.github.io/apollo-api-docs/
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Apollo API client.
        
        Args:
            api_key: Apollo API key
        """
        super().__init__(api_key=api_key, base_url="https://api.apollo.io/v1")
    
    def _setup_auth(self) -> None:
        """Setup Apollo API authentication."""
        # Apollo API requires API key in X-Api-Key header
        self.session.headers.update({
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        })
        # Add API key to X-Api-Key header as required by Apollo
        if self.api_key:
            self.session.headers["X-Api-Key"] = self.api_key
    
    SAMPLE_LEADS_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_leads.json"
    
    def _load_sample_leads(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Load sample leads from local dataset as a fallback when Apollo API is unavailable.
        """
        try:
            if self.SAMPLE_LEADS_PATH.exists():
                with open(self.SAMPLE_LEADS_PATH, "r", encoding="utf-8") as f:
                    leads = json.load(f)
                    return leads[:max_results]
        except Exception:
            pass
        return []
    
    def search_companies(
        self,
        industry: Optional[List[str]] = None,
        location: Optional[str] = None,
        revenue_min: Optional[int] = None,
        revenue_max: Optional[int] = None,
        employee_min: Optional[int] = None,
        employee_max: Optional[int] = None,
        tech_stack: Optional[List[str]] = None,
        signals: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for companies matching ICP criteria.
        
        Args:
            industry: List of industries
            location: Location (country/region)
            revenue_min: Minimum revenue
            revenue_max: Maximum revenue
            employee_min: Minimum employee count
            employee_max: Maximum employee count
            tech_stack: List of technologies
            signals: List of signals
            max_results: Maximum number of results
            
        Returns:
            List of company/contact dictionaries
        """
        # Build search parameters according to Apollo API specification
        # NOTE: According to Apollo docs, search endpoint does NOT reveal emails
        # We need to use enrichment endpoint separately for that
        search_params = {
            "page": 1,
            "per_page": min(max_results, 100),
            "person_titles": ["CEO", "CTO", "VP", "VP Sales", "Founder", "Director", "Head of"]  # Default titles
        }
        
        # Build filters using correct Apollo API parameter names
        filters = {}
        
        # Industry - Use organization_industry_tag_ids for filtering
        # Note: We'll rely on post-filtering for strict matching since Apollo's filter may be fuzzy
        if industry:
            # Convert to list if single string
            industry_list = industry if isinstance(industry, list) else [industry]
            # Use q_organization_keyword_tags to hint at industry (will be strictly filtered post-search)
            filters["q_organization_keyword_tags"] = industry_list
        
        # Tech stack as additional keywords
        if tech_stack:
            tech_list = tech_stack if isinstance(tech_stack, list) else [tech_stack]
            # Combine with industry if both exist
            if "q_organization_keyword_tags" in filters:
                filters["q_organization_keyword_tags"].extend(tech_list)
            else:
                filters["q_organization_keyword_tags"] = tech_list
        
        # Location - Apollo expects organization_locations as list
        if location:
            # Apollo accepts country names or region names
            filters["organization_locations"] = [location] if isinstance(location, str) else location
        
        # Revenue range - Use Apollo's min/max revenue parameters
        if revenue_min is not None:
            # Apollo expects revenue in dollars
            filters["revenue_min"] = revenue_min
        
        if revenue_max is not None:
            filters["revenue_max"] = revenue_max
        
        # Employee count - Apollo uses predefined ranges - only include ranges WITHIN the requested range
        if employee_min is not None or employee_max is not None:
            # Apollo uses predefined employee ranges
            # Common ranges: "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"
            # Define range boundaries
            range_map = {
                "1-10": (1, 10),
                "11-50": (11, 50),
                "51-200": (51, 200),
                "201-500": (201, 500),
                "501-1000": (501, 1000),
                "1001-5000": (1001, 5000),
                "5001-10000": (5001, 10000),
                "10001+": (10001, 100000)
            }
            
            employee_ranges = []
            emp_min = employee_min if employee_min is not None else 1
            emp_max = employee_max if employee_max is not None else 100000
            
            # Only include ranges that have ANY overlap with the requested range
            for range_name, (range_min, range_max) in range_map.items():
                # Check if this range overlaps with requested range
                if range_max >= emp_min and range_min <= emp_max:
                    employee_ranges.append(range_name)
            
            if employee_ranges:
                filters["organization_num_employees_ranges"] = employee_ranges
        
        # Make API request
        # API key is now in X-Api-Key header, not in request body
        def _clean_domain(raw_domain: Optional[str]) -> str:
            """Normalize domains and handle None safely."""
            if not raw_domain or not isinstance(raw_domain, str):
                return ""
            return (
                raw_domain.replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .split("/")[0]
                .strip()
            )
        
        def _filter_by_criteria(lead: Dict[str, Any]) -> bool:
            """Filter leads to match exact ICP criteria"""
            company_name = lead.get("company_name", "Unknown")
            
            # Check revenue range
            if revenue_min is not None or revenue_max is not None:
                lead_revenue = lead.get("revenue")
                if lead_revenue is not None:
                    if revenue_min is not None and lead_revenue < revenue_min:
                        print(f"[Apollo Filter] ❌ REJECTED: '{company_name}' - Revenue too low: ${lead_revenue:,} < ${revenue_min:,}")
                        return False
                    if revenue_max is not None and lead_revenue > revenue_max:
                        print(f"[Apollo Filter] ❌ REJECTED: '{company_name}' - Revenue too high: ${lead_revenue:,} > ${revenue_max:,}")
                        return False
            
            # Check employee count range
            if employee_min is not None or employee_max is not None:
                lead_employees = lead.get("employee_count")
                if lead_employees is not None:
                    if employee_min is not None and lead_employees < employee_min:
                        print(f"[Apollo Filter] ❌ REJECTED: '{company_name}' - Too few employees: {lead_employees} < {employee_min}")
                        return False
                    if employee_max is not None and lead_employees > employee_max:
                        print(f"[Apollo Filter] ❌ REJECTED: '{company_name}' - Too many employees: {lead_employees} > {employee_max}")
                        return False
            
            # Check industry match (VERY STRICT)
            if industry:
                lead_industry = lead.get("industry")
                if lead_industry:
                    # Normalize for comparison
                    lead_industry_lower = str(lead_industry).lower().strip()
                    industry_list = industry if isinstance(industry, list) else [industry]
                    
                    # Define industry keyword mappings for strict matching
                    industry_keywords = {
                        "manufacturing": ["manufacturing", "industrial", "factory", "production"],
                        "technology": ["technology", "software", "tech", "it services"],
                        "healthcare": ["healthcare", "health care", "medical", "hospital", "pharma"],
                        "financial services": ["financial", "finance", "banking", "insurance", "fintech"],
                        "retail": ["retail", "e-commerce", "ecommerce", "consumer goods"],
                        "professional services": ["professional services", "consulting", "legal", "accounting"],
                        "real estate": ["real estate", "property", "real-estate"],
                        "education": ["education", "educational", "e-learning", "elearning", "training", "learning"],
                        "transportation & logistics": ["transportation", "logistics", "shipping", "freight"],
                        "energy & utilities": ["energy", "utilities", "power", "oil", "gas"]
                    }
                    
                    industry_match = False
                    for ind in industry_list:
                        ind_lower = str(ind).lower().strip()
                        
                        # Get keywords for this industry
                        keywords = industry_keywords.get(ind_lower, [ind_lower])
                        
                        # Check if ANY keyword matches the lead industry
                        for keyword in keywords:
                            if keyword in lead_industry_lower:
                                industry_match = True
                                break
                        
                        if industry_match:
                            break
                    
                    if not industry_match:
                        # Log rejected lead for debugging
                        print(f"[Apollo Filter] ❌ REJECTED: '{company_name}' - Industry mismatch: wanted '{industry}', got '{lead_industry}'")
                        return False
                    else:
                        # Log accepted match for verification
                        print(f"[Apollo Filter] ✅ ACCEPTED: '{company_name}' - Industry match: '{lead_industry}' matches '{industry}'")
                else:
                    # No industry data, exclude if industry filter is strict
                    print(f"[Apollo Filter] ❌ REJECTED: '{company_name}' - No industry data")
                    return False
            
            # Check location match
            if location:
                lead_location = lead.get("location")
                if lead_location:
                    location_lower = str(location).lower().strip()
                    lead_location_lower = str(lead_location).lower().strip()
                    # Check if location matches (contains or is contained)
                    if location_lower not in lead_location_lower and lead_location_lower not in location_lower:
                        return False
                else:
                    # No location data, might want to include or exclude
                    # For now, we'll be lenient on location
                    pass
            
            return True
        
        def _transform_people_response(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
            people = response_data.get("people", [])
            results = []
            for person in people:
                organization = person.get("organization", {})
                lead = {
                    "company_name": organization.get("name", ""),
                    "domain": _clean_domain(organization.get("website_url") or organization.get("primary_domain")),
                    "contact_email": person.get("email"),
                    "contact_name": person.get("name", ""),
                    "contact_title": person.get("title"),
                    "revenue": organization.get("estimated_annual_revenue"),
                    "employee_count": organization.get("estimated_num_employees"),
                    "industry": organization.get("industry"),
                    "location": person.get("city") or organization.get("location")
                }
                # Apply strict filtering
                if _filter_by_criteria(lead):
                    results.append(lead)
            return results
        
        def _transform_contacts_response(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
            contacts = response_data.get("contacts", [])
            results = []
            for contact in contacts:
                organization = contact.get("organization", {})
                lead = {
                    "company_name": organization.get("name", ""),
                    "domain": _clean_domain(organization.get("website_url") or organization.get("primary_domain")),
                    "contact_email": contact.get("email"),
                    "contact_name": contact.get("name", ""),
                    "contact_title": contact.get("title"),
                    "revenue": organization.get("estimated_annual_revenue"),
                    "employee_count": organization.get("estimated_num_employees"),
                    "industry": organization.get("industry"),
                    "location": contact.get("city") or organization.get("location")
                }
                # Apply strict filtering
                if _filter_by_criteria(lead):
                    results.append(lead)
            return results
        
        request_data = {
            **search_params,
            **filters
        }
        
        # Try People Search endpoint first (supported on more plans)
        try:
            response = self._make_request(
                method="POST",
                endpoint="/people/search",
                data=request_data
            )
            if response.get("people"):
                raw_count = len(response.get("people", []))
                filtered_results = _transform_people_response(response)[:max_results]
                filtered_count = len(filtered_results)
                if raw_count > filtered_count:
                    print(f"[Apollo API] Filtered {raw_count - filtered_count} leads that didn't match ICP criteria (kept {filtered_count}/{raw_count})")
                return filtered_results
        
            # Some responses use `contacts` key even for people search
            if response.get("contacts"):
                raw_count = len(response.get("contacts", []))
                filtered_results = _transform_contacts_response(response)[:max_results]
                filtered_count = len(filtered_results)
                if raw_count > filtered_count:
                    print(f"[Apollo API] Filtered {raw_count - filtered_count} leads that didn't match ICP criteria (kept {filtered_count}/{raw_count})")
                return filtered_results
        
            # If API responds without data but with error details, check fallback
            error_info = response.get("error")
            if error_info:
                error_msg = json.dumps(error_info)
                if "API_INACCESSIBLE" in error_msg or "not accessible with this api_key" in error_msg:
                    response = self._make_request(
                        method="POST",
                        endpoint="/contacts/search",
                        data=request_data
                    )
                    return _transform_contacts_response(response)[:max_results]
                if "E.C.P" in error_msg or "not enabled" in error_msg.lower():
                    raise RuntimeError(
                        "Apollo E.C.P (Email Campaign Platform) is not enabled. "
                        "Please enable it in your Apollo account settings or use a different prospecting source."
                    )
                raise RuntimeError(f"Apollo API error: {error_msg}")
            
            # If response is empty but no error, fall back to /contacts/search
            response = self._make_request(
                method="POST",
                endpoint="/contacts/search",
                data=request_data
            )
            raw_count = len(response.get("contacts", []))
            contacts = _transform_contacts_response(response)
            filtered_count = len(contacts)
            if raw_count > filtered_count:
                print(f"[Apollo API] Filtered {raw_count - filtered_count} leads that didn't match ICP criteria (kept {filtered_count}/{raw_count})")
            if not contacts:
                return self._load_sample_leads(max_results)
            return contacts[:max_results]
        
        except RuntimeError as e:
            error_msg = str(e)
            # Handle endpoint access restrictions for free plans
            if "API_INACCESSIBLE" in error_msg or "not accessible with this api_key" in error_msg:
                # Fallback to contacts/search endpoint
                response = self._make_request(
                    method="POST",
                    endpoint="/contacts/search",
                    data=request_data
                )
                raw_count = len(response.get("contacts", []))
                contacts = _transform_contacts_response(response)
                filtered_count = len(contacts)
                if raw_count > filtered_count:
                    print(f"[Apollo API] Filtered {raw_count - filtered_count} leads that didn't match ICP criteria (kept {filtered_count}/{raw_count})")
                if not contacts:
                    return self._load_sample_leads(max_results)
                return contacts[:max_results]
            
            # Check for Apollo-specific errors
            if "E.C.P" in error_msg or "not enabled" in error_msg.lower():
                raise RuntimeError(
                    "Apollo E.C.P (Email Campaign Platform) is not enabled. "
                    "Please enable it in your Apollo account settings or use a different prospecting source."
                )
            if "403" in error_msg or "Forbidden" in error_msg:
                raise RuntimeError(
                    "Apollo API authentication failed (403 Forbidden). "
                    "Please check your API key is valid and has the required permissions."
                )
            # Final fallback to sample leads
            return self._load_sample_leads(max_results)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email via Apollo Send.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body
            from_email: Sender email
            from_name: Sender name
            
        Returns:
            Response with message ID and status
        """
        payload = {
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "from_email": from_email,
            "from_name": from_name
        }

        response = self._make_request(
            method="POST",
            endpoint="/emails/messages/send",
            data=payload
        )
        
        return {
            "message_id": response.get("id"),
            "status": "sent",
            "provider": "apollo"
        }
    
    def enrich_company(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich company data using Apollo API Organization Enrichment endpoint.
        
        Uses GET /organizations/enrich with domain as query parameter.
        
        Args:
            domain: Company domain (required for API, but we'll try company_name if missing)
            company_name: Company name (fallback if domain not available)
            
        Returns:
            Enriched company data dictionary
        """
        if not domain:
            if not company_name:
                raise ValueError("Either domain or company_name must be provided")
            # Try to extract domain from company name (simple heuristic)
            # This is a fallback - ideally domain should be provided
            domain = company_name.lower().replace(" ", "").replace(",", "").replace(".", "") + ".com"
        
        # Clean domain: remove www., http://, https://
        clean_domain = domain.replace("www.", "").replace("http://", "").replace("https://", "").strip("/").split("/")[0]
        
        # Use GET with query params as per API documentation
        response = self._make_request(
            method="GET",
            endpoint="/organizations/enrich",
            params={"domain": clean_domain}
        )

        org = response.get("organization") or response.get("organization_record") or response
        if not isinstance(org, dict):
            return {}
        
        tech_stack = org.get("technologies") or org.get("tech_stack") or []
        if isinstance(tech_stack, dict):
            tech_stack = list(tech_stack.values())

        primary_phone = org.get("primary_phone") or {}

        return {
            "company_name": org.get("name"),
            "domain": org.get("website_url") or org.get("primary_domain") or domain,
            "industry": org.get("industry") or org.get("industries") or org.get("industry_tag_list"),
            "revenue": org.get("estimated_annual_revenue") or org.get("annual_revenue"),
            "employee_count": org.get("estimated_num_employees") or org.get("employee_count") or org.get("num_employees"),
            "linkedin_url": org.get("linkedin_url") or org.get("linkedin"),
            "tech_stack": tech_stack,
            "firmographics": {
                "founded_year": org.get("founded_year"),
                "headquarters": primary_phone.get("location") or org.get("location") or org.get("city"),
                "description": org.get("description") or org.get("short_description"),
                "tags": org.get("tags", [])
            },
            "role_details": {}
        }
    
    def match_person_reveal_email(
        self,
        first_name: str,
        last_name: str,
        domain: str
    ) -> Optional[str]:
        """
        Match a person and reveal their email using Apollo /people/match endpoint.
        This is the CORRECT way to get real emails from Apollo API.
        
        Args:
            first_name: Person's first name
            last_name: Person's last name
            domain: Company domain
            
        Returns:
            Real email address or None
        """
        # Clean domain: remove www., http://, https://
        clean_domain = domain.replace("www.", "").replace("http://", "").replace("https://", "").strip("/")
        
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "domain": clean_domain,
            "reveal_personal_emails": True  # THIS is the key parameter!
        }

        try:
            response = self._make_request(
                method="POST",
                endpoint="/people/match",  # Correct endpoint for email reveal
                data=payload
            )

            person = response.get("person", {})
            email = person.get("email")
            
            # Debug logging
            if not email or "email_not_unlocked" in str(email):
                print(f"Apollo /people/match returned: {person.get('email')} for {first_name} {last_name} @ {clean_domain}")
                print(f"Person data: name={person.get('name')}, email_status={person.get('email_status')}")
            
            # Check if we got a real email (not locked)
            if email and "email_not_unlocked" not in str(email) and "@domain.com" not in str(email):
                return email
            
            return None
            
        except Exception as e:
            print(f"Apollo match_person error: {str(e)}")
            return None
    
    def enrich_person(
        self,
        email: Optional[str] = None,
        domain: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        name: Optional[str] = None,
        organization_name: Optional[str] = None,
        reveal_personal_emails: bool = True
    ) -> Dict[str, Any]:
        """
        Enrich person/contact data using Apollo API People Enrichment endpoint.
        
        Uses POST /people/match endpoint as per API documentation.
        
        Args:
            email: Contact email
            domain: Company domain
            first_name: First name
            last_name: Last name
            name: Full name (alternative to first_name + last_name)
            organization_name: Company name
            reveal_personal_emails: Whether to reveal personal emails (default: True)
            
        Returns:
            Enriched person data dictionary with real email if available
        """
        # Build payload according to API documentation
        payload: Dict[str, Any] = {}
        
        # Add name information (prefer full name, then first+last)
        if name:
            payload["name"] = name
        elif first_name and last_name:
            payload["first_name"] = first_name
            payload["last_name"] = last_name
        elif first_name:
            payload["first_name"] = first_name
        
        # Add email if available
        if email:
            payload["email"] = email
        
        # Add domain (required for better matching)
        if domain:
            # Clean domain: remove www., http://, https://
            clean_domain = domain.replace("www.", "").replace("http://", "").replace("https://", "").strip("/").split("/")[0]
            payload["domain"] = clean_domain
        
        # Add organization name if available
        if organization_name:
            payload["organization_name"] = organization_name
        
        # Add reveal_personal_emails parameter
        payload["reveal_personal_emails"] = reveal_personal_emails
        
        # Need at least some identifying information
        if not payload:
            return {}

        try:
            # Use POST /people/match endpoint as per API documentation
            response = self._make_request(
                method="POST",
                endpoint="/people/match",
                data=payload
            )

            person = response.get("person") or response
            if not isinstance(person, dict):
                return {}

            organization = person.get("organization") or response.get("organization") or {}
            
            # Get Apollo person ID - we can use this to get more detailed info
            apollo_person_id = person.get("id") or person.get("_id")

            # Extract email from Apollo response (this is the key fix!)
            apollo_email = person.get("email")
            email_status = person.get("email_status", "unknown")
            
            # Debug: Log what Apollo returned
            print(f"[ApolloAPI] Person enrichment response for {first_name} {last_name}:")
            print(f"  - Email: {apollo_email}")
            print(f"  - Email Status: {email_status}")
            print(f"  - Person ID: {apollo_person_id}")
            print(f"  - Domain used: {domain}")
            print(f"  - Title: {person.get('title')}")
            print(f"  - LinkedIn: {person.get('linkedin_url')}")
            
            # If no email found, try to get it using person ID (more detailed lookup)
            if not apollo_email or "email_not_unlocked" in str(apollo_email) or "@domain.com" in str(apollo_email):
                if apollo_person_id:
                    try:
                        # Try to get person by ID for more detailed info
                        print(f"[ApolloAPI] Trying person ID lookup: {apollo_person_id}")
                        person_detail_response = self._make_request(
                            method="GET",
                            endpoint=f"/people/{apollo_person_id}",
                            params={"reveal_personal_emails": "true"}
                        )
                        detailed_person = person_detail_response.get("person", {})
                        detailed_email = detailed_person.get("email")
                        if detailed_email and "email_not_unlocked" not in str(detailed_email) and "@domain.com" not in str(detailed_email):
                            apollo_email = detailed_email
                            email_status = detailed_person.get("email_status", email_status)
                            print(f"[ApolloAPI] ✅ Found email via person ID lookup: {apollo_email} for {first_name} {last_name}")
                        else:
                            print(f"[ApolloAPI] Person ID lookup returned: {detailed_email} (status: {detailed_person.get('email_status')})")
                    except Exception as e:
                        # Person ID lookup failed, continue with what we have
                        print(f"[ApolloAPI] Person ID lookup failed: {str(e)}")
                        pass
            
            # Use Apollo's email if it's valid, otherwise fall back to input email
            final_email = None
            if apollo_email and "email_not_unlocked" not in str(apollo_email) and "@domain.com" not in str(apollo_email):
                final_email = apollo_email
                # Debug logging
                if not email or email != apollo_email:
                    print(f"[ApolloAPI] Found email from Apollo: {apollo_email} (status: {email_status}) for {first_name} {last_name}")
            elif email and "email_not_unlocked" not in str(email) and "@domain.com" not in str(email):
                final_email = email
            else:
                # Log when Apollo didn't return a valid email
                if apollo_email:
                    print(f"[ApolloAPI] Apollo returned invalid email: {apollo_email} (status: {email_status}) for {first_name} {last_name}")
                else:
                    print(f"[ApolloAPI] Apollo did not return email for {first_name} {last_name} @ {domain}")
            
            tech_stack = organization.get("technologies") or organization.get("tech_stack") or []
            if isinstance(tech_stack, dict):
                tech_stack = list(tech_stack.values())
            
            primary_phone = organization.get("primary_phone") or {}

            return {
                "email": final_email,  # Use email from Apollo response if available
                "title": person.get("title"),
                "seniority": person.get("seniority"),
                "linkedin_url": person.get("linkedin_url"),
                "company_name": organization.get("name"),
                "domain": organization.get("website_url") or organization.get("primary_domain") or domain,
                "industry": organization.get("industry") or organization.get("industries") or organization.get("industry_tag_list"),
                "revenue": organization.get("estimated_annual_revenue") or organization.get("annual_revenue"),
                "employee_count": organization.get("estimated_num_employees") or organization.get("employee_count") or organization.get("num_employees"),
                "tech_stack": tech_stack,
                "firmographics": {
                    "company_name": organization.get("name"),
                    "founded_year": organization.get("founded_year"),
                    "headquarters": primary_phone.get("location") or organization.get("location") or organization.get("city"),
                    "description": organization.get("description") or organization.get("short_description"),
                    "tags": organization.get("tags", [])
                },
                "role_details": {
                    "seniority": person.get("seniority"),
                    "role": person.get("title")
                }
            }
        except Exception:
            return {}
    
    def create_contact(
        self,
        first_name: str,
        last_name: str,
        organization_name: str,
        email: Optional[str] = None,
        title: Optional[str] = None,
        website_url: Optional[str] = None,
        present_raw_address: Optional[str] = None,
        direct_phone: Optional[str] = None,
        corporate_phone: Optional[str] = None,
        mobile_phone: Optional[str] = None,
        home_phone: Optional[str] = None,
        other_phone: Optional[str] = None,
        label_names: Optional[List[str]] = None,
        contact_stage_id: Optional[str] = None,
        account_id: Optional[str] = None,
        typed_custom_fields: Optional[Dict[str, Any]] = None,
        run_dedupe: bool = True
    ) -> Dict[str, Any]:
        """
        Create a contact in Apollo.
        
        According to Apollo API documentation:
        https://docs.apollo.io/reference/create-a-contact
        
        Args:
            first_name: Contact's first name (required)
            last_name: Contact's last name (required)
            organization_name: Company name (required)
            email: Contact email address
            title: Job title
            website_url: Company website URL
            present_raw_address: Personal location (e.g., "Atlanta, United States")
            direct_phone: Primary phone number
            corporate_phone: Work/office phone number
            mobile_phone: Mobile phone number
            home_phone: Home phone number
            other_phone: Alternative phone number
            label_names: List of labels/lists to add contact to
            contact_stage_id: Apollo contact stage ID
            account_id: Apollo account ID
            typed_custom_fields: Custom field values
            run_dedupe: Enable deduplication (default: True to prevent duplicates)
            
        Returns:
            Dictionary with created contact data including contact ID
            
        Raises:
            RuntimeError: If API request fails
        """
        if not first_name or not last_name or not organization_name:
            raise ValueError("first_name, last_name, and organization_name are required")
        
        payload: Dict[str, Any] = {
            "first_name": first_name,
            "last_name": last_name,
            "organization_name": organization_name,
            "run_dedupe": run_dedupe
        }
        
        # Add optional fields if provided
        if email:
            payload["email"] = email
        if title:
            payload["title"] = title
        if website_url:
            payload["website_url"] = website_url
        if present_raw_address:
            payload["present_raw_address"] = present_raw_address
        if direct_phone:
            payload["direct_phone"] = direct_phone
        if corporate_phone:
            payload["corporate_phone"] = corporate_phone
        if mobile_phone:
            payload["mobile_phone"] = mobile_phone
        if home_phone:
            payload["home_phone"] = home_phone
        if other_phone:
            payload["other_phone"] = other_phone
        if label_names:
            payload["label_names"] = label_names
        if contact_stage_id:
            payload["contact_stage_id"] = contact_stage_id
        if account_id:
            payload["account_id"] = account_id
        if typed_custom_fields:
            payload["typed_custom_fields"] = typed_custom_fields
        
        # Apollo API contacts endpoint
        # Note: Documentation shows: POST https://api.apollo.io/api/v1/contacts
        # But our base_url is https://api.apollo.io/v1, so endpoint is /contacts
        # This results in: https://api.apollo.io/v1/contacts (which works)
        # The /api/v1 path in docs might be for a different API version or documentation format
        response = self._make_request(
            method="POST",
            endpoint="/contacts",
            data=payload
        )
        
        return response
    
    def update_contact(
        self,
        contact_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        title: Optional[str] = None,
        email: Optional[str] = None,
        organization_name: Optional[str] = None,
        website_url: Optional[str] = None,
        present_raw_address: Optional[str] = None,
        direct_phone: Optional[str] = None,
        corporate_phone: Optional[str] = None,
        mobile_phone: Optional[str] = None,
        label_names: Optional[List[str]] = None,
        contact_stage_id: Optional[str] = None,
        typed_custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing contact in Apollo.
        
        According to Apollo API documentation:
        https://docs.apollo.io/reference/update-a-contact
        
        Args:
            contact_id: Apollo contact ID (required)
            first_name: Contact's first name
            last_name: Contact's last name
            title: Job title
            email: Contact email address
            organization_name: Company name
            website_url: Company website URL
            present_raw_address: Personal location
            direct_phone: Primary phone number
            corporate_phone: Work/office phone number
            mobile_phone: Mobile phone number
            label_names: List of labels/lists to add contact to
            contact_stage_id: Apollo contact stage ID
            typed_custom_fields: Custom field values (e.g., {"custom_field_id": "value"})
            
        Returns:
            Dictionary with updated contact data
            
        Raises:
            RuntimeError: If API request fails
        """
        if not contact_id:
            raise ValueError("contact_id is required")
        
        payload: Dict[str, Any] = {
            "id": contact_id
        }
        
        # Add optional fields if provided
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if title is not None:
            payload["title"] = title
        if email is not None:
            payload["email"] = email
        if organization_name is not None:
            payload["organization_name"] = organization_name
        if website_url is not None:
            payload["website_url"] = website_url
        if present_raw_address is not None:
            payload["present_raw_address"] = present_raw_address
        if direct_phone is not None:
            payload["direct_phone"] = direct_phone
        if corporate_phone is not None:
            payload["corporate_phone"] = corporate_phone
        if mobile_phone is not None:
            payload["mobile_phone"] = mobile_phone
        if label_names is not None:
            payload["label_names"] = label_names
        if contact_stage_id is not None:
            payload["contact_stage_id"] = contact_stage_id
        if typed_custom_fields is not None:
            payload["typed_custom_fields"] = typed_custom_fields
        
        # Apollo API contact update endpoint
        response = self._make_request(
            method="PUT",
            endpoint=f"/contacts/{contact_id}",
            data=payload
        )
        
        return response
    
    def search_sequences(
        self,
        q_name: Optional[str] = None,
        page: int = 1,
        per_page: int = 25
    ) -> Dict[str, Any]:
        """
        Search for sequences (emailer campaigns) in your Apollo account.
        
        According to Apollo API documentation:
        https://docs.apollo.io/reference/search-for-sequences
        
        Args:
            q_name: Keyword to search sequence names (e.g., "marketing")
            page: Page number for pagination
            per_page: Number of results per page (default: 25, max: 100)
            
        Returns:
            Dictionary with:
            - emailer_campaigns: List of sequence objects
            - pagination: Pagination metadata
            
        Raises:
            RuntimeError: If API request fails
        """
        payload: Dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100)  # Apollo max is 100
        }
        
        if q_name:
            payload["q_name"] = q_name
        
        response = self._make_request(
            method="POST",
            endpoint="/emailer_campaigns/search",
            data=payload
        )
        
        return response
    
    def add_contacts_to_sequence(
        self,
        sequence_id: str,
        contact_ids: List[str],
        emailer_campaign_id: Optional[str] = None,
        send_email_from_email_account_id: Optional[str] = None,
        sequence_active_in_other_campaigns: bool = False,
        sequence_finished_in_other_campaigns: bool = False,
        sequence_no_email: bool = False,
        sequence_unsubscribed_email: bool = False,
        contact_without_ownership_permission: bool = False,
        add_to_active: bool = True
    ) -> Dict[str, Any]:
        """
        Add contacts to a sequence (emailer campaign) in Apollo.
        
        According to Apollo API documentation:
        https://docs.apollo.io/reference/add-contacts-to-sequence
        
        Args:
            sequence_id: The sequence ID (emailer_campaign_id)
            contact_ids: List of Apollo contact IDs to add to sequence
            emailer_campaign_id: (Optional) Same as sequence_id, for compatibility
            send_email_from_email_account_id: Email account ID to send from
            sequence_active_in_other_campaigns: Add even if active in other sequences
            sequence_finished_in_other_campaigns: Add even if finished in other sequences
            sequence_no_email: Add contacts without email
            sequence_unsubscribed_email: Add contacts with unsubscribed emails
            contact_without_ownership_permission: Add contacts without ownership
            add_to_active: Set to true to add contacts to active sequences
            
        Returns:
            Dictionary with:
            - contacts: List of added contacts with their status
            - emailer_campaign: Sequence details
            
        Raises:
            RuntimeError: If API request fails
        """
        if not sequence_id or not contact_ids:
            raise ValueError("sequence_id and contact_ids are required")
        
        # Use sequence_id or emailer_campaign_id (they're the same)
        campaign_id = emailer_campaign_id or sequence_id
        
        payload: Dict[str, Any] = {
            "contact_ids": contact_ids,
            "emailer_campaign_id": campaign_id,
            "sequence_active_in_other_campaigns": sequence_active_in_other_campaigns,
            "sequence_finished_in_other_campaigns": sequence_finished_in_other_campaigns,
            "sequence_no_email": sequence_no_email,
            "sequence_unsubscribed_email": sequence_unsubscribed_email,
            "contact_without_ownership_permission": contact_without_ownership_permission
        }
        
        if send_email_from_email_account_id:
            payload["send_email_from_email_account_id"] = send_email_from_email_account_id
        
        # Apollo endpoint format
        response = self._make_request(
            method="POST",
            endpoint=f"/emailer_campaigns/{campaign_id}/add_contact_ids",
            data=payload
        )
        
        return response
    
    def get_sequence_details(
        self,
        sequence_id: str
    ) -> Dict[str, Any]:
        """
        Get details of a specific sequence.
        
        Args:
            sequence_id: The sequence ID
            
        Returns:
            Dictionary with sequence details
            
        Raises:
            RuntimeError: If API request fails
        """
        response = self._make_request(
            method="GET",
            endpoint=f"/emailer_campaigns/{sequence_id}"
        )
        
        return response

