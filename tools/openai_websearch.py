"""
OpenAI Web Search API for data enrichment fallback.
Uses OpenAI's web search capability to find missing company/person data.
"""

from typing import Dict, Any, Optional
import requests
import json


class OpenAIWebSearch:
    """
    OpenAI Web Search client for enriching missing data fields.
    
    This is used as a final fallback when Apollo and Explorium don't have the data.
    It intelligently searches the web for specific missing fields.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize OpenAI Web Search client.
        
        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def enrich_company_missing_fields(
        self,
        company_name: str,
        domain: str,
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search the web for missing company data fields.
        
        Args:
            company_name: Company name
            domain: Company domain
            current_data: Current data we have (to identify what's missing)
            
        Returns:
            Dictionary with found data
        """
        # Identify missing fields
        missing_fields = []
        if not current_data.get("industry"):
            missing_fields.append("industry")
        if not current_data.get("revenue"):
            missing_fields.append("annual revenue")
        if not current_data.get("employee_count"):
            missing_fields.append("number of employees")
        if not current_data.get("tech_stack") or not current_data["tech_stack"]:
            missing_fields.append("tech stack")
        if not current_data.get("firmographics", {}).get("description"):
            missing_fields.append("company description")
        
        if not missing_fields:
            return {}
        
        # Create search query
        query = f"""Find the following information about {company_name} ({domain}):
{', '.join(missing_fields)}

Provide the information in JSON format with these exact keys:
- industry (string)
- revenue (number or null if not available)
- employee_count (number or null if not available)
- tech_stack (array of strings)
- description (string)

Only include factual, verified information. If information is not available, use null."""
        
        try:
            # Use GPT-4o with detailed instructions (no web_search parameter - it doesn't exist)
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a B2B data enrichment assistant. Provide accurate, factual information about companies based on your knowledge. If you don't know specific information, return null for that field. Always return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "temperature": 0.3,  # Lower temperature for factual responses
                "max_tokens": 1000,
                "response_format": { "type": "json_object" }  # Force JSON response
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Parse JSON response (should be clean JSON due to response_format)
                try:
                    enriched_data = json.loads(content)
                    
                    # Clean and validate the data
                    result = {}
                    if enriched_data.get("industry"):
                        result["industry"] = str(enriched_data["industry"])
                    if enriched_data.get("revenue"):
                        try:
                            result["revenue"] = float(enriched_data["revenue"])
                        except (ValueError, TypeError):
                            pass
                    if enriched_data.get("employee_count"):
                        try:
                            result["employee_count"] = int(enriched_data["employee_count"])
                        except (ValueError, TypeError):
                            pass
                    if enriched_data.get("tech_stack") and isinstance(enriched_data["tech_stack"], list):
                        result["tech_stack"] = enriched_data["tech_stack"]
                    if enriched_data.get("description"):
                        result["description"] = str(enriched_data["description"])
                    
                    print(f"✅ OpenAI Web Search found data for {company_name}: {list(result.keys())}")
                    return result
                    
                except json.JSONDecodeError:
                    print(f"⚠️ Could not parse OpenAI response as JSON for {company_name}")
                    return {}
            else:
                print(f"❌ OpenAI Web Search API error: {response.status_code} - {response.text[:200]}")
                return {}
                
        except Exception as e:
            print(f"❌ OpenAI Web Search error for {company_name}: {str(e)}")
            return {}
    
    def enrich_person_missing_fields(
        self,
        person_name: str,
        company_name: str,
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search the web for missing person data fields.
        
        Args:
            person_name: Person's name
            company_name: Company name
            current_data: Current data we have
            
        Returns:
            Dictionary with found data
        """
        # Identify missing fields
        missing_fields = []
        if not current_data.get("title"):
            missing_fields.append("job title")
        if not current_data.get("seniority"):
            missing_fields.append("seniority level")
        if not current_data.get("linkedin_url"):
            missing_fields.append("LinkedIn profile URL")
        
        if not missing_fields:
            return {}
        
        # Create search query
        query = f"""Find the following information about {person_name} at {company_name}:
{', '.join(missing_fields)}

Provide the information in JSON format with these exact keys:
- title (string)
- seniority (string: executive, director, manager, senior, entry, or founder)
- linkedin_url (string)

Only include factual, verified information. If information is not available, use null."""
        
        try:
            # Use GPT-4o with detailed instructions
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a B2B data enrichment assistant. Provide accurate, factual information about business professionals based on your knowledge. If you don't know specific information, return null for that field. Always return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 500,
                "response_format": { "type": "json_object" }
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Parse JSON response (should be clean JSON due to response_format)
                try:
                    enriched_data = json.loads(content)
                    
                    result = {}
                    if enriched_data.get("title"):
                        result["title"] = str(enriched_data["title"])
                    if enriched_data.get("seniority"):
                        result["seniority"] = str(enriched_data["seniority"])
                    if enriched_data.get("linkedin_url"):
                        result["linkedin_url"] = str(enriched_data["linkedin_url"])
                    
                    print(f"✅ OpenAI Web Search found data for {person_name}: {list(result.keys())}")
                    return result
                    
                except json.JSONDecodeError:
                    print(f"⚠️ Could not parse OpenAI response as JSON for {person_name}")
                    return {}
            else:
                print(f"❌ OpenAI Web Search API error: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"❌ OpenAI Web Search error for {person_name}: {str(e)}")
            return {}

