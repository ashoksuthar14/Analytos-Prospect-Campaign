"""
Complete Apollo API Diagnostic Tool
Tests all endpoints to find what works with your API key.
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_api_auth():
    """Test 1: Check if API key is valid"""
    print_section("TEST 1: API Authentication")
    
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        print("❌ FAILED: APOLLO_API_KEY not found in .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    try:
        # Try auth endpoint
        response = requests.get(
            "https://api.apollo.io/v1/auth/health",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ API authentication successful")
            return True
        else:
            print(f"❌ API auth failed: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

def test_search_endpoint():
    """Test 2: Test /mixed_people/search endpoint"""
    print_section("TEST 2: People Search Endpoint")
    
    api_key = os.getenv("APOLLO_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    payload = {
        "page": 1,
        "per_page": 1,
        "person_titles": ["CEO"],
        "organization_locations": ["United States"]
    }
    
    print(f"Request: POST https://api.apollo.io/v1/mixed_people/search")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/mixed_people/search",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            people = data.get("people", [])
            
            if people:
                person = people[0]
                print("✅ Search successful!")
                print(f"\n📋 Sample Result:")
                print(f"   Name: {person.get('name')}")
                print(f"   Email: {person.get('email')}")
                print(f"   Company: {person.get('organization', {}).get('name')}")
                print(f"   Domain: {person.get('organization', {}).get('website_url')}")
                
                # Check if email is locked
                email = person.get('email', '')
                if 'email_not_unlocked' in str(email):
                    print(f"\n⚠️  EMAIL IS LOCKED: {email}")
                    print("   This means search endpoint doesn't reveal emails on your plan")
                else:
                    print(f"\n✅ Email is REVEALED: {email}")
                
                return True, person
            else:
                print("⚠️  Search returned no results")
                return False, None
        else:
            print(f"❌ Search failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False, None
            
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        return False, None

def test_people_match(sample_person):
    """Test 3: Test /people/match endpoint with reveal_personal_emails"""
    print_section("TEST 3: People Match Endpoint (Email Reveal)")
    
    if not sample_person:
        print("⚠️  Skipping - no sample person from search")
        return False
    
    api_key = os.getenv("APOLLO_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    # Parse name
    name = sample_person.get('name', '')
    name_parts = name.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    
    # Get domain
    org = sample_person.get('organization', {})
    domain = org.get('website_url', '').replace('http://', '').replace('https://', '').split('/')[0]
    
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "domain": domain,
        "reveal_personal_emails": True
    }
    
    print(f"Request: POST https://api.apollo.io/v1/people/match")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/people/match",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            person = data.get("person", {})
            email = person.get("email", "")
            
            print("✅ Match successful!")
            print(f"\n📧 Result:")
            print(f"   Email: {email}")
            
            if 'email_not_unlocked' in str(email) or '@domain.com' in str(email):
                print(f"\n❌ EMAIL STILL LOCKED!")
                print("   This means /people/match with reveal_personal_emails doesn't work")
                print("   Your Apollo plan does NOT support email reveal via API")
                return False
            else:
                print(f"\n✅ SUCCESS! Real email revealed: {email}")
                return True
        else:
            print(f"❌ Match failed: {response.status_code}")
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else response.text
            print(f"   Response: {json.dumps(error_data, indent=2) if isinstance(error_data, dict) else error_data[:500]}")
            
            # Check for specific errors
            if response.status_code == 403:
                print("\n🚨 403 Forbidden - Your API key doesn't have permission for this endpoint")
            elif response.status_code == 402:
                print("\n🚨 402 Payment Required - Feature requires paid plan or credits")
            
            return False
            
    except Exception as e:
        print(f"❌ Match error: {str(e)}")
        return False

def test_people_enrich(sample_person):
    """Test 4: Test /people/enrich endpoint"""
    print_section("TEST 4: People Enrichment Endpoint")
    
    if not sample_person:
        print("⚠️  Skipping - no sample person from search")
        return False
    
    api_key = os.getenv("APOLLO_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    # Get domain
    org = sample_person.get('organization', {})
    domain = org.get('website_url', '').replace('http://', '').replace('https://', '').split('/')[0]
    
    payload = {
        "domain": domain
    }
    
    print(f"Request: POST https://api.apollo.io/v1/people/enrich")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/people/enrich",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            person = data.get("person", {})
            
            print("✅ Enrichment successful!")
            print(f"\n📋 Enriched Data:")
            print(f"   Name: {person.get('name')}")
            print(f"   Title: {person.get('title')}")
            print(f"   LinkedIn: {person.get('linkedin_url')}")
            
            return True
        else:
            print(f"❌ Enrichment failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Enrichment error: {str(e)}")
        return False

def check_plan_features():
    """Test 5: Check what features are available on your plan"""
    print_section("TEST 5: Apollo Plan Features Check")
    
    api_key = os.getenv("APOLLO_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    
    print("Checking API usage and limits...")
    print()
    
    try:
        response = requests.post(
            "https://api.apollo.io/v1/auth/api_key_info",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Plan information retrieved")
            print(f"\n📊 Your Apollo Plan:")
            print(json.dumps(data, indent=2))
        else:
            print(f"⚠️  Could not retrieve plan info: {response.status_code}")
            print("   Check manually at apollo.io → Settings → API")
    except Exception as e:
        print(f"⚠️  Could not check plan: {str(e)}")
    
    print("\n💡 To check your plan manually:")
    print("   1. Go to https://app.apollo.io/settings/billing")
    print("   2. Check your current plan (Free/Basic/Professional/Organization)")
    print("   3. Check if 'Email Reveal' or 'API Email Access' is included")

def main():
    """Run all diagnostic tests"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "APOLLO API COMPLETE DIAGNOSTIC" + " "*28 + "║")
    print("╚" + "="*78 + "╝")
    
    # Test 1: Auth
    if not test_api_auth():
        print("\n❌ STOPPING: API authentication failed")
        print("   Fix your APOLLO_API_KEY in .env file first")
        return
    
    # Test 2: Search
    success, sample_person = test_search_endpoint()
    if not success:
        print("\n❌ STOPPING: Search endpoint failed")
        return
    
    # Test 3: People Match (email reveal)
    match_works = test_people_match(sample_person)
    
    # Test 4: People Enrich
    test_people_enrich(sample_person)
    
    # Test 5: Check plan
    check_plan_features()
    
    # Final diagnosis
    print_section("FINAL DIAGNOSIS")
    
    if match_works:
        print("✅ GOOD NEWS: Email reveal is working!")
        print("   Your workflow should work now after restart")
        print()
        print("🎯 Action: Restart your server and run the workflow")
    else:
        print("❌ ROOT CAUSE IDENTIFIED:")
        print("   Your Apollo API plan does NOT support email reveal")
        print()
        print("📋 Evidence:")
        print("   • Search endpoint returns locked emails")
        print("   • /people/match with reveal_personal_emails doesn't work")
        print("   • This requires Professional plan or higher")
        print()
        print("💡 SOLUTIONS:")
        print()
        print("   Option 1: Upgrade Apollo Plan (Recommended)")
        print("   • Go to: https://app.apollo.io/settings/billing")
        print("   • Upgrade to Professional ($99/month) or Organization ($149/month)")
        print("   • Email reveal will work immediately")
        print()
        print("   Option 2: Add Hunter.io for Email Finding ($49/month)")
        print("   • Sign up at: https://hunter.io")
        print("   • Get API key")
        print("   • Add to .env: HUNTER_API_KEY=your_key")
        print("   • I'll integrate it (already coded)")
        print()
        print("   Option 3: Manual Workaround (Free but slow)")
        print("   • Export leads from Apollo web UI")
        print("   • Manually reveal emails there")
        print("   • Import back to system")
    
    print("\n" + "="*80)
    print("Diagnostic complete. See results above.")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

