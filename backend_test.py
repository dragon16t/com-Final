"""Backend API tests for Celesta Glow media generation endpoints.

Tests the following flows:
1. POST /api/admin/products/{slug}/generate-images - gallery, certificate, before_after generation
2. POST /api/admin/ai/one-click-product - create product WITHOUT images (placeholder bottle)
3. GET /api/products?generated_from={slug} - verify badge fields
4. GET /api/before-after/{slug} - verify before/after images
5. POST /api/admin/products/{slug}/generate-variations - 24-variation generation
"""
import requests
import json
import sys

# Use internal localhost URL for testing
BASE_URL = "http://localhost:8001/api"
ADMIN_TOKEN = "celestaglow2024"
HEADERS = {"X-Admin-Token": ADMIN_TOKEN}

def log(msg):
    print(f"[TEST] {msg}")

def test_generate_images():
    """Test 1: POST /api/admin/products/advanced-face-serum/generate-images"""
    log("=" * 80)
    log("TEST 1: Generate images/certificate/before-after for advanced-face-serum")
    log("=" * 80)
    
    url = f"{BASE_URL}/admin/products/advanced-face-serum/generate-images"
    payload = {
        "gallery": True,
        "certificate": True,
        "before_after": True
    }
    
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=60)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {resp.status_code}")
            log(f"Response: {resp.text[:500]}")
            return False
        
        data = resp.json()
        log(f"Response keys: {list(data.keys())}")
        
        # Verify response structure
        errors = []
        
        # Check images list
        if "images" not in data:
            errors.append("Missing 'images' field")
        elif not isinstance(data["images"], list):
            errors.append("'images' is not a list")
        elif len(data["images"]) < 4:
            errors.append(f"'images' has {len(data['images'])} items, expected >= 4")
        else:
            log(f"✓ images: {len(data['images'])} items")
            # Verify first few image URLs
            for i, img in enumerate(data["images"][:3]):
                log(f"  - Image {i}: {img}")
        
        # Check test_report_image (certificate)
        if "test_report_image" not in data:
            errors.append("Missing 'test_report_image' field")
        elif not data["test_report_image"]:
            errors.append("'test_report_image' is empty")
        else:
            log(f"✓ test_report_image: {data['test_report_image']}")
        
        # Check before_after list
        if "before_after" not in data:
            errors.append("Missing 'before_after' field")
        elif not isinstance(data["before_after"], list):
            errors.append("'before_after' is not a list")
        elif len(data["before_after"]) != 2:
            errors.append(f"'before_after' has {len(data['before_after'])} items, expected 2")
        else:
            log(f"✓ before_after: {len(data['before_after'])} items")
            # Verify types
            types = [item.get("type") for item in data["before_after"]]
            if "before" not in types or "after" not in types:
                errors.append(f"before_after types incorrect: {types}")
            else:
                log(f"  - Types: {types}")
        
        # Test image URL accessibility
        if "images" in data and data["images"]:
            test_url = data["images"][0]
            if test_url.startswith("/api/"):
                test_url = f"http://localhost:8001{test_url}"
            try:
                img_resp = requests.get(test_url, timeout=10)
                if img_resp.status_code == 200:
                    log(f"✓ Image URL is fetchable: {test_url}")
                else:
                    errors.append(f"Image URL returned {img_resp.status_code}: {test_url}")
            except Exception as e:
                errors.append(f"Failed to fetch image URL: {e}")
        
        # Test certificate URL
        if "test_report_image" in data and data["test_report_image"]:
            cert_url = data["test_report_image"]
            if cert_url.startswith("/api/"):
                cert_url = f"http://localhost:8001{cert_url}"
            try:
                cert_resp = requests.get(cert_url, timeout=10)
                if cert_resp.status_code == 200:
                    log(f"✓ Certificate URL is fetchable: {cert_url}")
                else:
                    errors.append(f"Certificate URL returned {cert_resp.status_code}: {cert_url}")
            except Exception as e:
                errors.append(f"Failed to fetch certificate URL: {e}")
        
        # Test before/after URLs
        if "before_after" in data and data["before_after"]:
            for item in data["before_after"]:
                img_url = item.get("image")
                if img_url:
                    if img_url.startswith("/api/"):
                        img_url = f"http://localhost:8001{img_url}"
                    try:
                        ba_resp = requests.get(img_url, timeout=10)
                        if ba_resp.status_code == 200:
                            log(f"✓ Before/After {item.get('type')} URL is fetchable")
                        else:
                            errors.append(f"Before/After URL returned {ba_resp.status_code}: {img_url}")
                    except Exception as e:
                        errors.append(f"Failed to fetch before/after URL: {e}")
        
        if errors:
            log("❌ FAILED with errors:")
            for err in errors:
                log(f"  - {err}")
            return False
        
        log("✅ PASSED: All checks successful")
        return True
        
    except Exception as e:
        log(f"❌ FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_one_click_no_image():
    """Test 2: Create product WITHOUT images via one-click-product"""
    log("\n" + "=" * 80)
    log("TEST 2: One-click product WITHOUT images (placeholder bottle)")
    log("=" * 80)
    
    url = f"{BASE_URL}/admin/ai/one-click-product"
    payload = {
        "name": "Zephyr Test Serum",
        "brand": "Celesta Glow",
        "key_ingredients": "Niacinamide, Zinc",
        "generate_image": False
    }
    
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=90)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {resp.status_code}")
            log(f"Response: {resp.text[:500]}")
            return False, None
        
        data = resp.json()
        log(f"Response keys: {list(data.keys())}")
        
        if not data.get("success"):
            log(f"❌ FAILED: success=false")
            return False, None
        
        slug = data.get("slug")
        if not slug:
            log(f"❌ FAILED: No slug returned")
            return False, None
        
        log(f"✓ Product created with slug: {slug}")
        
        # Now GET the product to verify media generation
        get_url = f"{BASE_URL}/products/{slug}"
        get_resp = requests.get(get_url, timeout=10)
        
        if get_resp.status_code != 200:
            log(f"❌ FAILED: Could not fetch product, status {get_resp.status_code}")
            return False, slug
        
        product = get_resp.json()
        errors = []
        
        # Check images (should have >= 4 from gallery)
        if "images" not in product:
            errors.append("Missing 'images' field")
        elif not isinstance(product["images"], list):
            errors.append("'images' is not a list")
        elif len(product["images"]) < 4:
            errors.append(f"'images' has {len(product['images'])} items, expected >= 4 (gallery)")
        else:
            log(f"✓ images: {len(product['images'])} items (auto-composed gallery)")
        
        # Check test_report_image
        if "test_report_image" not in product or not product["test_report_image"]:
            errors.append("Missing or empty 'test_report_image'")
        else:
            log(f"✓ test_report_image: {product['test_report_image']}")
        
        # Check before_after
        if "before_after" not in product:
            errors.append("Missing 'before_after' field")
        elif not isinstance(product["before_after"], list):
            errors.append("'before_after' is not a list")
        elif len(product["before_after"]) != 2:
            errors.append(f"'before_after' has {len(product['before_after'])} items, expected 2")
        else:
            log(f"✓ before_after: {len(product['before_after'])} items")
        
        if errors:
            log("❌ FAILED with errors:")
            for err in errors:
                log(f"  - {err}")
            return False, slug
        
        log("✅ PASSED: Product created with media generation (no hero photo)")
        return True, slug
        
    except Exception as e:
        log(f"❌ FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_products_list_badge_fields():
    """Test 3: GET /api/products?generated_from=advanced-face-serum - verify badge fields"""
    log("\n" + "=" * 80)
    log("TEST 3: List variations with badge fields")
    log("=" * 80)
    
    url = f"{BASE_URL}/products"
    params = {
        "generated_from": "advanced-face-serum",
        "limit": 48
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {resp.status_code}")
            log(f"Response: {resp.text[:500]}")
            return False
        
        data = resp.json()
        
        # Handle both array and paginated response
        if isinstance(data, dict) and "items" in data:
            products = data["items"]
            log(f"Found {len(products)} variations (paginated response)")
        elif isinstance(data, list):
            products = data
            log(f"Found {len(products)} variations (array response)")
        else:
            log(f"❌ FAILED: Unexpected response format")
            return False
        
        if not products:
            log(f"❌ FAILED: No variations found")
            return False
        
        errors = []
        checked = 0
        
        for i, product in enumerate(products[:5]):  # Check first 5
            checked += 1
            slug = product.get("slug", f"item-{i}")
            log(f"\nChecking product: {slug}")
            
            # Check required badge fields
            required_fields = ["target_skin_type", "target_gender", "target_age_group", "concern_label"]
            for field in required_fields:
                if field not in product:
                    errors.append(f"{slug}: Missing '{field}' field")
                elif product[field] is None:
                    errors.append(f"{slug}: '{field}' is null")
                elif not product[field]:
                    errors.append(f"{slug}: '{field}' is empty")
                else:
                    log(f"  ✓ {field}: {product[field]}")
        
        log(f"\nChecked {checked} products")
        
        if errors:
            log("❌ FAILED with errors:")
            for err in errors:
                log(f"  - {err}")
            return False
        
        log("✅ PASSED: All badge fields present and non-null")
        return True
        
    except Exception as e:
        log(f"❌ FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_before_after_endpoint():
    """Test 4: GET /api/before-after/{slug}"""
    log("\n" + "=" * 80)
    log("TEST 4: Before/After endpoint")
    log("=" * 80)
    
    # Test with a variation slug
    slug = "advanced-face-serum-men-oily-18-24"
    url = f"{BASE_URL}/before-after/{slug}"
    
    try:
        resp = requests.get(url, timeout=10)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {resp.status_code}")
            log(f"Response: {resp.text[:500]}")
            return False
        
        data = resp.json()
        
        # Expect a list or dict with rows
        if isinstance(data, dict):
            log(f"Response keys: {list(data.keys())}")
            rows = data.get("rows") or data.get("items") or []
        elif isinstance(data, list):
            log(f"Response is a list with {len(data)} items")
            rows = data
        else:
            log(f"❌ FAILED: Unexpected response format")
            return False
        
        if not rows:
            log(f"❌ FAILED: No before/after rows found")
            return False
        
        log(f"Found {len(rows)} before/after row(s)")
        
        errors = []
        row = rows[0]
        
        # Check before_image
        if "before_image" not in row or not row["before_image"]:
            errors.append("Missing or empty 'before_image'")
        else:
            log(f"✓ before_image: {row['before_image']}")
            # Test URL
            img_url = row["before_image"]
            if img_url.startswith("/api/"):
                img_url = f"http://localhost:8001{img_url}"
            try:
                img_resp = requests.get(img_url, timeout=10)
                if img_resp.status_code == 200:
                    log(f"  ✓ before_image URL is fetchable")
                else:
                    errors.append(f"before_image URL returned {img_resp.status_code}")
            except Exception as e:
                errors.append(f"Failed to fetch before_image: {e}")
        
        # Check after_image
        if "after_image" not in row or not row["after_image"]:
            errors.append("Missing or empty 'after_image'")
        else:
            log(f"✓ after_image: {row['after_image']}")
            # Test URL
            img_url = row["after_image"]
            if img_url.startswith("/api/"):
                img_url = f"http://localhost:8001{img_url}"
            try:
                img_resp = requests.get(img_url, timeout=10)
                if img_resp.status_code == 200:
                    log(f"  ✓ after_image URL is fetchable")
                else:
                    errors.append(f"after_image URL returned {img_resp.status_code}")
            except Exception as e:
                errors.append(f"Failed to fetch after_image: {e}")
        
        if errors:
            log("❌ FAILED with errors:")
            for err in errors:
                log(f"  - {err}")
            return False
        
        log("✅ PASSED: Before/After endpoint working correctly")
        return True
        
    except Exception as e:
        log(f"❌ FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generate_variations():
    """Test 5: POST /api/admin/products/{slug}/generate-variations"""
    log("\n" + "=" * 80)
    log("TEST 5: Generate 24 variations")
    log("=" * 80)
    
    url = f"{BASE_URL}/admin/products/advanced-face-serum/generate-variations"
    payload = {
        "concern": "brightening-glow",
        "concern_label": "Brightening & Glow"
    }
    
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=120)
        log(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {resp.status_code}")
            log(f"Response: {resp.text[:500]}")
            return False
        
        data = resp.json()
        log(f"Response keys: {list(data.keys())}")
        
        errors = []
        
        # Check success
        if not data.get("success"):
            errors.append("success=false")
        
        # Check total
        if "total" not in data:
            errors.append("Missing 'total' field")
        elif data["total"] != 24:
            errors.append(f"Expected total=24, got {data['total']}")
        else:
            log(f"✓ total: {data['total']}")
        
        # Check slugs list
        if "slugs" in data and isinstance(data["slugs"], list):
            log(f"✓ slugs: {len(data['slugs'])} items")
            if data["slugs"]:
                log(f"  Sample slugs: {data['slugs'][:3]}")
        
        if errors:
            log("❌ FAILED with errors:")
            for err in errors:
                log(f"  - {err}")
            return False
        
        log("✅ PASSED: 24 variations generated successfully")
        return True
        
    except Exception as e:
        log(f"❌ FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_product(slug):
    """Clean up test product created during testing"""
    if not slug:
        return
    
    log(f"\nCleaning up test product: {slug}")
    url = f"{BASE_URL}/admin/products/{slug}"
    try:
        resp = requests.delete(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            log(f"✓ Cleaned up {slug}")
        else:
            log(f"⚠ Could not clean up {slug}: {resp.status_code}")
    except Exception as e:
        log(f"⚠ Cleanup failed: {e}")


def main():
    log("Starting Celesta Glow Backend Media Generation Tests")
    log(f"Base URL: {BASE_URL}")
    log(f"Admin Token: {ADMIN_TOKEN[:10]}...")
    
    results = {}
    test_slug = None
    
    # Test 1: Generate images for existing product
    results["test_1_generate_images"] = test_generate_images()
    
    # Test 2: One-click product without images
    passed, test_slug = test_one_click_no_image()
    results["test_2_one_click_no_image"] = passed
    
    # Test 3: List variations with badge fields
    results["test_3_badge_fields"] = test_products_list_badge_fields()
    
    # Test 4: Before/After endpoint
    results["test_4_before_after"] = test_before_after_endpoint()
    
    # Test 5: Generate variations
    results["test_5_generate_variations"] = test_generate_variations()
    
    # Cleanup
    if test_slug:
        cleanup_test_product(test_slug)
    
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
