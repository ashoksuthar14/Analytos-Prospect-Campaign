"""
Explorium API integration for prospect and business enrichment.
Reference: https://developers.explorium.ai/reference/quick-starts/use_case_prospecting
"""

import requests
from typing import Dict, Any, List, Optional
import time


class ExporiumAPI:
    """
    Explorium AgentSource API client for prospect and business enrichment.
    
    Features:
    - Prospect fetching with job department/level filters
    - Contact information enrichment (emails, phones)
    - Business fetching and statistics
    - Proper pagination support
    
    Reference: https://developers.explorium.ai/reference/quick-starts/use_case_prospecting
    """
    
    BASE_URL = "https://api.explorium.ai/v1"
    
    def __init__(self, api_key: str):
        """
        Initialize Explorium API client.
        
        Args:
            api_key: Explorium API key
        """
        self.api_key = api_key
        # Explorium uses API_KEY header, not Authorization Bearer
        self.headers = {
            "API_KEY": api_key,
            "Content-Type": "application/json"
        }
    
    def fetch_prospects_by_business(
        self,
        business_ids: List[str],
        job_departments: Optional[List[str]] = None,
        has_email: bool = True,
        page_size: int = 50,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch prospects from specific businesses.
        
        Per Explorium docs: This returns basic prospect info (name, title, department)
        but NOT contact details. Use enrich_contact_info() to get emails/phones.
        
        Args:
            business_ids: List of Explorium business IDs
            job_departments: Filter by departments (e.g., ["marketing", "sales"])
            has_email: Only return prospects with emails
            page_size: Results per page (max 100)
            max_results: Total max results
            
        Returns:
            List of prospect dictionaries with prospect_id
        """
        try:
            payload = {
                "mode": "full",
                "size": min(max_results, 10000),
                "page_size": min(page_size, 100),
                "page": 1,
                "filters": {
                    "business_id": {
                        "type": "includes",
                        "values": business_ids
                    }
                }
            }
            
            if job_departments:
                payload["filters"]["job_department"] = {
                    "type": "includes",
                    "values": job_departments
                }
            
            if has_email:
                payload["filters"]["has_email"] = {
                    "type": "exists",
                    "value": True
                }
            
            response = requests.post(
                f"{self.BASE_URL}/prospects",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                prospects = data.get("data", [])
                return prospects
            else:
                print(f"Explorium fetch prospects failed: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Explorium fetch prospects error: {e}")
            return []
    
    def enrich_contact_info(self, prospect_id: str) -> Optional[Dict[str, Any]]:
        """
        Enrich a prospect with contact information (emails, phone numbers).
        
        Per Explorium docs: This is a separate call after fetching prospects.
        This endpoint returns the actual email addresses and phone numbers.
        
        Args:
            prospect_id: Explorium prospect ID from fetch_prospects
            
        Returns:
            Dictionary with contact info including emails and phone numbers
        """
        try:
            payload = {
                "prospect_id": prospect_id
            }
            
            response = requests.post(
                f"{self.BASE_URL}/prospects/contacts_information/enrich",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                contact_data = data.get("data", {})
                
                # Parse contact information
                emails = contact_data.get("emails", [])
                professional_email = contact_data.get("professions_email")
                
                return {
                    "emails": emails,
                    "professional_email": professional_email,
                    "email": professional_email or (emails[0] if emails else None),
                    "phone_numbers": contact_data.get("phone_numbers"),
                    "mobile_phone": contact_data.get("mobile_phone"),
                    "source": "explorium"
                }
            else:
                print(f"Explorium contact enrichment failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Explorium contact enrichment error: {e}")
            return None
    
    def fetch_businesses(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        page_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch businesses matching domain or name.
        
        Note: Explorium's business filters may not support direct domain filtering.
        We'll search by company name derived from domain if needed.
        
        Args:
            domain: Company domain (will be converted to search term)
            company_name: Company name
            page_size: Results per page
            
        Returns:
            List of business dictionaries with business_id
        """
        try:
            # If only domain provided, try to derive company name
            search_term = company_name
            if not search_term and domain:
                # Extract company name from domain (e.g., "apple.com" -> "apple")
                search_term = domain.replace("www.", "").replace(".com", "").replace(".io", "").replace(".ai", "")
            
            if not search_term:
                return []
            
            # Use a basic request without complex filters
            # Per Explorium docs, filters like country_code, company_size, google_category are supported
            # but domain filtering isn't explicitly mentioned
            payload = {
                "mode": "full",
                "size": page_size,
                "page_size": page_size,
                "page": 1
            }
            
            # Try a minimal approach - fetch and filter client-side
            response = requests.post(
                f"{self.BASE_URL}/businesses",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                businesses = data.get("data", [])
                
                # Filter businesses client-side by domain or name
                filtered = []
                for biz in businesses:
                    biz_domain = biz.get("domain", "").lower()
                    biz_name = biz.get("name", "").lower()
                    
                    if domain and domain.lower() in biz_domain:
                        filtered.append(biz)
                    elif search_term and search_term.lower() in biz_name:
                        filtered.append(biz)
                
                return filtered[:page_size]
            else:
                print(f"Explorium fetch businesses failed: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Explorium fetch businesses error: {e}")
            return []
    
    def match_prospect(
        self,
        first_name: str,
        last_name: str,
        company_domain: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Match a prospect and return their contact details.
        
        Workflow per Explorium docs:
        1. Fetch businesses by domain/name
        2. Fetch prospects from those businesses
        3. Enrich contact info to get email/phone
        
        Args:
            first_name: First name
            last_name: Last name
            company_domain: Company domain
            company_name: Company name
            
        Returns:
            Dictionary with matched prospect data including email
        """
        try:
            # Step 1: Fetch businesses by domain
            businesses = self.fetch_businesses(
                domain=company_domain,
                company_name=company_name
            )
            
            if not businesses:
                return None
            
            # Get business IDs
            business_ids = [b.get("business_id") for b in businesses if b.get("business_id")]
            
            if not business_ids:
                return None
            
            # Step 2: Fetch prospects from these businesses
            prospects = self.fetch_prospects_by_business(
                business_ids=business_ids,
                has_email=True,
                max_results=50
            )
            
            if not prospects:
                return None
            
            # Step 3: Find matching prospect by name
            full_name_search = f"{first_name} {last_name}".lower()
            matched_prospect = None
            
            for prospect in prospects:
                prospect_name = prospect.get("full_name", "").lower()
                if first_name.lower() in prospect_name and last_name.lower() in prospect_name:
                    matched_prospect = prospect
                    break
            
            if not matched_prospect:
                # Try first prospect if no exact match
                matched_prospect = prospects[0] if prospects else None
            
            if not matched_prospect:
                return None
            
            # Step 4: Enrich contact info to get email
            prospect_id = matched_prospect.get("prospect_id")
            if not prospect_id:
                return None
            
            contact_info = self.enrich_contact_info(prospect_id)
            
            if not contact_info or not contact_info.get("email"):
                return None
            
            # Combine prospect data with contact info
            return {
                "email": contact_info.get("email"),
                "first_name": matched_prospect.get("first_name") or first_name,
                "last_name": matched_prospect.get("last_name") or last_name,
                "full_name": matched_prospect.get("full_name"),
                "title": matched_prospect.get("job_title"),
                "seniority": matched_prospect.get("job_level"),
                "linkedin_url": matched_prospect.get("linkedin_url"),
                "phone": contact_info.get("mobile_phone") or contact_info.get("phone_numbers"),
                "company_name": matched_prospect.get("company_name"),
                "company_domain": company_domain,
                "source": "explorium",
                "prospect_id": prospect_id
            }
                
        except Exception as e:
            print(f"Explorium match error: {e}")
            return None
    
    def enrich_business(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Enrich business with firmographic data.
        
        This fetches the business and returns basic firmographic information.
        
        Args:
            domain: Company domain
            company_name: Company name
            
        Returns:
            Dictionary with enriched business data
        """
        try:
            businesses = self.fetch_businesses(domain=domain, company_name=company_name)
            
            if not businesses:
                return None
            
            business = businesses[0]
            
            return {
                "company_name": business.get("name"),
                "domain": business.get("domain"),
                "industry": business.get("google_category") or business.get("linkedin_category"),
                "employee_count": business.get("number_of_employees_range"),
                "headquarters": business.get("headquarters_location") or business.get("country_name"),
                "description": business.get("description"),
                "linkedin_url": business.get("linkedin_url"),
                "source": "explorium",
                "business_id": business.get("business_id")
            }
                
        except Exception as e:
            print(f"Explorium business enrichment error: {e}")
            return None

