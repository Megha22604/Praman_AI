"""
Multi-Image Integration & Persistence Test Suite (Step 9 OCR Persistence Completed)
Tests scan endpoints across:
- Test 1: Single-image OCR persistence -> 200, scans.ocr_raw_text stored as JSON array
- Test 2: Multi-image 5-image OCR persistence -> 200, 1 scan row, scans.ocr_raw_text populated, 5 image rows, 8 scan_results
- Test 3: Empty OCR persistence -> 200, scans.ocr_raw_text stored as []
- Test 4: Rollback -> 500, DB transaction rolled back, Storage objects cleaned up
- Test 5: Rejection & OpenAPI schema preservation
"""

import os
import sys
import io
import json
import asyncio
from PIL import Image, ImageDraw
from starlette.datastructures import Headers
from fastapi import UploadFile, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor

import app
from app import scan_package_image, scan_package_images, export_official_notice_pdf
from database import get_connection
from storage import supabase


def make_distinct_image_bytes(label: str, bg_color: tuple, format: str = "PNG") -> bytes:
    """Generates a genuinely distinct image payload."""
    img = Image.new("RGB", (250, 150), color=bg_color)
    d = ImageDraw.Draw(img)
    d.text((10, 10), f"PramanAI Test Image: {label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


async def run_step9_test_suite():
    print("================================================================")
    print("  ADITYA BACKEND — STEP 9 OCR PERSISTENCE TEST SUITE            ")
    print("================================================================")

    bytes1 = make_distinct_image_bytes("1_Red", (200, 40, 40))
    bytes2 = make_distinct_image_bytes("2_Green", (40, 160, 40))
    bytes3 = make_distinct_image_bytes("3_Blue", (40, 40, 200))
    bytes4 = make_distinct_image_bytes("4_Yellow", (200, 200, 40))
    bytes5 = make_distinct_image_bytes("5_Purple", (160, 40, 160))
    bytes6 = make_distinct_image_bytes("6_Cyan", (40, 200, 200))

    kw = {"package_height_cm": 15.0, "package_width_cm": 10.0, "detected_font_height_mm": 2.5}

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # TEST 1 — SINGLE-IMAGE OCR PERSISTENCE
    # ------------------------------------------------------------------
    print("\n--- TEST 1: SINGLE-IMAGE OCR PERSISTENCE ---")
    f1_single = UploadFile(filename="single.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res1 = await scan_package_image(file=f1_single, **kw)
    assert res1["status"] == "success"
    scan_id_1 = res1["scan_id"]

    cur.execute("SELECT scan_id, overall_verdict, ocr_raw_text FROM scans WHERE scan_id = %s;", (scan_id_1,))
    db_scan_1 = cur.fetchone()
    assert db_scan_1 is not None
    assert db_scan_1["ocr_raw_text"] is not None
    assert isinstance(db_scan_1["ocr_raw_text"], list)
    assert db_scan_1["ocr_raw_text"] == res1["detected_raw_lines"]
    print(f"[PASS] Single-image OCR persistence verified for scan_id = {scan_id_1}: ocr_raw_text = {db_scan_1['ocr_raw_text']}")

    # ------------------------------------------------------------------
    # TEST 2 — MULTI-IMAGE 5-IMAGE OCR PERSISTENCE
    # ------------------------------------------------------------------
    print("\n--- TEST 2: MULTI-IMAGE 5-IMAGE OCR PERSISTENCE ---")
    f1 = UploadFile(filename="img1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="img2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="img3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    f4 = UploadFile(filename="img4.png", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/png"}))
    f5 = UploadFile(filename="img5.png", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/png"}))

    res2 = await scan_package_images(files=[f1, f2, f3, f4, f5], **kw)
    assert res2["status"] == "success"
    scan_id_2 = res2["scan_id"]

    cur.execute("SELECT scan_id, overall_verdict, ocr_raw_text FROM scans WHERE scan_id = %s;", (scan_id_2,))
    db_scan_2 = cur.fetchone()
    assert db_scan_2 is not None
    assert db_scan_2["ocr_raw_text"] is not None
    assert isinstance(db_scan_2["ocr_raw_text"], list)
    assert db_scan_2["ocr_raw_text"] == res2["detected_raw_lines"]
    print(f"[PASS] 5-Image OCR persistence verified for scan_id = {scan_id_2}: ocr_raw_text = {db_scan_2['ocr_raw_text']}")

    cur.execute("SELECT image_id, scan_id, image_url, image_type FROM images WHERE scan_id = %s ORDER BY image_id;", (scan_id_2,))
    db_images_2 = cur.fetchall()
    assert len(db_images_2) == 5
    assert all(img["scan_id"] == scan_id_2 for img in db_images_2)
    assert all(img["image_type"] is None for img in db_images_2)

    bucket_files_2 = [f["name"] for f in supabase.storage.from_("scan-images").list(f"scan-{scan_id_2}")]
    assert set(bucket_files_2) == {"img_1.png", "img_2.png", "img_3.png", "img_4.png", "img_5.png"}

    cur.execute("SELECT COUNT(*) FROM scan_results WHERE scan_id = %s;", (scan_id_2,))
    assert cur.fetchone()["count"] == len(res2["compliance_report"]["results"])
    print("[PASS] 5 Image rows, 5 Storage objects, and 1 set of scan_results verified.")

    # ------------------------------------------------------------------
    # TEST 3 — EMPTY OCR PERSISTENCE ([])
    # ------------------------------------------------------------------
    print("\n--- TEST 3: EMPTY OCR PERSISTENCE ([]) ---")
    orig_extract = app.extract_text_lines_from_image
    app.extract_text_lines_from_image = lambda b: []

    f_empty = UploadFile(filename="empty.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res3 = await scan_package_image(file=f_empty, **kw)
    scan_id_3 = res3["scan_id"]

    app.extract_text_lines_from_image = orig_extract

    cur.execute("SELECT scan_id, ocr_raw_text FROM scans WHERE scan_id = %s;", (scan_id_3,))
    db_scan_3 = cur.fetchone()
    assert db_scan_3["ocr_raw_text"] == []
    print(f"[PASS] Empty OCR persistence verified: ocr_raw_text stored explicitly as [] (not NULL).")

    # ------------------------------------------------------------------
    # TEST 4 — ROLLBACK & STORAGE CLEANUP VERIFICATION
    # ------------------------------------------------------------------
    print("\n--- TEST 4: ROLLBACK & STORAGE CLEANUP VERIFICATION ---")
    captured_scan_id = None
    orig_create_scan = app.create_scan
    def tracking_create_scan(*args, **kwargs):
        nonlocal captured_scan_id
        captured_scan_id = orig_create_scan(*args, **kwargs)
        return captured_scan_id

    orig_create_scan_result = app.create_scan_result
    def failing_create_scan_result(*args, **kwargs):
        raise RuntimeError("Simulated Database Failure during scan_results insertion")

    app.create_scan = tracking_create_scan
    app.create_scan_result = failing_create_scan_result

    f1 = UploadFile(filename="img1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="img2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))

    err_raised_4 = False
    try:
        await scan_package_images(files=[f1, f2], **kw)
    except HTTPException as exc:
        err_raised_4 = True
        assert exc.status_code == 500
        assert "Simulated Database Failure" in exc.detail
        print(f"[PASS] Simulated failure caught HTTP 500: '{exc.detail}'")

    app.create_scan = orig_create_scan
    app.create_scan_result = orig_create_scan_result
    assert err_raised_4
    assert captured_scan_id is not None

    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (captured_scan_id,))
    assert cur.fetchone()["count"] == 0
    print(f"[PASS] PostgreSQL transaction rolled back cleanly for scan-{captured_scan_id}.")

    failed_dir_files = supabase.storage.from_("scan-images").list(f"scan-{captured_scan_id}")
    assert len(failed_dir_files) == 0
    print("[PASS] Rollback verification succeeded: 0 orphaned storage objects remain.")

    # ------------------------------------------------------------------
    # TEST 5 — REJECTION & OPENAPI PRESERVATION
    # ------------------------------------------------------------------
    print("\n--- TEST 5: REJECTION & OPENAPI PRESERVATION ---")
    f1 = UploadFile(filename="1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    f4 = UploadFile(filename="4.png", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/png"}))
    f5 = UploadFile(filename="5.png", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/png"}))
    f6 = UploadFile(filename="6.png", file=io.BytesIO(bytes6), headers=Headers({"content-type": "image/png"}))

    err_raised_5 = False
    try:
        await scan_package_images(files=[f1, f2, f3, f4, f5, f6], **kw)
    except HTTPException as exc:
        err_raised_5 = True
        assert exc.status_code == 400
        assert "Number of images must be between 1 and 5." in exc.detail
        print(f"[PASS] 6 images HTTP 400 detail: '{exc.detail}'")

    assert err_raised_5

    openapi_schema = app.app.openapi()
    scan_images_schema = openapi_schema["components"]["schemas"]["Body_scan_package_images_api_scan_images_post"]
    assert "image_types" not in scan_images_schema["properties"]
    assert scan_images_schema["required"] == ["files"]
    print("[PASS] OpenAPI schema verified: image_types REMOVED, required = ['files'].")

    cur.close()
    conn.close()

    print("\n================================================================")
    print("     ALL STEP 9 OCR PERSISTENCE TESTS PASSED SUCCESSFULLY!      ")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(run_step9_test_suite())
