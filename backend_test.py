"""Backend API tests for Celesta Glow - OTP Auth & Taxonomy Reflection

Tests the following flows:
1. Customer email OTP login (send-otp / verify-otp) - regression fix
2. Admin taxonomy edits reflect on public endpoints (concerns/categories/niches)
"""
import requests
import json
import sys
import os
from pymongo import MongoClient

# Use external URL from frontend/.env
BASE_URL = "https://com7-staging.preview.emergentagent.com/api"
ADMIN_TOKEN = "celestaglow2024"
HEADERS = {"X-Admin-Token": ADMIN_TOKEN}

# MongoDB connection for reading OTP
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

def log(msg):
    print(f"[TEST] {msg}")

def get_otp_from_db(email):
    """Read OTP from MongoDB customer_otps collection"""
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        record = db.customer_otps.find_one({"email": email})
        client.close()
        if record:
            return record.get("otp")
        return None
    except Exception as e:
        log(f"Error reading OTP from DB: {e}")
        return None

def test_customer_otp_login():
    """Test 1: Customer email OTP login flow (regression fix)"""
    log("=" * 80)
    log("TEST 1: Customer Email OTP Login (Regression Fix)")
    log("=" * 80)
    
    email = "qa_tester@example.com"
    errors = []
    
    # Step 1: Send OTP
    log("\nStep 1: POST /api/auth/send-otp")
    send_url = f"{BASE_URL}/auth/send-otp"
    payload = {"email": email}
    
    try:
        resp = requests.post(send_url, json=payload, timeout=30)
        log(f"Status: {resp.status_code}")
        log(f"Response: {resp.text[:500]}")
        
        if resp.status_code != 200:
            errors.append(f"send-otp: Expected 200, got {resp.status_code}")
        else:
            data = resp.json()
            if not data.get("success"):
                errors.append(f"send-otp: success=false")
            else:
                log(f"✓ success: {data.get('success')}")
            
            # Check delivered flag
            delivered = data.get("delivered")
            log(f"✓ delivered: {delivered}")
            if delivered != True:
                errors.append(f"send-otp: delivered={delivered}, expected True (Gmail SMTP should be configured)")
    
    except Exception as e:
        errors.append(f"send-otp exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 2: Read OTP from MongoDB
    log("\nStep 2: Read OTP from MongoDB customer_otps collection")
    otp = get_otp_from_db(email)
    if not otp:
        errors.append("Could not read OTP from MongoDB")
        log(f"❌ Could not read OTP from DB")
    else:
        log(f"✓ OTP from DB: {otp}")
    
    # Step 3: Verify OTP
    if otp:
        log("\nStep 3: POST /api/auth/verify-otp")
        verify_url = f"{BASE_URL}/auth/verify-otp"
        verify_payload = {
            "email": email,
            "otp": otp
        }
        
        try:
            resp = requests.post(verify_url, json=verify_payload, timeout=30)
            log(f"Status: {resp.status_code}")
            log(f"Response: {resp.text[:500]}")
            
            if resp.status_code != 200:
                errors.append(f"verify-otp: Expected 200, got {resp.status_code}")
            else:
                data = resp.json()
                if not data.get("success"):
                    errors.append(f"verify-otp: success=false")
                else:
                    log(f"✓ success: {data.get('success')}")
                
                # Check token
                token = data.get("token")
                if not token:
                    errors.append("verify-otp: No token returned")
                else:
                    log(f"✓ token: {token[:20]}...")
                
                # Check user object
                user = data.get("user")
                if not user:
                    errors.append("verify-otp: No user object returned")
                else:
                    log(f"✓ user.email: {user.get('email')}")
                    if user.get("email") != email:
                        errors.append(f"verify-otp: user.email mismatch, expected {email}, got {user.get('email')}")
        
        except Exception as e:
            errors.append(f"verify-otp exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Step 4: Confirm old wrong path returns 404
    log("\nStep 4: Confirm OLD wrong path POST /api/customer/send-otp returns 404")
    old_url = f"{BASE_URL}/customer/send-otp"
    try:
        resp = requests.post(old_url, json={"email": email}, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 404:
            errors.append(f"old-path: Expected 404, got {resp.status_code} (old path should not exist)")
        else:
            log(f"✓ Old path correctly returns 404")
    
    except Exception as e:
        errors.append(f"old-path exception: {e}")
    
    # Summary
    if errors:
        log("\n❌ TEST 1 FAILED with errors:")
        for err in errors:
            log(f"  - {err}")
        return False
    
    log("\n✅ TEST 1 PASSED: Customer OTP login working correctly")
    return True


def test_taxonomy_reflection():
    """Test 2: Admin taxonomy edits reflect on public endpoints"""
    log("\n" + "=" * 80)
    log("TEST 2: Admin Taxonomy Edits Reflect on Public Endpoints")
    log("=" * 80)
    
    errors = []
    
    # Test Concerns
    log("\n--- Testing Concerns ---")
    
    # Step 1: GET /api/concerns (public)
    log("\nStep 1: GET /api/concerns (public)")
    concerns_url = f"{BASE_URL}/concerns"
    
    try:
        resp = requests.get(concerns_url, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            errors.append(f"GET concerns: Expected 200, got {resp.status_code}")
            return False
        
        concerns = resp.json()
        if not concerns or not isinstance(concerns, list):
            errors.append("GET concerns: No concerns returned or not a list")
            return False
        
        log(f"✓ Found {len(concerns)} concerns")
        
        # Pick first concern
        concern = concerns[0]
        concern_slug = concern.get("slug")
        original_description = concern.get("description", "")
        original_sort_order = concern.get("sort_order", 99)
        
        log(f"✓ Testing with concern: {concern_slug}")
        log(f"  Original description: {original_description[:50]}...")
        log(f"  Original sort_order: {original_sort_order}")
        
    except Exception as e:
        errors.append(f"GET concerns exception: {e}")
        return False
    
    # Step 2: PUT /api/admin/concerns/{slug} - change description
    log(f"\nStep 2: PUT /api/admin/concerns/{concern_slug} (admin)")
    admin_concern_url = f"{BASE_URL}/admin/concerns/{concern_slug}"
    
    # Create update payload with modified description
    new_description = f"{original_description} [TEST EDIT]"
    update_payload = {
        "slug": concern_slug,
        "name": concern.get("name"),
        "tagline": concern.get("tagline", ""),
        "icon": concern.get("icon", ""),
        "image": concern.get("image", ""),
        "accent_from": concern.get("accent_from", "#dcfce7"),
        "accent_to": concern.get("accent_to", "#bbf7d0"),
        "accent_text": concern.get("accent_text", "#14532d"),
        "description": new_description,
        "sort_order": concern.get("sort_order", 99),
        "is_active": concern.get("is_active", True),
        "niche": concern.get("niche", "skincare")
    }
    
    try:
        resp = requests.put(admin_concern_url, json=update_payload, headers=HEADERS, timeout=10)
        log(f"Status: {resp.status_code}")
        log(f"Response: {resp.text[:200]}")
        
        if resp.status_code != 200:
            errors.append(f"PUT concern: Expected 200, got {resp.status_code}")
        else:
            data = resp.json()
            if not data.get("success"):
                errors.append(f"PUT concern: success=false")
            else:
                log(f"✓ Concern updated successfully")
    
    except Exception as e:
        errors.append(f"PUT concern exception: {e}")
    
    # Step 3: GET /api/concerns again to verify change
    log("\nStep 3: GET /api/concerns again to verify change")
    
    try:
        resp = requests.get(concerns_url, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            errors.append(f"GET concerns (verify): Expected 200, got {resp.status_code}")
        else:
            concerns = resp.json()
            updated_concern = next((c for c in concerns if c.get("slug") == concern_slug), None)
            
            if not updated_concern:
                errors.append(f"GET concerns (verify): Could not find concern {concern_slug}")
            else:
                updated_description = updated_concern.get("description", "")
                log(f"  Updated description: {updated_description[:80]}...")
                
                if "[TEST EDIT]" not in updated_description:
                    errors.append(f"GET concerns (verify): Change not reflected. Expected '[TEST EDIT]' in description")
                else:
                    log(f"✓ Change reflected in public endpoint")
    
    except Exception as e:
        errors.append(f"GET concerns (verify) exception: {e}")
    
    # Step 4: Restore original value
    log(f"\nStep 4: Restore original concern description")
    restore_payload = {**update_payload, "description": original_description}
    
    try:
        resp = requests.put(admin_concern_url, json=restore_payload, headers=HEADERS, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            log(f"✓ Concern restored to original state")
        else:
            log(f"⚠ Could not restore concern: {resp.status_code}")
    
    except Exception as e:
        log(f"⚠ Restore concern exception: {e}")
    
    # Test Categories
    log("\n--- Testing Categories ---")
    
    # Step 5: GET /api/categories (public)
    log("\nStep 5: GET /api/categories (public)")
    categories_url = f"{BASE_URL}/categories"
    
    try:
        resp = requests.get(categories_url, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            errors.append(f"GET categories: Expected 200, got {resp.status_code}")
        else:
            categories = resp.json()
            if not categories or not isinstance(categories, list):
                errors.append("GET categories: No categories returned or not a list")
            else:
                log(f"✓ Found {len(categories)} categories")
                
                # Pick first category
                category = categories[0]
                category_slug = category.get("slug")
                original_tagline = category.get("tagline", "")
                
                log(f"✓ Testing with category: {category_slug}")
                log(f"  Original tagline: {original_tagline}")
    
    except Exception as e:
        errors.append(f"GET categories exception: {e}")
        category_slug = None
    
    # Step 6: PUT /api/admin/categories/{slug} - change tagline
    if category_slug:
        log(f"\nStep 6: PUT /api/admin/categories/{category_slug} (admin)")
        admin_category_url = f"{BASE_URL}/admin/categories/{category_slug}"
        
        # Partial update - only send fields we want to change
        new_tagline = f"{original_tagline} [TEST]"
        category_update = {
            "tagline": new_tagline
        }
        
        try:
            resp = requests.put(admin_category_url, json=category_update, headers=HEADERS, timeout=10)
            log(f"Status: {resp.status_code}")
            log(f"Response: {resp.text[:200]}")
            
            if resp.status_code != 200:
                errors.append(f"PUT category: Expected 200, got {resp.status_code}")
            else:
                data = resp.json()
                if not data.get("success"):
                    errors.append(f"PUT category: success=false")
                else:
                    log(f"✓ Category updated successfully")
        
        except Exception as e:
            errors.append(f"PUT category exception: {e}")
        
        # Step 7: GET /api/categories again to verify change
        log("\nStep 7: GET /api/categories again to verify change")
        
        try:
            resp = requests.get(categories_url, timeout=10)
            log(f"Status: {resp.status_code}")
            
            if resp.status_code != 200:
                errors.append(f"GET categories (verify): Expected 200, got {resp.status_code}")
            else:
                categories = resp.json()
                updated_category = next((c for c in categories if c.get("slug") == category_slug), None)
                
                if not updated_category:
                    errors.append(f"GET categories (verify): Could not find category {category_slug}")
                else:
                    updated_tagline = updated_category.get("tagline", "")
                    log(f"  Updated tagline: {updated_tagline}")
                    
                    if "[TEST]" not in updated_tagline:
                        errors.append(f"GET categories (verify): Change not reflected. Expected '[TEST]' in tagline")
                    else:
                        log(f"✓ Change reflected in public endpoint")
        
        except Exception as e:
            errors.append(f"GET categories (verify) exception: {e}")
        
        # Step 8: Restore original value
        log(f"\nStep 8: Restore original category tagline")
        restore_category = {"tagline": original_tagline}
        
        try:
            resp = requests.put(admin_category_url, json=restore_category, headers=HEADERS, timeout=10)
            log(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                log(f"✓ Category restored to original state")
            else:
                log(f"⚠ Could not restore category: {resp.status_code}")
        
        except Exception as e:
            log(f"⚠ Restore category exception: {e}")
    
    # Test Niches
    log("\n--- Testing Niches ---")
    
    # Step 9: GET /api/niches (public)
    log("\nStep 9: GET /api/niches (public)")
    niches_url = f"{BASE_URL}/niches"
    
    try:
        resp = requests.get(niches_url, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            errors.append(f"GET niches: Expected 200, got {resp.status_code}")
        else:
            niches = resp.json()
            if not niches or not isinstance(niches, list):
                errors.append("GET niches: No niches returned or not a list")
            else:
                log(f"✓ Found {len(niches)} active niches")
                for niche in niches:
                    log(f"  - {niche.get('slug')}: {niche.get('name')}")
    
    except Exception as e:
        errors.append(f"GET niches exception: {e}")
    
    # Summary
    if errors:
        log("\n❌ TEST 2 FAILED with errors:")
        for err in errors:
            log(f"  - {err}")
        return False
    
    log("\n✅ TEST 2 PASSED: Admin taxonomy edits reflect on public endpoints")
    return True


def main():
    log("Starting Celesta Glow Backend Tests - OTP Auth & Taxonomy Reflection")
    log(f"Base URL: {BASE_URL}")
    log(f"Admin Token: {ADMIN_TOKEN[:10]}...")
    
    results = {}
    
    # Test 1: Customer OTP Login
    results["test_1_customer_otp_login"] = test_customer_otp_login()
    
    # Test 2: Taxonomy Reflection
    results["test_2_taxonomy_reflection"] = test_taxonomy_reflection()
    
    # Summary
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        log("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        log(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
