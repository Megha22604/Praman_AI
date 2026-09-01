"""
Test Suite for PramanAI Database CRUD Access Layer (Step 3)
Tests create_scan(), create_scan_result(), and get_scan() within an explicit transaction,
verifies data integrity, and performs a complete ROLLBACK without persisting test records.
"""

import sys
from database import get_connection
from crud import create_scan, create_scan_result, get_scan

def run_crud_tests():
    conn = None
    try:
        print("Connecting to database using database.py...")
        conn = get_connection()
        print("[OK] Database connection established.")

        # Phase 6 — Execute Test Operations inside transaction
        print("\nExecuting test_crud workflow...")
        
        # 1. Test create_scan()
        test_product_id = 1
        test_user_id = 1
        test_verdict = "FAIL"
        test_font_height = 2.5
        test_org = "PramanAI CRUD TEST"

        scan_id = create_scan(
            conn,
            product_id=test_product_id,
            user_id=test_user_id,
            image_url=None,
            overall_verdict=test_verdict,
            font_height_detected=test_font_height,
            org=test_org
        )

        if not isinstance(scan_id, (int, float)) or scan_id <= 0:
            raise ValueError(f"Invalid scan_id returned: {scan_id}")
        print(f"  [PASS] create_scan() returned valid numeric scan_id: {scan_id}")

        # 2. Test create_scan_result()
        result_id = create_scan_result(
            conn,
            scan_id=scan_id,
            rule_code="TEST_RULE",
            status="FAIL",
            finding_detail="CRUD layer test"
        )

        if not isinstance(result_id, (int, float)) or result_id <= 0:
            raise ValueError(f"Invalid result_id returned: {result_id}")
        print(f"  [PASS] create_scan_result() returned valid numeric result_id: {result_id}")

        # 3. Test get_scan()
        scan_data = get_scan(conn, scan_id)
        if not scan_data:
            raise ValueError(f"get_scan() returned None for scan_id: {scan_id}")

        print(f"  [PASS] get_scan() returned dictionary record.")

        # Assertions
        assert scan_data["scan_id"] == scan_id, f"Expected scan_id {scan_id}, got {scan_data['scan_id']}"
        assert scan_data["product_id"] == test_product_id, f"Expected product_id {test_product_id}, got {scan_data['product_id']}"
        assert scan_data["user_id"] == test_user_id, f"Expected user_id {test_user_id}, got {scan_data['user_id']}"
        assert scan_data["overall_verdict"] == test_verdict, f"Expected overall_verdict '{test_verdict}', got '{scan_data['overall_verdict']}'"
        assert float(scan_data["font_height_detected"]) == test_font_height, f"Expected font_height_detected {test_font_height}, got {scan_data['font_height_detected']}"
        assert scan_data["org"] == test_org, f"Expected org '{test_org}', got '{scan_data['org']}'"

        print("  [PASS] All field assertions matched expected values!")

        # Phase 5 & 6 — Explicit Transaction Rollback
        print("\nRolling back transaction (no test records will be committed)...")
        conn.rollback()
        print("[OK] Transaction rolled back.")

        # Phase 9 — Verify Rollback Persistence Isolation
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scans WHERE org = %s;", (test_org,))
            scans_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM scan_results WHERE rule_code = %s;", ("TEST_RULE",))
            results_count = cur.fetchone()[0]

        print(f"  Rollback verification: scans count for '{test_org}' = {scans_count}")
        print(f"  Rollback verification: scan_results count for 'TEST_RULE' = {results_count}")

        assert scans_count == 0, f"Expected 0 remaining scans, found {scans_count}"
        assert results_count == 0, f"Expected 0 remaining scan_results, found {results_count}"

        print("  [PASS] Rollback verification succeeded (0 test records remain).")
        print("\n[OK] STEP 3 DATABASE ACCESS LAYER TEST PASSED SUCCESSFULLY!")

    except Exception as e:
        print(f"\n[FAIL] STEP 3 CRUD TEST FAILED: {e}")
        if conn:
            try:
                conn.rollback()
                print("Transaction rolled back due to error.")
            except Exception as rollback_err:
                print(f"Rollback error: {rollback_err}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("Database connection closed cleanly.")

if __name__ == "__main__":
    run_crud_tests()
