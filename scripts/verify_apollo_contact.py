"""
Script to verify a contact exists in Apollo.

This script retrieves a contact from Apollo by ID or email to verify it was created.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.apollo_api import ApolloAPI
from configs.api_keys import APOLLO_API_KEY


def get_contact_by_id(apollo_api: ApolloAPI, contact_id: str) -> dict:
    """
    Get contact by Apollo contact ID.
    
    Args:
        apollo_api: ApolloAPI instance
        contact_id: Apollo contact ID
        
    Returns:
        Contact data dictionary
    """
    try:
        response = apollo_api._make_request(
            method="GET",
            endpoint=f"/contacts/{contact_id}",
            params={}
        )
        return response
    except Exception as e:
        print(f"❌ Error retrieving contact: {str(e)}")
        return {}


def search_contacts_by_email(apollo_api: ApolloAPI, email: str) -> list:
    """
    Search for contacts by email address.
    
    Args:
        apollo_api: ApolloAPI instance
        email: Email address to search for
        
    Returns:
        List of matching contacts
    """
    try:
        # Apollo search endpoint for contacts
        response = apollo_api._make_request(
            method="POST",
            endpoint="/contacts/search",
            data={
                "q_keywords": email,
                "page": 1,
                "per_page": 10
            }
        )
        return response.get("contacts", [])
    except Exception as e:
        print(f"❌ Error searching contacts: {str(e)}")
        return []


def display_contact_details(contact: dict):
    """Display contact details in a formatted way."""
    print(f"\n{'='*80}")
    print("Contact Details")
    print(f"{'='*80}")
    
    print(f"\n📋 Basic Information:")
    print(f"   Contact ID: {contact.get('id', 'N/A')}")
    print(f"   Name: {contact.get('first_name', '')} {contact.get('last_name', '')}")
    print(f"   Email: {contact.get('email', 'N/A')}")
    print(f"   Title: {contact.get('title', 'N/A')}")
    print(f"   Seniority: {contact.get('seniority', 'N/A')}")
    
    print(f"\n🏢 Organization:")
    organization = contact.get('organization', {})
    if organization:
        print(f"   Company: {organization.get('name', 'N/A')}")
        print(f"   Website: {organization.get('website_url', 'N/A')}")
        print(f"   Industry: {organization.get('industry', 'N/A')}")
        print(f"   Employees: {organization.get('estimated_num_employees', 'N/A')}")
        print(f"   Revenue: ${organization.get('estimated_annual_revenue', 0):,}")
    
    print(f"\n📞 Contact Information:")
    print(f"   Phone: {contact.get('phone_numbers', [{}])[0].get('raw_number', 'N/A') if contact.get('phone_numbers') else 'N/A'}")
    print(f"   LinkedIn: {contact.get('linkedin_url', 'N/A')}")
    print(f"   City: {contact.get('city', 'N/A')}")
    print(f"   State: {contact.get('state', 'N/A')}")
    print(f"   Country: {contact.get('country', 'N/A')}")
    
    print(f"\n🎯 Apollo Metadata:")
    print(f"   Account ID: {contact.get('account_id', 'N/A')}")
    print(f"   Contact Stage: {contact.get('contact_stage_id', 'N/A')}")
    print(f"   Email Status: {contact.get('email_status', 'N/A')}")
    print(f"   Email Needs Tickling: {contact.get('email_needs_tickling', 'N/A')}")
    print(f"   Created At: {contact.get('created_at', 'N/A')}")
    print(f"   Updated At: {contact.get('updated_at', 'N/A')}")
    
    # Labels/Lists
    if contact.get('label_names'):
        print(f"\n🏷️  Labels/Lists:")
        for label in contact.get('label_names', []):
            print(f"   - {label}")
    
    print(f"\n{'='*80}")


def main():
    """Main function to verify Apollo contact."""
    print("="*80)
    print("Verify Contact in Apollo")
    print("="*80)
    
    # Initialize Apollo API
    if not APOLLO_API_KEY:
        print("\n❌ Apollo API key not found in configs/api_keys.py")
        return
    
    apollo_api = ApolloAPI(APOLLO_API_KEY)
    
    # The contact ID from the previous creation
    contact_id = "690ed34c506927001585ffdd"
    contact_email = "john@provenroi.com"
    
    print(f"\n🔍 Method 1: Retrieving contact by ID: {contact_id}")
    contact = get_contact_by_id(apollo_api, contact_id)
    
    if contact and contact.get('contact'):
        print("✅ Contact found by ID!")
        display_contact_details(contact.get('contact'))
    else:
        print("⚠️  Could not retrieve contact by ID")
        print(f"Response: {json.dumps(contact, indent=2)}")
        
        # Try searching by email instead
        print(f"\n🔍 Method 2: Searching for contact by email: {contact_email}")
        contacts = search_contacts_by_email(apollo_api, contact_email)
        
        if contacts:
            print(f"✅ Found {len(contacts)} contact(s) matching '{contact_email}'")
            for i, contact in enumerate(contacts, 1):
                print(f"\n--- Contact {i} ---")
                display_contact_details(contact)
        else:
            print("❌ No contacts found by email search")
    
    print("\n" + "="*80)
    print("Verification Complete")
    print("="*80)
    print("\n💡 To view in Apollo web interface:")
    print("   1. Go to: https://app.apollo.io")
    print("   2. Click 'Contacts' in the left sidebar")
    print("   3. Search for: 'John Cronin' or 'john@provenroi.com'")
    print("="*80)


if __name__ == "__main__":
    main()

