import urllib.request
import json
import time

def verify():
    time.sleep(1)

    print("1. Checking Live Port 8000 OpenAPI Schema for Dashboard Stats Route...")
    with urllib.request.urlopen("http://127.0.0.1:8000/openapi.json") as resp:
        schema = json.loads(resp.read().decode())
        paths = list(schema.get("paths", {}).keys())
        print("   Routes found in OpenAPI schema:")
        for p in paths:
            print("    ", p)

    assert "/api/stats" in paths
    print("\n   [PASS] Route GET /api/stats registered in Swagger/OpenAPI!")

    print("\n2. Testing Live HTTP GET /api/stats...")
    url = "http://127.0.0.1:8000/api/stats"
    with urllib.request.urlopen(url) as resp:
        print("   Status:", resp.status)
        data = json.loads(resp.read().decode())
        print("   total_scans:", data["total_scans"])
        print("   pass_count:", data["pass_count"])
        print("   fail_count:", data["fail_count"])
        print("   needs_review_count:", data["needs_review_count"])
        print("   compliance_percentage:", data["compliance_percentage"])
        print("   failed_rule_counts keys:", list(data["failed_rule_counts"].keys()))

    print("\n[SUCCESS] Live HTTP server test for GET /api/stats PASSED!")

if __name__ == "__main__":
    verify()
