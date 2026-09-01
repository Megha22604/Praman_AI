"""
Multi-Image Integration Test Suite (Step 8)
Tests POST /api/scan-images endpoint with 3 image uploads (front, back, close-up).
Verifies single scan creation, Supabase Storage uploads, images table records, and scan_results.
"""

import os
import sys
import io
import asyncio

# Ensure project root is in python path
sys.path.insert(0, os.getcwd())

from starlette.datastructures import Headers
from fastapi import UploadFile
import psycopg2
from psycopg2.extras import RealDictCursor

from app import scan_package_images, export_official_notice_pdf
from database import get_connection
from storage import supabase

async def run_multi_image_test():
    test_image_path = os.path.join(os.getcwd(), "test_label_food.png")
    if not os.path.exists(test_image_path):
        print(f"Error: test_image_path {test_image_path} does not exist.")
        sys.exit(1)

    print("=== TESTING POST /api/scan-images WITH 3 IMAGES (FRONT, BACK, CLOSE-UP) ===")
    with open(test_image_path, "rb") as f:
        file_bytes = f.read()

    # Create 3 UploadFile instances representing front, back, and close-up images
    file1 = UploadFile(filename="front_label.png", file=io.BytesIO(file_bytes), headers=Headers({"content-type": "image/png"}))
    file2 = UploadFile(filename="back_label.png", file=io.BytesIO(file_bytes), headers=Headers({"content-type": "image/png"}))
    file3 = UploadFile(filename="closeup_label.png", file=io.BytesIO(file_bytes), headers=Headers({"content-type": "image/png"}))

    files_list = [file1, file2, file3]
    image_types_list = ["front", "back", "close-up"]

    res_json = await scan_package_images(
        files=files_list,
        image_types=image_types_list,
        package_height_cm=15.0,
        package_width_cm=10.0,
        detected_font_height_mm=2.5
    )

    print("[PASS] scan_package_images() execution completed.")
    print(f"  Response status: {res_json.get('status')}")
    print(f"  Returned scan_id: {res_json.get('scan_id')}")

    scan_id = res_json.get("scan_id")
    if not isinstance(scan_id, int):
        print(f"FAIL: scan_id is not integer: {type(scan_id)}")
        sys.exit(1)

    # Response schema assertions
    assert res_json.get("status") == "success"
    assert "detected_raw_lines" in res_json
    assert "compliance_report" in res_json
    assert "images" in res_json and len(res_json["images"]) == 3
    print("[PASS] Multi-image response schema verified (status, scan_id, detected_raw_lines, compliance_report, images[3]).")

    comp_report = res_json["compliance_report"]
    api_results_count = len(comp_report.get("results", []))

    print("\n=== DATABASE VERIFICATION (POSTGRESQL) ===")
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Verify scans count = 1
    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (scan_id,))
    scans_count = cur.fetchone()["count"]
    assert scans_count == 1, f"Expected exactly 1 scan row, found {scans_count}"
    print(f"[PASS] Single scan record created for multi-image submission (scan_id = {scan_id}).")

    # 2. Verify images count = 3 with correct image_types and same scan_id
    cur.execute("SELECT image_id, scan_id, image_url, image_type FROM images WHERE scan_id = %s ORDER BY image_id;", (scan_id,))
    db_images = cur.fetchall()
    assert len(db_images) == 3, f"Expected 3 images rows, found {len(db_images)}"

    db_types = [img["image_type"] for img in db_images]
    db_scan_ids = set(img["scan_id"] for img in db_images)

    assert db_scan_ids == {scan_id}, f"All images must share scan_id {scan_id}, found {db_scan_ids}"
    assert db_types == ["front", "back", "close-up"], f"Expected types ['front', 'back', 'close-up'], got {db_types}"
    print("[PASS] images table verified: 3 rows created with identical scan_id and types ('front', 'back', 'close-up').")

    # 3. Verify scan_results count equals 1 set of rule results (not 3x)
    cur.execute("SELECT COUNT(*) FROM scan_results WHERE scan_id = %s;", (scan_id,))
    db_results_count = cur.fetchone()["count"]
    assert db_results_count == api_results_count, f"scan_results count mismatch: DB {db_results_count} vs API {api_results_count}"
    print(f"[PASS] scan_results table verified: {db_results_count} rule results persisted (single evaluation set).")

    print("\n=== SUPABASE STORAGE VERIFICATION ===")
    bucket_files = supabase.storage.from_("scan-images").list(f"scan-{scan_id}")
    file_names = [f["name"] for f in bucket_files]
    print(f"  Files found in Supabase Storage scan-{scan_id}/: {file_names}")

    expected_files = {"front.png", "back.png", "close-up.png"}
    assert set(file_names) == expected_files, f"Expected storage files {expected_files}, got {set(file_names)}"
    print("[PASS] Supabase Storage verified: scan-{scan_id}/ contains front.png, back.png, and close-up.png.")

    print("\n=== PDF EXPORT VERIFICATION ===")
    pdf_response = export_official_notice_pdf()
    assert pdf_response.media_type == "application/pdf"
    print("[PASS] /api/export-pdf endpoint verified using latest_report_cache.")

    cur.close()
    conn.close()

    print(f"\nMulti-Image Scan ID: {scan_id}")
    print("ALL STEP 8 MULTI-IMAGE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_multi_image_test())
