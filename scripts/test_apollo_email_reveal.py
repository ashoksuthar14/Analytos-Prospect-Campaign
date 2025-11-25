"""
Test script to diagnose Apollo email reveal issue.

This script tests if your Apollo API key and plan support email reveal.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

def test_apollo_email_reveal():
    """Test Apollo API email reveal functionality."""
    
    print("=" * 70)
    print("Apollo Email Reveal Diagnostic Test")
    print("=" * 70)
    print()
    
    # Check API key
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        print("❌ ERROR: APOLLO_API_KEY not found in .env file")
        print("   Please add APOLLO_API_KEY to your .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    print()
    
    # Test 1: Basic API connectivity
    print("Test 1: Basic API Connectivity")
    print("-" * 70)
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        response = requests.get(
            "https://api.apollo.io/v1/auth/health",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ API connectivity OK")
        else:
            print(f"⚠️ API returned status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False
    
    print()
    
    # Test 2: Search without email reveal
    print("Test 2: Search WITHOUT Email Reveal")
    print("-" * 70)
    
    payload_no_reveal = {
        "page": 1,
        "per_page": 1,
        "person_titles": ["CEO", "Founder"],
        "organization_locations": ["United States"]
    }
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/mixed_people/search",
            headers=headers,
            json=payload_no_reveal,
            timeout=30
        )
        
        data = response.json()
        
        if response.status_code != 200:
            print(f"❌ ERROR: {response.status_code}")
            print(f"Message: {data.get('error', data)}")
            return False
        
        people = data.get("people", [])
        if people:
            person = people[0]
            email = person.get("email", "")
            name = person.get("name", "Unknown")
            org_name = person.get("organization", {}).get("name", "Unknown")
            
            print(f"✅ Search successful")
            print(f"   Contact: {name}")
            print(f"   Company: {org_name}")
            print(f"   Email: {email}")
            
            if "email_not_unlocked" in str(email):
                print("   Status: Email is LOCKED (expected without reveal)")
            else:
                print("   Status: Email is VISIBLE (no reveal needed!)")
        else:
            print("⚠️ No results found")
            return False
            
    except Exception as e:
        print(f"❌ Search failed: {str(e)}")
        return False
    
    print()
    
    # Test 3: Search WITH email reveal
    print("Test 3: Search WITH Email Reveal (reveal_personal_emails: true)")
    print("-" * 70)
    
    payload_with_reveal = {
        "page": 1,
        "per_page": 1,
        "person_titles": ["CEO", "Founder"],
        "organization_locations": ["United States"],
        "reveal_personal_emails": True,  # CRITICAL PARAMETER
        "reveal_phone_number": True
    }
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/mixed_people/search",
            headers=headers,
            json=payload_with_reveal,
            timeout=30
        )
        
        data = response.json()
        
        if response.status_code != 200:
            print(f"❌ ERROR: {response.status_code}")
            print(f"Message: {data.get('error', data)}")
            
            # Check for specific error messages
            error_msg = str(data.get('error', data))
            if "not enabled" in error_msg.lower() or "not available" in error_msg.lower():
                print()
                print("🚨 DIAGNOSIS: Email reveal is NOT enabled on your Apollo plan")
                print("   Solution: Upgrade to Professional plan or higher")
                print("   Cost: $99/month (Professional) or $149/month (Organization)")
                return False
            return False
        
        people = data.get("people", [])
        if people:
            person = people[0]
            email = person.get("email", "")
            name = person.get("name", "Unknown")
            org_name = person.get("organization", {}).get("name", "Unknown")
            
            print(f"✅ Search successful with reveal parameter")
            print(f"   Contact: {name}")
            print(f"   Company: {org_name}")
            print(f"   Email: {email}")
            print()
            
            if "email_not_unlocked" in str(email) or "@domain.com" in str(email):
                print("❌ DIAGNOSIS: Email reveal is NOT working")
                print()
                print("   Possible reasons:")
                print("   1. Apollo plan doesn't support email reveal (most common)")
                print("   2. Insufficient email credits")
                print("   3. API key doesn't have email reveal permission")
                print()
                print("   SOLUTION:")
                print("   • Check your plan: apollo.io → Settings → Billing")
                print("   • Upgrade to Professional plan ($99/month)")
                print("   • Or contact Apollo support: support@apollo.io")
                return False
            else:
                print("✅ SUCCESS! Email reveal is WORKING!")
                print()
                print("   Your Apollo API is correctly configured.")
                print("   Emails will be revealed in the workflow.")
                return True
        else:
            print("⚠️ No results found")
            return False
            
    except Exception as e:
        print(f"❌ Search with reveal failed: {str(e)}")
        return False
    
    print()


def check_apollo_credits():
    """Check Apollo credit balance."""
    
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        return
    
    print()
    print("=" * 70)
    print("Checking Apollo Credit Balance")
    print("=" * 70)
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        response = requests.get(
            "https://api.apollo.io/v1/auth/health",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # Note: Credit info might not be in health endpoint
            # You may need to check Apollo dashboard manually
            print("ℹ️  Check your credit balance manually:")
            print("   1. Go to apollo.io")
            print("   2. Settings → API")
            print("   3. Check 'Credits Remaining'")
        else:
            print("⚠️ Could not check credit balance via API")
            print("   Check manually in Apollo dashboard")
            
    except Exception as e:
        print(f"⚠️ Could not check credits: {str(e)}")


def main():
    """Run all diagnostic tests."""
    
    success = test_apollo_email_reveal()
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if success:
        print("✅ Apollo email reveal is WORKING")
        print("   Your workflow should work correctly now.")
    else:
        print("❌ Apollo email reveal is NOT working")
        print()
        print("RECOMMENDED ACTIONS:")
        print("1. Check your Apollo plan (Settings → Billing)")
        print("2. Upgrade to Professional plan ($99/month)")
        print("3. Or contact Apollo support: support@apollo.io")
        print()
        print("ALTERNATIVE OPTIONS:")
        print("• Add Hunter.io API for email finding ($49/month)")
        print("• Add Clay API for email waterfall ($149/month)")
        print("• Use manual email export workaround")
    
    check_apollo_credits()
    
    print()
    print("=" * 70)
    print("For more information, see: APOLLO_EMAIL_ISSUE_FIXES.md")
    print("=" * 70)


if __name__ == "__main__":
    main()

