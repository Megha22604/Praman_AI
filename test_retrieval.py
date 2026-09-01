"""
Scan Retrieval Integration & Accuracy Test Suite (Step 10 Implementation)
Tests GET /api/scans/{scan_id} endpoint across:
- Test 1: Existing scan retrieval -> HTTP 200, matching metadata, OCR, results, images
- Test 2: Unknown scan retrieval -> HTTP 404 ("Scan not found")
- Test 3: Empty OCR retrieval ([]) -> "ocr": {"raw_lines": []}
- Test 4: OCR with actual data -> matches PostgreSQL ocr_raw_text exactly
- Test 5: Five-image scan retrieval -> 1 scan, 5 image records, 1 set of scan_results
- Test 6: Rule results -> All 8 scan_results returned in result_id ASC order
- Test 7: Cache independence -> Create Scan A, Create Scan B, clear latest_report_cache, GET Scan A -> returns Scan A
- Test 8: Step 8 regression -> 1-5 accepted, 6 rejected, OpenAPI schema intact
"""

import os
import sys
import io
import json
import asyncio
from PIL import Image, ImageDraw
from starlette.datastructures import Headers
from fastapi import UploadFile, HTTPException
from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extras import RealDictCursor

import app
from app import app as fastapi_app, scan_package_image, scan_package_images, get_scan_by_id
from database import get_connection
from storage import supabase

client = TestClient(fastapi_app)

