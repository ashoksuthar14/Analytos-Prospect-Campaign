"""
Script to verify contacts synced to Apollo from the latest workflow run.

This script:
1. Queries database for leads with apollo_contact_id
2. Fetches each contact from Apollo using the View Contact API
3. Displays detailed contact information
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_service import DatabaseService
from tools.apollo_api import ApolloAPI
from configs.api_keys import APOLLO_API_KEY


def get_synced_contacts_from_db(db_service: DatabaseService, limit: int = 10):
    """
    Get contacts that have been synced to Apollo.
    
    Args:
        db_service: Database service instance
        limit: Maximum number of contacts to retrieve
        
    Returns:
        List of lead dictionaries with Apollo contact IDs
    """
    with db_service.get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                lead_id,
                company_name,
                contact_name,
                contact_email,
                contact_title,
                score,
                apollo_contact_id,
                apollo_synced_at,
                apollo_sync_status
            FROM leads
            WHERE apollo_contact_id IS NOT NULL
            ORDER BY apollo_synced_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_contact_from_apollo(apollo_api: ApolloAPI, contact_id: str) -> dict:
    """
    Fetch contact details from Apollo.
    
    Args:
        apollo_api: Apollo API instance
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
        return {"error": str(e)}


def display_contact(contact_data: dict, index: int):
    """Display contact details in a formatted way."""
    contact = contact_data.get("contact", contact_data)
    
    print(f"\n{'='*80}")
    print(f"Contact {index}")
    print(f"{'='*80}")
    
    if "error" in contact:
        print(f"❌ Error: {contact['error']}")
        return
    
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
        revenue = organization.get('estimated_annual_revenue', 0)
        if revenue:
            print(f"   Revenue: ${revenue:,}")
    
    print(f"\n📞 Contact Information:")
    phone_numbers = contact.get('phone_numbers', [])
    if phone_numbers and len(phone_numbers) > 0:
        print(f"   Phone: {phone_numbers[0].get('raw_number', 'N/A')}")
    else:
        print(f"   Phone: N/A")
    
    print(f"   LinkedIn: {contact.get('linkedin_url', 'N/A')}")
    print(f"   City: {contact.get('city', 'N/A')}")
    print(f"   State: {contact.get('state', 'N/A')}")
    print(f"   Country: {contact.get('country', 'N/A')}")
    
    print(f"\n🎯 Apollo Metadata:")
    print(f"   Email Status: {contact.get('email_status', 'N/A')}")
    print(f"   Email Verified: {contact.get('email_needs_tickling', 'N/A')}")
    print(f"   Contact Stage: {contact.get('contact_stage_id', 'N/A')}")
    print(f"   Created At: {contact.get('created_at', 'N/A')}")
    print(f"   Updated At: {contact.get('updated_at', 'N/A')}")
    
    # Labels/Lists
    if contact.get('label_names'):
        print(f"\n🏷️  Labels/Lists:")
        for label in contact.get('label_names', []):
            print(f"   - {label}")


def main():
    """Main function to verify synced contacts."""
    print("="*80)
    print("Verify Contacts Synced to Apollo")
    print("="*80)
    
    # Initialize services
    db_service = DatabaseService()
    
    if not APOLLO_API_KEY:
        print("\n❌ Apollo API key not found in configs/api_keys.py")
        return
    
    apollo_api = ApolloAPI(APOLLO_API_KEY)
    
    # Get synced contacts from database
    print("\n🔍 Retrieving synced contacts from database...")
    synced_contacts = get_synced_contacts_from_db(db_service, limit=10)
    
    if not synced_contacts:
        print("❌ No synced contacts found in database")
        print("\nMake sure you've run a workflow with the apollo_contact_sync agent")
        return
    
    print(f"✅ Found {len(synced_contacts)} synced contacts")
    
    # Display database info
    print("\n" + "="*80)
    print("Database Records")
    print("="*80)
    
    for i, lead in enumerate(synced_contacts, 1):
        print(f"\n{i}. {lead['contact_name']} @ {lead['company_name']}")
        print(f"   Apollo Contact ID: {lead['apollo_contact_id']}")
        print(f"   Synced At: {lead['apollo_synced_at']}")
        print(f"   Sync Status: {lead['apollo_sync_status']}")
        print(f"   Score: {lead['score']}")
    
    # Verify each contact in Apollo
    print("\n" + "="*80)
    print("Verifying Contacts in Apollo")
    print("="*80)
    
    verified_count = 0
    error_count = 0
    
    for i, lead in enumerate(synced_contacts, 1):
        contact_id = lead['apollo_contact_id']
        
        print(f"\n🔍 Fetching contact {i}/{len(synced_contacts)}: {lead['contact_name']}")
        print(f"   Apollo ID: {contact_id}")
        
        # Fetch from Apollo
        contact_data = get_contact_from_apollo(apollo_api, contact_id)
        
        if "error" in contact_data:
            print(f"   ❌ Error: {contact_data['error']}")
            error_count += 1
        elif contact_data.get("contact"):
            contact = contact_data["contact"]
            print(f"   ✅ Found: {contact.get('first_name', '')} {contact.get('last_name', '')}")
            print(f"   Email: {contact.get('email', 'N/A')}")
            print(f"   Title: {contact.get('title', 'N/A')}")
            
            org = contact.get('organization', {})
            if org:
                print(f"   Company: {org.get('name', 'N/A')}")
            
            verified_count += 1
            
            # Display full details
            display_contact(contact_data, i)
        else:
            print(f"   ⚠️  Unexpected response format")
            error_count += 1
    
    # Summary
    print("\n" + "="*80)
    print("Verification Summary")
    print("="*80)
    print(f"   Total Contacts in DB: {len(synced_contacts)}")
    print(f"   ✅ Verified in Apollo: {verified_count}")
    print(f"   ❌ Errors/Not Found: {error_count}")
    
    if verified_count == len(synced_contacts):
        print(f"\n🎉 All contacts successfully verified in Apollo!")
    elif verified_count > 0:
        print(f"\n⚠️  Some contacts could not be verified")
    else:
        print(f"\n❌ No contacts could be verified in Apollo")
    
    print("\n💡 To view in Apollo web interface:")
    print("   1. Go to: https://app.apollo.io")
    print("   2. Click 'Contacts' in the left sidebar")
    print("   3. Search for any contact name or email")
    print("="*80)


if __name__ == "__main__":
    main()

