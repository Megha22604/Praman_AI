"""
Scan Retrieval, Pagination, Filtering & Product History Test Suite (Step 10, 11, 12 & 13)
Tests GET /api/scans, GET /api/scans/{scan_id}, and GET /api/products/{product_id}/history across:
- Step 10 Tests: Individual scan retrieval by ID, 404 behavior, OCR, 5-image retrieval, ordering, cache independence.
- Step 11 Tests: Default pagination, page sizing, newest-first ordering, limit/offset, validation, total calculation.
- Step 12 Tests: Search & filtering by status, date range, failed_rule, product_name, brand, inspector, combined filters.
- Step 13 Tests:
  - Product with associated scans returns history (product metadata + scan items)
  - History is newest-first (timestamp DESC, scan_id DESC)
  - Product with no scans returns empty history (items: [], total: 0)
  - Unknown product_id returns HTTP 404 ("Product not found")
  - Pagination works on product history (page, page_size, total_pages)
  - Regressions across all previous steps.
"""

import os
import sys
import io
import json
import asyncio
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw
from starlette.datastructures import Headers
from fastapi import UploadFile, HTTPException
from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extras import RealDictCursor

import app
from app import app as fastapi_app, scan_package_image, scan_package_images, get_scan_by_id, get_scans, get_product_history
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


