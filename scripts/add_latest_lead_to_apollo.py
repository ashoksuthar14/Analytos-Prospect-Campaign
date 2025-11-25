"""
Script to add the latest lead from database to Apollo as a contact.

This script:
1. Retrieves the most recent lead from the database
2. Extracts enrichment data
3. Maps lead fields to Apollo contact creation format
4. Creates the contact in Apollo using the API
"""

import sys
import json
from pathlib import Path
from typing import Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_service import DatabaseService
from tools.apollo_api import ApolloAPI
from configs.api_keys import APOLLO_API_KEY


def parse_name(full_name: str) -> Tuple[str, str]:
    """
    Parse full name into first and last name.
    
    Args:
        full_name: Full name string
        
    Returns:
        Tuple of (first_name, last_name)
    """
    if not full_name:
        return ("", "")
    
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ("", "")
    elif len(parts) == 1:
        return (parts[0], "")
    else:
        # First name is first part, last name is everything else
        return (parts[0], " ".join(parts[1:]))


def extract_enrichment_data(lead: dict) -> dict:
    """
    Extract enrichment data from lead.
    
    Args:
        lead: Lead dictionary from database
        
    Returns:
        Dictionary with enrichment fields
    """
    enrichment = {}
    
    # Parse enrichment_data JSON if present
    if lead.get("enrichment_data"):
        try:
            enrichment = json.loads(lead["enrichment_data"])
        except (json.JSONDecodeError, TypeError):
            enrichment = {}
    
    return enrichment


def build_website_url(domain: str) -> str:
    """
    Build website URL from domain.
    
    Args:
        domain: Domain string (may or may not include protocol)
        
    Returns:
        Full website URL
    """
    if not domain:
        return ""
    
    domain = domain.strip()
    # Remove existing protocol if present
    domain = domain.replace("http://", "").replace("https://", "").replace("www.", "")
    
    # Add https:// if no protocol
    if domain:
        return f"https://{domain}"
    return ""


def create_apollo_contact_from_lead(lead: dict, apollo_api: ApolloAPI) -> dict:
    """
    Create Apollo contact from lead data.
    
    Args:
        lead: Lead dictionary from database
        apollo_api: ApolloAPI instance
        
    Returns:
        Response from Apollo API
    """
    # Parse contact name
    contact_name = lead.get("contact_name", "")
    first_name, last_name = parse_name(contact_name)
    
    # If we don't have a last name, try to get it from enrichment data
    if not last_name:
        enrichment = extract_enrichment_data(lead)
        # Could check enrichment for name parts, but for now use what we have
    
    # Get required fields
    organization_name = lead.get("company_name", "")
    email = lead.get("contact_email")
    title = lead.get("contact_title")
    domain = lead.get("domain")
    location = lead.get("location")
    
    # Extract enrichment data for additional fields
    enrichment = extract_enrichment_data(lead)
    
    # Build website URL from domain
    website_url = ""
    if domain:
        website_url = build_website_url(domain)
    elif enrichment.get("domain"):
        website_url = build_website_url(enrichment.get("domain"))
    
    # Get location from enrichment firmographics if not in lead
    present_raw_address = location
    if not present_raw_address and enrichment.get("firmographics"):
        firmographics = enrichment.get("firmographics", {})
        present_raw_address = firmographics.get("headquarters")
    
    # Prepare contact data
    contact_data = {
        "first_name": first_name or "Unknown",
        "last_name": last_name or "Contact",
        "organization_name": organization_name,
        "run_dedupe": True  # Prevent duplicates
    }
    
    # Add optional fields
    if email:
        contact_data["email"] = email
    if title:
        contact_data["title"] = title
    elif enrichment.get("title"):
        contact_data["title"] = enrichment.get("title")
    elif enrichment.get("role_details", {}).get("role"):
        contact_data["title"] = enrichment.get("role_details", {}).get("role")
    
    if website_url:
        contact_data["website_url"] = website_url
    
    if present_raw_address:
        contact_data["present_raw_address"] = present_raw_address
    
    # Phone numbers from enrichment (if available)
    # Note: Apollo API doesn't return phone in enrichment, but we can add if we have it
    
    print(f"\n📝 Creating contact in Apollo:")
    print(f"   Name: {first_name} {last_name}")
    print(f"   Company: {organization_name}")
    print(f"   Email: {email or 'N/A'}")
    print(f"   Title: {contact_data.get('title', 'N/A')}")
    print(f"   Website: {website_url or 'N/A'}")
    print(f"   Location: {present_raw_address or 'N/A'}")
    
    # Create contact
    try:
        response = apollo_api.create_contact(**contact_data)
        return response
    except Exception as e:
        print(f"\n❌ Error creating contact: {str(e)}")
        raise


def main():
    """Main function to add latest lead to Apollo."""
    print("=" * 80)
    print("Add Latest Lead to Apollo")
    print("=" * 80)
    
    # Initialize database service
    db_service = DatabaseService()
    
    # Get latest lead
    print("\n🔍 Retrieving latest lead from database...")
    
    # Get all leads ordered by created_at DESC, limit 1
    with db_service.get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM leads 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
    
    if not row:
        print("❌ No leads found in database!")
        return
    
    # Convert row to dictionary
    lead = dict(row)
    
    print(f"✅ Found latest lead:")
    print(f"   Lead ID: {lead.get('lead_id')}")
    print(f"   Company: {lead.get('company_name')}")
    print(f"   Contact: {lead.get('contact_name')}")
    print(f"   Email: {lead.get('contact_email')}")
    print(f"   Created: {lead.get('created_at')}")
    
    # Initialize Apollo API
    if not APOLLO_API_KEY:
        print("\n❌ Apollo API key not found in configs/api_keys.py")
        return
    
    apollo_api = ApolloAPI(APOLLO_API_KEY)
    
    # Create contact in Apollo
    try:
        response = create_apollo_contact_from_lead(lead, apollo_api)
        
        # Check response
        if response and response.get("contact"):
            contact = response.get("contact", {})
            print(f"\n✅ Successfully created contact in Apollo!")
            print(f"   Contact ID: {contact.get('id')}")
            print(f"   Name: {contact.get('name')}")
            print(f"   Title: {contact.get('title')}")
            print(f"   Email Status: {contact.get('email_needs_tickling', 'N/A')}")
        else:
            print(f"\n⚠️  Unexpected response from Apollo API:")
            print(json.dumps(response, indent=2))
            
    except Exception as e:
        print(f"\n❌ Failed to create contact: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    main()

