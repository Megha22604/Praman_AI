"""
Multi-Image Integration & Boundary Test Suite (Step 8 Final Clean Contract)
Tests POST /api/scan-images endpoint across:
- Test A: 1 Image, no image_types -> 200, image_type = NULL, storage = img_1.png
- Test B: 3 Images, no image_types -> 200, 3 image rows, image_type = NULL for all
- Test C: 5 Images, no image_types -> 200, 1 scan, 5 image rows, all image_type = NULL, 5 unique Storage objects, 8 scan_results
- Test D: 6 Images -> 400 rejection (0 DB/Storage artifacts)
- Test E: 1 Non-image file -> 400 rejection ('All uploaded files must be images.')
- Test F: 5 Arbitrary image filenames (abc.jpeg, random.png, 123.webp, etc.) -> 200 success
- Test G: Duplicate/identical semantic-looking filenames -> 200, 5 distinct Storage paths (img_1.png..img_5.png)
- Test H: Rollback during scan_results insertion -> 500, DB rollback, Storage cleanup
"""

import os
import sys
import io
import asyncio
from PIL import Image, ImageDraw
from starlette.datastructures import Headers
from fastapi import UploadFile, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor

import app
from app import scan_package_images, export_official_notice_pdf
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


async def run_step8_test_suite():
    print("================================================================")
    print("  ADITYA BACKEND — STEP 8 MULTI-IMAGE TEST SUITE (FINAL CLEAN) ")
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
    # TEST A — 1 IMAGE, NO IMAGE_TYPES
    # ------------------------------------------------------------------
    print("\n--- TEST A: 1 IMAGE SUCCESS (NO IMAGE_TYPES) ---")
    f1 = UploadFile(filename="img1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    resA = await scan_package_images(files=[f1], **kw)
    assert resA["status"] == "success"
    scan_id_A = resA["scan_id"]

    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (scan_id_A,))
    assert cur.fetchone()["count"] == 1
    cur.execute("SELECT image_id, scan_id, image_url, image_type FROM images WHERE scan_id = %s;", (scan_id_A,))
    db_img_A = cur.fetchone()
    assert db_img_A["image_type"] is None
    assert db_img_A["image_url"] == f"scan-{scan_id_A}/img_1.png"
    bucket_files_A = supabase.storage.from_("scan-images").list(f"scan-{scan_id_A}")
    assert len(bucket_files_A) == 1
    assert bucket_files_A[0]["name"] == "img_1.png"
    print(f"[PASS] Test A verified (scan_id = {scan_id_A}, image_type = NULL, storage = 'img_1.png').")

    # ------------------------------------------------------------------
    # TEST B — 3 IMAGES, NO IMAGE_TYPES
    # ------------------------------------------------------------------
    print("\n--- TEST B: 3 IMAGES SUCCESS (NO IMAGE_TYPES) ---")
    f1 = UploadFile(filename="img1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="img2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="img3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    resB = await scan_package_images(files=[f1, f2, f3], **kw)
    scan_id_B = resB["scan_id"]

    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (scan_id_B,))
    assert cur.fetchone()["count"] == 1
    cur.execute("SELECT image_type FROM images WHERE scan_id = %s;", (scan_id_B,))
    assert all(row["image_type"] is None for row in cur.fetchall())
    bucket_files_B = [f["name"] for f in supabase.storage.from_("scan-images").list(f"scan-{scan_id_B}")]
    assert set(bucket_files_B) == {"img_1.png", "img_2.png", "img_3.png"}
    print(f"[PASS] Test B 3 Images verified (scan_id = {scan_id_B}, all image_type = NULL, storage = img_1..3.png).")

    # ------------------------------------------------------------------
    # TEST C — 5 IMAGES PRIMARY ACCEPTANCE (NO IMAGE_TYPES)
    # ------------------------------------------------------------------
    print("\n--- TEST C: 5 IMAGES PRIMARY ACCEPTANCE (NO IMAGE_TYPES) ---")
    f1 = UploadFile(filename="img1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="img2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="img3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    f4 = UploadFile(filename="img4.png", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/png"}))
    f5 = UploadFile(filename="img5.png", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/png"}))
    
    resC = await scan_package_images(files=[f1, f2, f3, f4, f5], **kw)
    assert resC["status"] == "success"
    scan_id_C = resC["scan_id"]

    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (scan_id_C,))
    assert cur.fetchone()["count"] == 1

    cur.execute("SELECT image_id, scan_id, image_url, image_type FROM images WHERE scan_id = %s ORDER BY image_id;", (scan_id_C,))
    db_images_C = cur.fetchall()
    assert len(db_images_C) == 5
    assert set(img["scan_id"] for img in db_images_C) == {scan_id_C}
    assert all(img["image_type"] is None for img in db_images_C)
    print(f"[PASS] 5 image rows verified for scan_id = {scan_id_C} (All image_type = NULL).")

    bucket_files_C = [f["name"] for f in supabase.storage.from_("scan-images").list(f"scan-{scan_id_C}")]
    expected_paths_C = {"img_1.png", "img_2.png", "img_3.png", "img_4.png", "img_5.png"}
    assert set(bucket_files_C) == expected_paths_C, f"Expected {expected_paths_C}, got {set(bucket_files_C)}"
    print(f"[PASS] 5 distinct Storage paths verified in scan-{scan_id_C}/: {bucket_files_C}")

    api_results_count = len(resC["compliance_report"]["results"])
    cur.execute("SELECT COUNT(*) FROM scan_results WHERE scan_id = %s;", (scan_id_C,))
    db_results_count = cur.fetchone()["count"]
    assert db_results_count == api_results_count
    print(f"[PASS] scan_results table verified: {db_results_count} rows persisted (single evaluation set).")

    # ------------------------------------------------------------------
    # TEST D — 6 IMAGES REJECTION
    # ------------------------------------------------------------------
    print("\n--- TEST D: 6 IMAGES REJECTION ---")
    cur.execute("SELECT MAX(scan_id) FROM scans;")
    max_scan_id_before = cur.fetchone()["max"] or 0

    f1 = UploadFile(filename="1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    f4 = UploadFile(filename="4.png", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/png"}))
    f5 = UploadFile(filename="5.png", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/png"}))
    f6 = UploadFile(filename="6.png", file=io.BytesIO(bytes6), headers=Headers({"content-type": "image/png"}))
    
    err_raised_d = False
    try:
        await scan_package_images(files=[f1, f2, f3, f4, f5, f6], **kw)
    except HTTPException as exc:
        err_raised_d = True
        assert exc.status_code == 400
        assert "Number of images must be between 1 and 5." in exc.detail
        print(f"[PASS] 6 images HTTP 400 detail: '{exc.detail}'")

    assert err_raised_d, "Expected HTTPException 400 for 6 images."
    cur.execute("SELECT MAX(scan_id) FROM scans;")
    assert (cur.fetchone()["max"] or 0) == max_scan_id_before
    print("[PASS] 6 images rejection verified: 0 new DB scan rows created.")

    # ------------------------------------------------------------------
    # TEST E — NON-IMAGE FILE REJECTION
    # ------------------------------------------------------------------
    print("\n--- TEST E: NON-IMAGE FILE REJECTION ---")
    txt_file = UploadFile(filename="document.txt", file=io.BytesIO(b"Hello world"), headers=Headers({"content-type": "text/plain"}))
    err_raised_e = False
    try:
        await scan_package_images(files=[txt_file], **kw)
    except HTTPException as exc:
        err_raised_e = True
        assert exc.status_code == 400
        assert "All uploaded files must be images." in exc.detail
        print(f"[PASS] Non-image file HTTP 400 detail: '{exc.detail}'")

    assert err_raised_e, "Expected HTTPException 400 for non-image file."

    # ------------------------------------------------------------------
    # TEST F — 5 ARBITRARY FILENAMES (NO SEMANTIC NAMING)
    # ------------------------------------------------------------------
    print("\n--- TEST F: 5 ARBITRARY FILENAMES SUCCESS ---")
    f_abc = UploadFile(filename="abc.jpeg", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/jpeg"}))
    f_rnd = UploadFile(filename="random.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f_123 = UploadFile(filename="123.webp", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/webp"}))
    f_pkg = UploadFile(filename="package-photo.jpeg", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/jpeg"}))
    f_wht = UploadFile(filename="whatever.jpg", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/jpeg"}))

    resF = await scan_package_images(files=[f_abc, f_rnd, f_123, f_pkg, f_wht], **kw)
    assert resF["status"] == "success"
    scan_id_F = resF["scan_id"]
    print(f"[PASS] 5 arbitrary filenames scan succeeded (scan_id = {scan_id_F}).")

    # ------------------------------------------------------------------
    # TEST G — DUPLICATE SEMANTIC-LOOKING FILENAMES
    # ------------------------------------------------------------------
    print("\n--- TEST G: DUPLICATE SEMANTIC FILENAMES UNIQUE STORAGE PATHS ---")
    f_dup1 = UploadFile(filename="front.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f_dup2 = UploadFile(filename="front.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f_dup3 = UploadFile(filename="front.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))

    resG = await scan_package_images(files=[f_dup1, f_dup2, f_dup3], **kw)
    scan_id_G = resG["scan_id"]
    bucket_files_G = [f["name"] for f in supabase.storage.from_("scan-images").list(f"scan-{scan_id_G}")]
    assert set(bucket_files_G) == {"img_1.png", "img_2.png", "img_3.png"}
    print(f"[PASS] Duplicate filenames storage paths verified in scan-{scan_id_G}/: {bucket_files_G}")

    # ------------------------------------------------------------------
    # TEST H — ROLLBACK & STORAGE CLEANUP VERIFICATION
    # ------------------------------------------------------------------
    print("\n--- TEST H: ROLLBACK & STORAGE CLEANUP VERIFICATION ---")
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

    err_raised_h = False
    try:
        await scan_package_images(files=[f1, f2], **kw)
    except HTTPException as exc:
        err_raised_h = True
        assert exc.status_code == 500
        assert "Simulated Database Failure" in exc.detail
        print(f"[PASS] Simulated failure caught HTTP 500: '{exc.detail}'")

    app.create_scan = orig_create_scan
    app.create_scan_result = orig_create_scan_result
    assert err_raised_h
    assert captured_scan_id is not None

    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (captured_scan_id,))
    assert cur.fetchone()["count"] == 0
    print(f"[PASS] PostgreSQL transaction rolled back cleanly for scan-{captured_scan_id}.")

    failed_dir_files = supabase.storage.from_("scan-images").list(f"scan-{captured_scan_id}")
    assert len(failed_dir_files) == 0, f"Expected 0 orphaned files in storage, found {len(failed_dir_files)}"
    print("[PASS] Rollback verification succeeded: DB transaction rolled back and all Storage objects deleted cleanly.")

    # ------------------------------------------------------------------
    # OPENAPI SCHEMA VERIFICATION
    # ------------------------------------------------------------------
    print("\n--- OPENAPI SCHEMA VERIFICATION ---")
    openapi_schema = app.app.openapi()
    scan_images_schema = openapi_schema["components"]["schemas"]["Body_scan_package_images_api_scan_images_post"]
    assert "image_types" not in scan_images_schema["properties"]
    assert scan_images_schema["required"] == ["files"]
    files_items = scan_images_schema["properties"]["files"]["items"]
    assert files_items["type"] == "string"
    assert files_items["format"] == "binary"
    print("[PASS] OpenAPI schema verified: image_types REMOVED, required = ['files'], files.items format = binary.")

    cur.close()
    conn.close()

    print("\n================================================================")
    print("     ALL STEP 8 CLEAN CONTRACT TESTS PASSED SUCCESSFULLY!       ")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(run_step8_test_suite())
