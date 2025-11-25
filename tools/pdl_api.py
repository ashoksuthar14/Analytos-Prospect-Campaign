"""
PDL (People Data Labs) API integration tool.
"""

from typing import Dict, Any, Optional
from tools.base_tool import BaseTool


class PDLAPI(BaseTool):
    """
    PDL API client for data enrichment.
    
    Documentation: https://docs.peoplelabs.io/
    """
    
    def __init__(self, api_key: str):
        """
        Initialize PDL API client.
        
        Args:
            api_key: PDL API key
        """
        super().__init__(api_key=api_key, base_url="https://api.peopledatalabs.com/v5")
    
    def _setup_auth(self) -> None:
        """Setup PDL API authentication."""
        self.session.headers.update({
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        })
    
    def enrich_company(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich company data.
        
        Args:
            domain: Company domain
            company_name: Company name (fallback)
            
        Returns:
            Enriched company data dictionary
        """
        if not domain and not company_name:
            raise ValueError("Either domain or company_name must be provided")
        
        # Use domain if available
        if domain:
            response = self._make_request(
                method="GET",
                endpoint=f"/company/enrich",
                params={"website": domain}
            )
        else:
            # Search by name
            response = self._make_request(
                method="GET",
                endpoint=f"/company/search",
                params={"name": company_name}
            )
            # Get first result if available
            if response.get("data"):
                response = response["data"][0]
        
        company_data = response.get("data", response) if isinstance(response, dict) else {}
        
        return {
            "linkedin_url": company_data.get("linkedin_url"),
            "tech_stack": company_data.get("technologies", []),
            "firmographics": {
                "founded_year": company_data.get("founded"),
                "headquarters": company_data.get("location", {}).get("locality"),
                "description": company_data.get("description"),
                "tags": company_data.get("tags", [])
            },
            "role_details": {}
        }
    
    def enrich_person(
        self,
        email: Optional[str] = None,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich person/contact data.
        
        Args:
            email: Contact email
            domain: Company domain
            
        Returns:
            Enriched person data dictionary
        """
        if email:
            response = self._make_request(
                method="GET",
                endpoint=f"/person/enrich",
                params={"email": email}
            )
        elif domain:
            response = self._make_request(
                method="GET",
                endpoint=f"/company/enrich",
                params={"website": domain}
            )
        else:
            raise ValueError("Either email or domain must be provided")
        
        data = response.get("data", response) if isinstance(response, dict) else {}
        
        return {
            "linkedin_url": data.get("linkedin_url"),
            "tech_stack": data.get("company", {}).get("technologies", []),
            "firmographics": {
                "founded_year": data.get("company", {}).get("founded"),
                "headquarters": data.get("location", {}).get("locality"),
                "description": data.get("company", {}).get("description"),
                "tags": data.get("company", {}).get("tags", [])
            },
            "role_details": {
                "seniority": data.get("seniority"),
                "role": data.get("job_title"),
                "email": data.get("emails", [{}])[0].get("address") if data.get("emails") else None
            }
        }

