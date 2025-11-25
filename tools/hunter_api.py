"""
Hunter.io API integration tool for email finding.
"""

from typing import Dict, Any, Optional
from tools.base_tool import BaseTool


class HunterAPI(BaseTool):
    """
    Hunter.io API client for finding email addresses.
    
    Documentation: https://hunter.io/api-documentation
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Hunter.io API client.
        
        Args:
            api_key: Hunter.io API key
        """
        super().__init__(api_key=api_key, base_url="https://api.hunter.io/v2")
    
    def _setup_auth(self) -> None:
        """Setup Hunter.io API authentication."""
        # Hunter.io uses API key as query parameter, not header
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def find_email(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        full_name: Optional[str] = None,
        company: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find email address using Hunter.io email finder.
        
        Args:
            domain: Company domain (e.g., "reddit.com")
            first_name: First name of the person
            last_name: Last name of the person
            full_name: Full name (alternative to first_name + last_name)
            company: Company name (optional, helps with accuracy)
            
        Returns:
            Dictionary with email data if found, None otherwise
            Format: {
                "email": "email@domain.com",
                "score": 97,
                "sources": [...],
                "verification": {
                    "status": "valid",
                    "date": "2025-11-22"
                }
            }
        """
        if not domain:
            return None
        
        # Build query parameters
        params = {
            "api_key": self.api_key,
            "domain": domain
        }
        
        # Add name parameters
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if full_name:
            params["full_name"] = full_name
        if company:
            params["company"] = company
        
        try:
            response = self._make_request(
                method="GET",
                endpoint="/email-finder",
                params=params
            )
            
            # Check if email was found
            if response.get("data") and response["data"].get("email"):
                email_data = response["data"]
                return {
                    "email": email_data.get("email"),
                    "score": email_data.get("score", 0),
                    "sources": email_data.get("sources", []),
                    "verification": email_data.get("verification", {}),
                    "position": email_data.get("position"),
                    "company": email_data.get("company"),
                    "linkedin_url": email_data.get("linkedin_url"),
                    "phone_number": email_data.get("phone_number")
                }
            
            return None
            
        except Exception as e:
            # Log error but don't fail the campaign
            print(f"[HunterAPI] Error finding email for {domain}: {str(e)}")
            return None
    
    def verify_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Verify an email address using Hunter.io.
        
        Args:
            email: Email address to verify
            
        Returns:
            Verification data if successful, None otherwise
        """
        if not email or "@" not in email:
            return None
        
        params = {
            "api_key": self.api_key,
            "email": email
        }
        
        try:
            response = self._make_request(
                method="GET",
                endpoint="/email-verifier",
                params=params
            )
            
            if response.get("data"):
                return {
                    "email": response["data"].get("email"),
                    "result": response["data"].get("result"),  # "deliverable", "undeliverable", "risky", "unknown"
                    "score": response["data"].get("score", 0),
                    "sources": response["data"].get("sources", []),
                    "verification": response["data"].get("verification", {})
                }
            
            return None
            
        except Exception as e:
            print(f"[HunterAPI] Error verifying email {email}: {str(e)}")
            return None
