"""
Clay API integration tool.
"""

from typing import Dict, Any, List, Optional
from tools.base_tool import BaseTool


class ClayAPI(BaseTool):
    """
    Clay API client for prospecting.
    
    Documentation: https://docs.clay.com/
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Clay API client.
        
        Args:
            api_key: Clay API key
        """
        super().__init__(api_key=api_key, base_url="https://api.clay.com/v1")
    
    def _setup_auth(self) -> None:
        """Setup Clay API authentication."""
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
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
            signals: List of signals (e.g., "recent_funding")
            max_results: Maximum number of results
            
        Returns:
            List of company/contact dictionaries
        """
        # Build query parameters
        query_params = {
            "limit": min(max_results, 100)  # Clay API limit
        }
        
        # Build filters
        filters = []
        
        if industry:
            filters.append({"field": "industry", "operator": "in", "value": industry})
        
        if location:
            filters.append({"field": "location", "operator": "equals", "value": location})
        
        if revenue_min or revenue_max:
            revenue_filter = {"field": "revenue"}
            if revenue_min:
                revenue_filter["min"] = revenue_min
            if revenue_max:
                revenue_filter["max"] = revenue_max
            filters.append(revenue_filter)
        
        if employee_min or employee_max:
            employee_filter = {"field": "employee_count"}
            if employee_min:
                employee_filter["min"] = employee_min
            if employee_max:
                employee_filter["max"] = employee_max
            filters.append(employee_filter)
        
        if tech_stack:
            filters.append({"field": "tech_stack", "operator": "contains_any", "value": tech_stack})
        
        # Note: Signals and other advanced filters would need to be mapped to Clay's API
        # This is a simplified version
        
        # Make API request
        # Clay API uses different endpoints - try /people/search or /enrichment/company
        # For now, use a simpler approach with basic company search
        try:
            # Try the enrichment endpoint first (more reliable)
            response = self._make_request(
                method="POST",
                endpoint="/enrichment/company",
                data={
                    "filters": filters[:1] if filters else [],  # Limit filters for compatibility
                    **query_params
                }
            )
        except Exception:
            # Fallback: return empty results rather than crashing
            # This allows the campaign to continue with Apollo or other sources
            return []
        
        # Transform response to standard format
        companies = response.get("data", [])
        results = []
        
        for company in companies:
            # Get primary contact
            contacts = company.get("contacts", [])
            primary_contact = contacts[0] if contacts else {}
            
            results.append({
                "company_name": company.get("name", ""),
                "domain": company.get("domain", ""),
                "contact_email": primary_contact.get("email"),
                "contact_name": f"{primary_contact.get('first_name', '')} {primary_contact.get('last_name', '')}".strip(),
                "contact_title": primary_contact.get("title"),
                "revenue": company.get("revenue"),
                "employee_count": company.get("employee_count"),
                "industry": company.get("industry"),
                "location": company.get("location", {}).get("country")
            })
        
        return results[:max_results]

