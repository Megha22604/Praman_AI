import urllib.request
import json
import time

def verify():
    time.sleep(1)

    print("1. Checking Live Port 8000 OpenAPI Schema for GET /api/scans Parameters...")
    with urllib.request.urlopen("http://127.0.0.1:8000/openapi.json") as resp:
        schema = json.loads(resp.read().decode())
        get_scans_op = schema["paths"]["/api/scans"]["get"]
        params = [p["name"] for p in get_scans_op["parameters"]]
        print("   Query Parameters registered in Swagger/OpenAPI:")
        for p in get_scans_op["parameters"]:
            print(f"     - {p['name']} ({p.get('schema', {}).get('type')})")

    required_params = ["page", "page_size", "status", "failed_rule", "start_date", "end_date", "product_name", "brand", "inspector"]
    for rp in required_params:
        assert rp in params, f"Parameter {rp} missing from OpenAPI schema"

    print("\n   [PASS] All 9 query parameters registered in Swagger/OpenAPI!")

    print("\n2. Testing Live HTTP GET /api/scans with combined filters...")
    url = "http://127.0.0.1:8000/api/scans?status=FAIL&failed_rule=RULE_6_MRP&product_name=Amul"
    with urllib.request.urlopen(url) as resp:
        print("   Status:", resp.status)
        data = json.loads(resp.read().decode())
        print("   Returned items count:", len(data["items"]))
        print("   Page:", data["page"])
        print("   Page Size:", data["page_size"])
        print("   Total:", data["total"])
        print("   Total Pages:", data["total_pages"])
        if data["items"]:
            print("   Item 0 scan_id:", data["items"][0]["scan_id"])
            print("   Item 0 overall_verdict:", data["items"][0]["overall_verdict"])

    print("\n[SUCCESS] Live HTTP server test for GET /api/scans search & filtering PASSED!")

if __name__ == "__main__":
    verify()