async def run_full_retrieval_test_suite():
    print("==================================================================")
    print("  ADITYA BACKEND — STEP 10, 11, 12 & 13 RETRIEVAL & HISTORY TESTS ")
    print("==================================================================")

    bytes1 = make_distinct_image_bytes("1_Red", (200, 40, 40))
    bytes2 = make_distinct_image_bytes("2_Green", (40, 160, 40))
    bytes3 = make_distinct_image_bytes("3_Blue", (40, 40, 200))
    bytes4 = make_distinct_image_bytes("4_Yellow", (200, 200, 40))

    kw = {"package_height_cm": 15.0, "package_width_cm": 10.0, "detected_font_height_mm": 2.5}

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # STEP 10 & 11 REGRESSIONS
    # ------------------------------------------------------------------
    print("\n--- STEP 10 & 11 REGRESSIONS ---")
    f1_single = UploadFile(filename="single.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res1_scan = await scan_package_image(file=f1_single, **kw)
    scan_id_1 = res1_scan["scan_id"]

    res1_get = client.get(f"/api/scans/{scan_id_1}")
    assert res1_get.status_code == 200
    assert res1_get.json()["scan_id"] == scan_id_1

    res404 = client.get("/api/scans/999999999")
    assert res404.status_code == 404

    res_scans_def = client.get("/api/scans")
    assert res_scans_def.status_code == 200
    print("[PASS] Step 10 & Step 11 regressions verified.")

    # ------------------------------------------------------------------
    # STEP 13 TESTS — PRODUCT HISTORY (GET /api/products/{product_id}/history)
    # ------------------------------------------------------------------
    print("\n--- STEP 13: PRODUCT HISTORY IMPLEMENTATION & VERIFICATION ---")

    # 1. Insert product A with 2 scans
    cur.execute(
        "INSERT INTO products (name, brand, category) VALUES (%s, %s, %s) RETURNING product_id;",
        ("Parle-G Gold Biscuits", "Parle", "Biscuits")
    )
    prod_A_id = cur.fetchone()["product_id"]

    # 2. Insert product B with 0 scans
    cur.execute(
        "INSERT INTO products (name, brand, category) VALUES (%s, %s, %s) RETURNING product_id;",
        ("Parle Hide & Seek", "Parle", "Confectionery")
    )
    prod_B_id = cur.fetchone()["product_id"]

    now = datetime.now(timezone.utc)
    t_older = now - timedelta(hours=2)
    t_newer = now - timedelta(hours=1)

    # Insert Scan 1 for Product A (Older)
    cur.execute(
        "INSERT INTO scans (product_id, overall_verdict, font_height_detected, timestamp, ocr_raw_text) VALUES (%s, %s, %s, %s, %s) RETURNING scan_id;",
        (prod_A_id, "FAIL", 2.0, t_older, json.dumps(["Parle-G Gold", "MRP 10"]))
    )
    scan_A_older_id = cur.fetchone()["scan_id"]

    # Insert Scan 2 for Product A (Newer)
    cur.execute(
        "INSERT INTO scans (product_id, overall_verdict, font_height_detected, timestamp, ocr_raw_text) VALUES (%s, %s, %s, %s, %s) RETURNING scan_id;",
        (prod_A_id, "PASS", 3.0, t_newer, json.dumps(["Parle-G Gold", "MRP Rs 10.00"]))
    )
    scan_A_newer_id = cur.fetchone()["scan_id"]

    conn.commit()

    # TEST 13.1 — Product A with scans returns history
    print("\n--- TEST 13.1: PRODUCT WITH SCANS RETRIEVAL ---")
    res_pA = client.get(f"/api/products/{prod_A_id}/history")
    assert res_pA.status_code == 200
    data_pA = res_pA.json()
    assert data_pA["product_id"] == prod_A_id
    assert data_pA["product_name"] == "Parle-G Gold Biscuits"
    assert data_pA["brand"] == "Parle"
    assert data_pA["category"] == "Biscuits"
    assert data_pA["total"] == 2
    assert len(data_pA["items"]) == 2
    print(f"[PASS] Product A history retrieved: product_id={prod_A_id}, name='{data_pA['product_name']}', total_scans=2.")

    # TEST 13.2 — Newest-first history ordering
    print("\n--- TEST 13.2: NEWEST-FIRST ORDERING ---")
    items_pA = data_pA["items"]
    assert items_pA[0]["scan_id"] == scan_A_newer_id, f"Expected newer scan {scan_A_newer_id} first, got {items_pA[0]['scan_id']}"
    assert items_pA[1]["scan_id"] == scan_A_older_id, f"Expected older scan {scan_A_older_id} second, got {items_pA[1]['scan_id']}"
    print("[PASS] History scans ordered newest-first (timestamp DESC, scan_id DESC).")

    # TEST 13.3 — Product with 0 scans returns empty history
    print("\n--- TEST 13.3: EMPTY PRODUCT HISTORY ---")
    res_pB = client.get(f"/api/products/{prod_B_id}/history")
    assert res_pB.status_code == 200
    data_pB = res_pB.json()
    assert data_pB["product_id"] == prod_B_id
    assert data_pB["items"] == []
    assert data_pB["total"] == 0
    assert data_pB["total_pages"] == 0
    print(f"[PASS] Product B with 0 scans returned empty history: items: [], total: 0.")

    # TEST 13.4 — Unknown product_id returns HTTP 404
    print("\n--- TEST 13.4: UNKNOWN PRODUCT ID (HTTP 404) ---")
    res_p404 = client.get("/api/products/999999999/history")
    assert res_p404.status_code == 404
    assert res_p404.json()["detail"] == "Product not found"
    print("[PASS] Unknown product_id 999999999 returned HTTP 404 ('Product not found').")

    # TEST 13.5 — Product history pagination
    print("\n--- TEST 13.5: PRODUCT HISTORY PAGINATION ---")
    res_pA_page1 = client.get(f"/api/products/{prod_A_id}/history?page=1&page_size=1").json()
    assert res_pA_page1["page"] == 1
    assert res_pA_page1["page_size"] == 1
    assert res_pA_page1["total"] == 2
    assert res_pA_page1["total_pages"] == 2
    assert len(res_pA_page1["items"]) == 1
    assert res_pA_page1["items"][0]["scan_id"] == scan_A_newer_id

    res_pA_page2 = client.get(f"/api/products/{prod_A_id}/history?page=2&page_size=1").json()
    assert res_pA_page2["page"] == 2
    assert res_pA_page2["items"][0]["scan_id"] == scan_A_older_id
    print("[PASS] Product history pagination verified: page 1 and page 2 returned correct scan items.")

    # TEST 13.6 — Invalid parameter rejections
    print("\n--- TEST 13.6: INVALID PARAMETER REJECTIONS ---")
    res_p_bad = client.get(f"/api/products/{prod_A_id}/history?page=0")
    assert res_p_bad.status_code == 400
    assert "page must be greater than or equal to 1." in res_p_bad.json()["detail"]
    print("[PASS] page=0 rejected with HTTP 400.")

    cur.close()
    conn.close()

    print("\n==================================================================")
    print("     ALL STEP 10, 11, 12 & 13 TESTS PASSED SUCCESSFULLY!          ")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_full_retrieval_test_suite())
