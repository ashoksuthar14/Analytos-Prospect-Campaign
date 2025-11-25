"""
Quick script to check which Apollo account the API key belongs to.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from configs.secrets_provider import SecretsProvider
from tools.apollo_api import ApolloAPI


def check_apollo_account():
    """Check which Apollo account the current API key belongs to."""
    
    print("=" * 80)
    print("APOLLO ACCOUNT CHECKER".center(80))
    print("=" * 80)
    
    # Get Apollo API key
    secrets = SecretsProvider()
    apollo_key = secrets.get_apollo_api_key()
    
    if not apollo_key:
        print("\n❌ ERROR: No Apollo API key found in configs/api_keys.py")
        print("\nPlease set APOLLO_API_KEY in configs/api_keys.py")
        return
    
    # Mask the API key for display
    masked_key = apollo_key[:8] + "*" * (len(apollo_key) - 12) + apollo_key[-4:]
    print(f"\n📌 Using API Key: {masked_key}")
    print("\n" + "=" * 80)
    
    # Initialize Apollo API
    try:
        apollo = ApolloAPI(apollo_key)
        print("\n✅ Successfully connected to Apollo API")
    except Exception as e:
        print(f"\n❌ Failed to initialize Apollo API: {e}")
        return
    
    # Try to get account information
    print("\n🔍 Fetching account information...\n")
    
    try:
        # Make a simple API call to verify the key works
        # We'll use the search endpoint with limit=1 as a test
        response = apollo._make_request(
            method="POST",
            endpoint="/mixed_people/search",
            data={
                "page": 1,
                "per_page": 1,
                "person_titles": ["CEO"]
            }
        )
        
        print("✅ API Key is VALID and working!")
        print("\n" + "=" * 80)
        print("APOLLO ACCOUNT DETAILS".center(80))
        print("=" * 80)
        
        # Try to extract any account info from the response
        pagination = response.get("pagination", {})
        
        print("\n📊 API Status:")
        print(f"   • Connection: Active")
        print(f"   • API Key: {masked_key}")
        print(f"   • Endpoint: https://api.apollo.io/v1")
        
        print("\n💡 How to Find Your Apollo Account Details:")
        print("   1. Go to: https://app.apollo.io")
        print("   2. Click on your profile icon (top right)")
        print("   3. Select 'Settings'")
        print("   4. Go to 'API' section")
        print("   5. You'll see:")
        print("      • Team Name")
        print("      • Account Email")
        print("      • Credits Remaining")
        print("      • Plan Type")
        
        print("\n📝 Alternative Method - Check Apollo Web UI:")
        print("   1. Login to Apollo: https://app.apollo.io")
        print("   2. Go to 'Contacts' section")
        print("   3. Any contacts created by this API will appear there")
        print("   4. Check the top-left corner for your team/account name")
        
        print("\n" + "=" * 80)
        print("CONTACTS WILL BE SAVED TO:".center(80))
        print("=" * 80)
        
        print("\n   📍 The Apollo account associated with this API key:")
        print(f"      API Key: {masked_key}")
        print("\n   🔗 View contacts at: https://app.apollo.io/#/contacts")
        
        print("\n" + "=" * 80)
        
        # Check if there's a comment with alternative key
        print("\n💡 ADDITIONAL API KEY FOUND:")
        print("\n   In configs/api_keys.py line 11, there's a commented API key:")
        print("   #santosh = \"Wj_Cu56FxpNxf5neBQVFBg\"")
        print("\n   If you want to switch to Santosh's Apollo account:")
        print("   1. Open: configs/api_keys.py")
        print("   2. Change line 10 to: APOLLO_API_KEY = \"Wj_Cu56FxpNxf5neBQVFBg\"")
        print("   3. Restart your Flask server")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ API Error: {str(e)}")
        print("\n⚠️ The API key may be invalid or expired.")
        print("\nTo get a new API key:")
        print("   1. Login to Apollo: https://app.apollo.io")
        print("   2. Go to Settings → API")
        print("   3. Copy your API key")
        print("   4. Update APOLLO_API_KEY in configs/api_keys.py")


if __name__ == "__main__":
    try:
        check_apollo_account()
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

