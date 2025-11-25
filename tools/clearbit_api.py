"""
Clearbit API integration tool.
"""

from typing import Dict, Any, Optional
from tools.base_tool import BaseTool


class ClearbitAPI(BaseTool):
    """
    Clearbit API client for data enrichment.
    
    Documentation: https://clearbit.com/docs
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Clearbit API client.
        
        Args:
            api_key: Clearbit API key
        """
        super().__init__(api_key=api_key, base_url="https://person.clearbit.com/v2")
    
    def _setup_auth(self) -> None:
        """Setup Clearbit API authentication."""
        self.session.auth = (self.api_key, "")  # Clearbit uses basic auth
    
    def enrich_company(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich company data.
        
        Args:
            domain: Company domain
            company_name: Company name (fallback if domain not available)
            
        Returns:
            Enriched company data dictionary
        """
        if not domain and not company_name:
            raise ValueError("Either domain or company_name must be provided")
        
        # Use domain if available, otherwise search by name
        if domain:
            endpoint = f"/combined/find/domain/{domain}"
        else:
            endpoint = f"/combined/find/name/{company_name}"
        
        response = self._make_request(
            method="GET",
            endpoint=endpoint
        )
        
        company_data = response.get("company", {})
        person_data = response.get("person", {})
        
        return {
            "linkedin_url": company_data.get("linkedin", {}).get("handle"),
            "tech_stack": company_data.get("tech", []),
            "firmographics": {
                "founded_year": company_data.get("foundedYear"),
                "headquarters": company_data.get("geo", {}).get("city"),
                "description": company_data.get("description"),
                "tags": company_data.get("tags", [])
            },
            "role_details": {
                "seniority": person_data.get("employment", {}).get("seniority"),
                "role": person_data.get("employment", {}).get("title")
            }
        }
    
    def enrich_lead(
        self,
        email: Optional[str] = None,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich lead/contact data.
        
        Args:
            email: Contact email
            domain: Company domain
            
        Returns:
            Enriched contact data dictionary
        """
        if email:
            # Person enrichment
            response = self._make_request(
                method="GET",
                endpoint=f"/combined/find/email/{email}"
            )
        elif domain:
            # Company enrichment
            response = self._make_request(
                method="GET",
                endpoint=f"/combined/find/domain/{domain}"
            )
        else:
            raise ValueError("Either email or domain must be provided")
        
        company_data = response.get("company", {})
        person_data = response.get("person", {})
        
        return {
            "linkedin_url": person_data.get("linkedin", {}).get("handle") or company_data.get("linkedin", {}).get("handle"),
            "tech_stack": company_data.get("tech", []),
            "firmographics": {
                "founded_year": company_data.get("foundedYear"),
                "headquarters": company_data.get("geo", {}).get("city"),
                "description": company_data.get("description"),
                "tags": company_data.get("tags", [])
            },
            "role_details": {
                "seniority": person_data.get("employment", {}).get("seniority"),
                "role": person_data.get("employment", {}).get("title"),
                "email": person_data.get("email")
            }
        }