def make_distinct_image_bytes(label: str, bg_color: tuple) -> bytes:
    img = Image.new("RGB", (250, 150), color=bg_color)
    d = ImageDraw.Draw(img)
    d.text((10, 10), f"PramanAI Test Image: {label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def run_step10_test_suite():
    print("================================================================")
    print("  ADITYA BACKEND — STEP 10 SCAN RETRIEVAL TEST SUITE           ")
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
    # TEST 1 — EXISTING SCAN RETRIEVAL
    # ------------------------------------------------------------------
    print("\n--- TEST 1: EXISTING SCAN RETRIEVAL ---")
    f1_single = UploadFile(filename="single.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res1_scan = await scan_package_image(file=f1_single, **kw)
    scan_id_1 = res1_scan["scan_id"]

    res1_get = client.get(f"/api/scans/{scan_id_1}")
    assert res1_get.status_code == 200, f"Expected 200, got {res1_get.status_code}"
    data1 = res1_get.json()

    assert data1["scan_id"] == scan_id_1
    assert data1["overall_verdict"] == res1_scan["compliance_report"]["status"]
    assert float(data1["font_height_detected"]) == 2.5
    assert isinstance(data1["ocr"]["raw_lines"], list)
    assert len(data1["results"]) == len(res1_scan["compliance_report"]["results"])
    assert len(data1["images"]) == 1
    assert data1["images"][0]["image_url"] == f"scan-{scan_id_1}/original.png"
    print(f"[PASS] Existing scan retrieval verified for scan_id = {scan_id_1}.")

    # ------------------------------------------------------------------
    # TEST 2 — UNKNOWN SCAN (HTTP 404)
    # ------------------------------------------------------------------
    print("\n--- TEST 2: UNKNOWN SCAN RETRIEVAL (HTTP 404) ---")
    res2_get = client.get("/api/scans/999999999")
    assert res2_get.status_code == 404
    assert res2_get.json()["detail"] == "Scan not found"
    print("[PASS] Unknown scan 999999999 correctly returned HTTP 404 ('Scan not found').")

    # ------------------------------------------------------------------
    # TEST 3 — EMPTY OCR RETRIEVAL ([])
    # ------------------------------------------------------------------
    print("\n--- TEST 3: EMPTY OCR RETRIEVAL ([]) ---")
    orig_extract = app.extract_text_lines_from_image
    app.extract_text_lines_from_image = lambda b: []

    f_empty = UploadFile(filename="empty.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res3_scan = await scan_package_image(file=f_empty, **kw)
    scan_id_3 = res3_scan["scan_id"]

    app.extract_text_lines_from_image = orig_extract

    res3_get = client.get(f"/api/scans/{scan_id_3}")
    assert res3_get.status_code == 200
    data3 = res3_get.json()
    assert data3["ocr"]["raw_lines"] == []
    print(f"[PASS] Empty OCR retrieval verified for scan_id = {scan_id_3}: 'ocr': {{'raw_lines': []}}.")

    # ------------------------------------------------------------------
    # TEST 4 — OCR WITH ACTUAL PERSISTED DATA
    # ------------------------------------------------------------------
    print("\n--- TEST 4: OCR WITH ACTUAL PERSISTED DATA ---")
    mock_ocr = ["Net Quantity: 750ml", "MRP Rs 299.00", "Manufactured by PramanAI Bottlers Ltd"]
    cur.execute(
        "INSERT INTO scans (overall_verdict, font_height_detected, ocr_raw_text) VALUES (%s, %s, %s) RETURNING scan_id;",
        ("PASS", 3.0, json.dumps(mock_ocr))
    )
    scan_id_4 = cur.fetchone()["scan_id"]
    conn.commit()

    res4_get = client.get(f"/api/scans/{scan_id_4}")
    assert res4_get.status_code == 200
    data4 = res4_get.json()
    assert data4["ocr"]["raw_lines"] == mock_ocr
    print(f"[PASS] OCR actual persisted data retrieval verified for scan_id = {scan_id_4}: {data4['ocr']['raw_lines']}")

    # ------------------------------------------------------------------
    # TEST 5 — FIVE-IMAGE SCAN RETRIEVAL
    # ------------------------------------------------------------------
    print("\n--- TEST 5: FIVE-IMAGE SCAN RETRIEVAL ---")
    f1 = UploadFile(filename="img1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="img2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="img3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    f4 = UploadFile(filename="img4.png", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/png"}))
    f5 = UploadFile(filename="img5.png", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/png"}))

    res5_scan = await scan_package_images(files=[f1, f2, f3, f4, f5], **kw)
    scan_id_5 = res5_scan["scan_id"]

    res5_get = client.get(f"/api/scans/{scan_id_5}")
    assert res5_get.status_code == 200
    data5 = res5_get.json()

    assert data5["scan_id"] == scan_id_5
    assert len(data5["images"]) == 5
    expected_paths = {f"scan-{scan_id_5}/img_{i}.png" for i in range(1, 6)}
    actual_paths = {img["image_url"] for img in data5["images"]}
    assert actual_paths == expected_paths, f"Expected {expected_paths}, got {actual_paths}"
    assert len(data5["results"]) == len(res5_scan["compliance_report"]["results"])
    print(f"[PASS] 5-Image scan retrieval verified for scan_id = {scan_id_5}: 5 images returned cleanly.")

    # ------------------------------------------------------------------
    # TEST 6 — RULE RESULTS RETRIEVAL & ORDERING
    # ------------------------------------------------------------------
    print("\n--- TEST 6: RULE RESULTS RETRIEVAL & ORDERING ---")
    results5 = data5["results"]
    result_ids = [r["result_id"] for r in results5]
    assert result_ids == sorted(result_ids), "Rule results must be ordered by result_id ASC"
    print(f"[PASS] Rule results verified: {len(results5)} items returned in ascending result_id order.")

    # ------------------------------------------------------------------
    # TEST 7 — CACHE INDEPENDENCE
    # ------------------------------------------------------------------
    print("\n--- TEST 7: CACHE INDEPENDENCE ---")
    # Scan A
    f1_a = UploadFile(filename="a.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    resA = await scan_package_image(file=f1_a, **kw)
    scan_id_A = resA["scan_id"]

    # Scan B
    f1_b = UploadFile(filename="b.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    resB = await scan_package_image(file=f1_b, **kw)
    scan_id_B = resB["scan_id"]

    # Wipe latest_report_cache
    app.latest_report_cache = {}

    # Retrieve Scan A from DB
    resA_get = client.get(f"/api/scans/{scan_id_A}")
    assert resA_get.status_code == 200
    dataA = resA_get.json()

    assert dataA["scan_id"] == scan_id_A
    assert dataA["images"][0]["image_url"] == f"scan-{scan_id_A}/original.png"
    print(f"[PASS] Cache independence verified: Scan A ({scan_id_A}) retrieved from PostgreSQL even after cache wipe!")

    # ------------------------------------------------------------------
    # TEST 8 — STEP 8 REGRESSION CHECK
    # ------------------------------------------------------------------
    print("\n--- TEST 8: STEP 8 REGRESSION CHECK ---")
    f1 = UploadFile(filename="1.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    f2 = UploadFile(filename="2.png", file=io.BytesIO(bytes2), headers=Headers({"content-type": "image/png"}))
    f3 = UploadFile(filename="3.png", file=io.BytesIO(bytes3), headers=Headers({"content-type": "image/png"}))
    f4 = UploadFile(filename="4.png", file=io.BytesIO(bytes4), headers=Headers({"content-type": "image/png"}))
    f5 = UploadFile(filename="5.png", file=io.BytesIO(bytes5), headers=Headers({"content-type": "image/png"}))
    f6 = UploadFile(filename="6.png", file=io.BytesIO(bytes6), headers=Headers({"content-type": "image/png"}))

    err_raised = False
    try:
        await scan_package_images(files=[f1, f2, f3, f4, f5, f6], **kw)
    except HTTPException as exc:
        err_raised = True
        assert exc.status_code == 400
        assert "Number of images must be between 1 and 5." in exc.detail
        print(f"[PASS] 6 images HTTP 400 detail: '{exc.detail}'")

    assert err_raised

    openapi_schema = app.app.openapi()
    scan_images_schema = openapi_schema["components"]["schemas"]["Body_scan_package_images_api_scan_images_post"]
    assert "image_types" not in scan_images_schema["properties"]
    assert scan_images_schema["required"] == ["files"]
    print("[PASS] Step 8 invariants preserved: 6 images rejected, OpenAPI schema clean.")

    cur.close()
    conn.close()

    print("\n================================================================")
    print("     ALL STEP 10 SCAN RETRIEVAL TESTS PASSED SUCCESSFULLY!       ")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(run_step10_test_suite())
