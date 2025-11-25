"""
Test Apollo API email reveal with detailed debugging.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

def test_email_reveal():
    """Test email reveal with different approaches."""
    
    if not APOLLO_API_KEY:
        print("❌ APOLLO_API_KEY not found in .env")
        return
    
    print("=" * 80)
    print("  APOLLO EMAIL REVEAL DEBUG TEST")
    print("=" * 80)
    print(f"\n✅ API Key: {APOLLO_API_KEY[:15]}...\n")
    
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY
    }
    
    # Test 1: Check account info
    print("=" * 80)
    print("  TEST 1: Account Information")
    print("=" * 80)
    
    try:
        response = requests.get(
            "https://api.apollo.io/v1/auth/health",
            headers=headers,
            timeout=30
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: People match with reveal
    print("\n" + "=" * 80)
    print("  TEST 2: People Match with Email Reveal")
    print("=" * 80)
    
    test_cases = [
        {
            "first_name": "Tim",
            "last_name": "Cook",
            "domain": "apple.com"
        },
        {
            "first_name": "Elon",
            "last_name": "Musk",
            "domain": "tesla.com"
        }
    ]
    
    for test in test_cases:
        print(f"\n📧 Testing: {test['first_name']} {test['last_name']} @ {test['domain']}")
        
        payload = {
            **test,
            "reveal_personal_emails": True
        }
        
        try:
            response = requests.post(
                "https://api.apollo.io/v1/people/match",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                person = data.get("person", {})
                email = person.get("email")
                
                print(f"   Name: {person.get('first_name')} {person.get('last_name')}")
                print(f"   Email: {email}")
                print(f"   Title: {person.get('title')}")
                
                if email and email != "email_not_unlocked@domain.com":
                    print(f"   ✅ SUCCESS! Real email revealed: {email}")
                else:
                    print(f"   ❌ Email not revealed (locked or None)")
            else:
                print(f"   ❌ Error: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    # Test 3: Check credits/limits
    print("\n" + "=" * 80)
    print("  TEST 3: Email Credits Check")
    print("=" * 80)
    print("\n⚠️  To check your email credits:")
    print("   1. Go to: https://app.apollo.io/settings/credits")
    print("   2. Look for 'Email Credits' or 'Export Credits'")
    print("   3. Check 'API Usage' section")
    print("\n💡 If you have 0 credits, email reveal will return None")
    print("💡 Free plans typically don't include email reveal via API")
    
    print("\n" + "=" * 80)
    print("  DIAGNOSIS")
    print("=" * 80)
    print("""
📋 Based on the test results:

1. If Status Code = 200 but Email = None or "email_not_unlocked":
   → Your plan doesn't include email reveal OR you're out of credits
   
2. If Status Code = 403:
   → Endpoint not accessible on your plan
   
3. If Status Code = 402:
   → Out of credits

✅ SOLUTION:
   - Upgrade your Apollo plan to include email reveal
   - Or purchase email credits if your plan supports it
   - Check: https://app.apollo.io/settings/billing
""")

if __name__ == "__main__":
    test_email_reveal()

