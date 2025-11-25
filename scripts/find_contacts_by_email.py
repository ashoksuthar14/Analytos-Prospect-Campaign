"""
Script to find contacts in Apollo by email from the latest workflow run.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_service import DatabaseService
from tools.apollo_api import ApolloAPI
from configs.api_keys import APOLLO_API_KEY


def get_latest_run_leads(db_service: DatabaseService):
    """Get leads from the most recent workflow run."""
    with db_service.get_connection() as conn:
        # Get the most recent run ID
        cursor = conn.execute("""
            SELECT run_id FROM runs 
            ORDER BY started_at DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if not row:
            return []
        
        run_id = row["run_id"]
        
        # Get leads from that run
        cursor = conn.execute("""
            SELECT 
                lead_id,
                company_name,
                contact_name,
                contact_email,
                contact_title,
                score
            FROM leads
            WHERE run_id = ?
            AND contact_email IS NOT NULL
            AND contact_email NOT LIKE '%email_not_unlocked%'
            ORDER BY score DESC
        """, (run_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def search_contact_by_email(apollo_api: ApolloAPI, email: str):
    """Search for a contact in Apollo by email."""
    try:
        response = apollo_api._make_request(
            method="POST",
            endpoint="/contacts/search",
            data={
                "q_keywords": email,
                "page": 1,
                "per_page": 10
            }
        )
        
        contacts = response.get("contacts", [])
        # Filter to exact email match
        matches = [c for c in contacts if c.get("email") == email]
        return matches
    except Exception as e:
        print(f"   ❌ Error searching: {e}")
        return []


def main():
    """Main function."""
    print("="*80)
    print("Find Contacts in Apollo by Email")
    print("="*80)
    
    # Initialize services
    db_service = DatabaseService()
    
    if not APOLLO_API_KEY:
        print("\n❌ Apollo API key not found")
        return
    
    apollo_api = ApolloAPI(APOLLO_API_KEY)
    
    # Get latest run leads
    print("\n🔍 Getting leads from latest workflow run...")
    leads = get_latest_run_leads(db_service)
    
    if not leads:
        print("❌ No leads found in the latest run")
        return
    
    print(f"✅ Found {len(leads)} leads with emails")
    
    # Search for each contact
    print("\n" + "="*80)
    print("Searching Apollo for Contacts")
    print("="*80)
    
    found_count = 0
    not_found_count = 0
    
    for i, lead in enumerate(leads, 1):
        email = lead['contact_email']
        name = lead['contact_name']
        company = lead['company_name']
        
        print(f"\n{i}. {name} @ {company}")
        print(f"   Email: {email}")
        print(f"   Searching Apollo...")
        
        matches = search_contact_by_email(apollo_api, email)
        
        if matches:
            contact = matches[0]
            apollo_id = contact.get('id')
            
            print(f"   ✅ FOUND in Apollo!")
            print(f"   Apollo Contact ID: {apollo_id}")
            print(f"   Title: {contact.get('title', 'N/A')}")
            print(f"   Email Status: {contact.get('email_status', 'N/A')}")
            
            # Update database with Apollo ID
            try:
                with db_service.get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE leads 
                        SET apollo_contact_id = ?,
                            apollo_sync_status = 'verified'
                        WHERE lead_id = ?
                        """,
                        (apollo_id, lead['lead_id'])
                    )
                print(f"   💾 Updated database with Apollo ID")
            except Exception as e:
                print(f"   ⚠️  Could not update database: {e}")
            
            found_count += 1
        else:
            print(f"   ❌ NOT FOUND in Apollo")
            not_found_count += 1
    
    # Summary
    print("\n" + "="*80)
    print("Search Summary")
    print("="*80)
    print(f"   Total Searched: {len(leads)}")
    print(f"   ✅ Found in Apollo: {found_count}")
    print(f"   ❌ Not Found: {not_found_count}")
    
    if found_count > 0:
        print(f"\n🎉 Successfully located and updated {found_count} contacts!")
        print(f"\n💡 Now you can run: python scripts/verify_synced_contacts.py")
    
    print("="*80)


if __name__ == "__main__":
    main()

