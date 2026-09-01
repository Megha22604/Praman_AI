"""
Test Suite for create_image() in crud.py (Step 6)
Tests image record insertion against existing scans table (scan_id = 6),
verifies foreign key constraints and field attributes, and performs transaction rollback.
"""

import sys
from database import get_connection
from crud import create_image

def test_image_crud_func():
    conn = None
    try:
        conn = get_connection()
        print("Database connection: PASS")

        # Target existing scan_id = 6
        target_scan_id = 6
        test_image_url = "TEST_CRUD_IMAGE_REFERENCE"
        test_image_type = "front"

        # 1. Execute create_image within transaction
        image_id = create_image(
            conn,
            scan_id=target_scan_id,
            image_url=test_image_url,
            image_type=test_image_type
        )

        if not isinstance(image_id, (int, float)) or image_id <= 0:
            print(f"create_image(): FAIL (Invalid image_id: {image_id})")
            sys.exit(1)

        print("create_image(): PASS")
        print(f"Generated image_id: {image_id}")

        # 2. Query within transaction to verify fields and foreign key reference
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scan_id, image_url, image_type FROM images WHERE image_id = %s;",
                (image_id,)
            )
            row = cur.fetchone()

        if not row:
            print("Field verification: FAIL (Row not found inside transaction)")
            sys.exit(1)

        fetched_scan_id, fetched_url, fetched_type = row

        if fetched_scan_id == target_scan_id and fetched_url == test_image_url and fetched_type == test_image_type:
            print("Field verification: PASS")
            print("Foreign key: PASS")
        else:
            print(f"Field verification: FAIL (Mismatched values: {row})")
            sys.exit(1)

        # 3. Perform Rollback
        conn.rollback()
        print("Rollback: PASS")

        # 4. Verify Rollback Persistence Isolation
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM images WHERE image_url = %s;",
                (test_image_url,)
            )
            remaining_count = cur.fetchone()[0]

        print(f"Remaining test rows: {remaining_count}")
        if remaining_count == 0:
            print("\n[OK] STEP 6 CREATE_IMAGE TEST PASSED SUCCESSFULLY!")
        else:
            print(f"[FAIL] Unexpected remaining rows count: {remaining_count}")
            sys.exit(1)

    except Exception as e:
        print(f"[FAIL] STEP 6 TEST ERROR: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_image_crud_func()
