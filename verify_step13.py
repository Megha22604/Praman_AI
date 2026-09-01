import urllib.request
import json
import time

def verify():
    time.sleep(1)

    print("1. Checking Live Port 8000 OpenAPI Schema for Product History Route...")
    with urllib.request.urlopen("http://127.0.0.1:8000/openapi.json") as resp:
        schema = json.loads(resp.read().decode())
        paths = list(schema.get("paths", {}).keys())
        print("   Routes found in OpenAPI schema:")
        for p in paths:
            print("    ", p)

    assert "/api/products/{product_id}/history" in paths
    print("\n   [PASS] Route GET /api/products/{product_id}/history registered in Swagger/OpenAPI!")

    print("\n2. Testing Live HTTP GET /api/products/1/history...")
    url = "http://127.0.0.1:8000/api/products/1/history"
    with urllib.request.urlopen(url) as resp:
        print("   Status:", resp.status)
        data = json.loads(resp.read().decode())
        print("   product_id:", data["product_id"])
        print("   product_name:", data["product_name"])
        print("   brand:", data["brand"])
        print("   Returned items count:", len(data["items"]))
        print("   Total:", data["total"])
        print("   Total Pages:", data["total_pages"])

    print("\n3. Testing Live HTTP GET /api/products/999999999/history (Unknown Product 404)...")
    url404 = "http://127.0.0.1:8000/api/products/999999999/history"
    try:
        with urllib.request.urlopen(url404) as resp:
            print("   Unexpected status:", resp.status)
    except urllib.error.HTTPError as err:
        print("   Status:", err.code)
        err_body = json.loads(err.read().decode())
        print("   Error Detail:", err_body["detail"])
        assert err.code == 404
        assert err_body["detail"] == "Product not found"

    print("\n[SUCCESS] Live HTTP server test for GET /api/products/{product_id}/history PASSED!")

if __name__ == "__main__":
    verify()
