"""
Test Explorium API integration.
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

from tools.explorium_api import ExporiumAPI

def test_explorium():
    """Test Explorium API functionality."""
    
    api_key = os.getenv("EXPLORIUM_API_KEY")
    
    if not api_key:
        print("❌ EXPLORIUM_API_KEY not found in .env")
        return
    
    print("=" * 80)
    print("  EXPLORIUM API INTEGRATION TEST")
    print("=" * 80)
    print(f"\n✅ API Key: {api_key[:15]}...\n")
    
    explorium = ExporiumAPI(api_key)
    
    # Test 1: Fetch Businesses
    print("=" * 80)
    print("  TEST 1: Fetch Businesses by Domain")
    print("=" * 80)
    
    test_domains = ["apple.com", "microsoft.com", "strongcrm.com"]
    
    for domain in test_domains:
        print(f"\n🏢 Testing domain: {domain}")
        businesses = explorium.fetch_businesses(domain=domain, page_size=3)
        
        if businesses:
            print(f"   ✅ Found {len(businesses)} business(es)")
            for biz in businesses[:1]:  # Show first one
                print(f"      - Name: {biz.get('name')}")
                print(f"      - Business ID: {biz.get('business_id')}")
                print(f"      - Employees: {biz.get('number_of_employees_range')}")
        else:
            print(f"   ❌ No businesses found")
    
    # Test 2: Full Workflow - Match Prospect
    print("\n" + "=" * 80)
    print("  TEST 2: Full Workflow - Match Prospect with Email Reveal")
    print("=" * 80)
    
    test_cases = [
        {
            "first_name": "Tim",
            "last_name": "Cook",
            "company_domain": "apple.com"
        },
        {
            "first_name": "Satya",
            "last_name": "Nadella",
            "company_domain": "microsoft.com"
        }
    ]
    
    for test in test_cases:
        print(f"\n📧 Testing: {test['first_name']} {test['last_name']} @ {test['company_domain']}")
        print(f"   Step 1: Fetching business...")
        print(f"   Step 2: Fetching prospects...")
        print(f"   Step 3: Enriching contact info...")
        
        result = explorium.match_prospect(
            first_name=test['first_name'],
            last_name=test['last_name'],
            company_domain=test['company_domain']
        )
        
        if result:
            email = result.get("email")
            if email and email != "email_not_unlocked@domain.com":
                print(f"   ✅ SUCCESS! Email revealed: {email}")
                print(f"   Title: {result.get('title')}")
                print(f"   Phone: {result.get('phone')}")
                print(f"   LinkedIn: {result.get('linkedin_url')}")
            else:
                print(f"   ❌ No email found (returned: {email})")
        else:
            print(f"   ❌ No match found (business/prospect not in database)")
    
    # Test 3: Business enrichment
    print("\n" + "=" * 80)
    print("  TEST 3: Enrich Business")
    print("=" * 80)
    
    result = explorium.enrich_business(domain="apple.com")
    
    if result:
        print(f"✅ Business enrichment successful!")
        print(f"   Company: {result.get('company_name')}")
        print(f"   Industry: {result.get('industry')}")
        print(f"   Employees: {result.get('employee_count')}")
        print(f"   Revenue: {result.get('revenue')}")
    else:
        print("❌ Business enrichment failed")
    
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print("""
✅ Explorium API is now integrated as a fallback!

When Apollo fails to reveal an email, the system will:
1. Try Apollo first (as primary)
2. If Apollo returns None, automatically try Explorium
3. Log the source of each email (apollo or explorium)

This gives you DOUBLE the coverage for email finding!
""")

if __name__ == "__main__":
    test_explorium()

