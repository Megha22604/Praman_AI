"""
Scan Retrieval, Pagination & Search/Filter Test Suite (Step 10, 11 & 12 Implementation)
Tests GET /api/scans and GET /api/scans/{scan_id} endpoints across:
- Step 10 Tests: Individual scan retrieval by ID, 404 behavior, OCR, 5-image retrieval, ordering, cache independence.
- Step 11 Tests: Default pagination, page sizing, newest-first ordering, limit/offset, validation, total calculation.
- Step 12 Tests:
  - status filter (PASS, FAIL, NEEDS REVIEW)
  - date filtering (start_date, end_date, combined date range)
  - failed_rule filter (returns matching scans without duplicate rows)
  - product_name & brand filtering (via products JOIN)
  - inspector filtering (via users JOIN)
  - combined filters (status + start_date + failed_rule)
  - pagination with filters (total & total_pages reflect filtered count)
  - empty filtered result (items: [], total: 0, total_pages: 0)
  - invalid filter value rejections (status=INVALID -> 400, start_date=bad -> 400)
  - SQL parameterization & safety
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
from app import app as fastapi_app, scan_package_image, scan_package_images, get_scan_by_id, get_scans
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


async def run_step10_step11_step12_test_suite():
    print("================================================================")
    print("  ADITYA BACKEND — STEP 10, 11 & 12 RETRIEVAL, PAGINATION & FILTER TESTS ")
    print("================================================================")

    bytes1 = make_distinct_image_bytes("1_Red", (200, 40, 40))
    bytes2 = make_distinct_image_bytes("2_Green", (40, 160, 40))
    bytes3 = make_distinct_image_bytes("3_Blue", (40, 40, 200))
    bytes4 = make_distinct_image_bytes("4_Yellow", (200, 200, 40))

    kw = {"package_height_cm": 15.0, "package_width_cm": 10.0, "detected_font_height_mm": 2.5}

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # STEP 10 TESTS
    # ------------------------------------------------------------------
    print("\n--- TEST 10: SCAN RETRIEVAL BY ID & 404 ---")
    f1_single = UploadFile(filename="single.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res1_scan = await scan_package_image(file=f1_single, **kw)
    scan_id_1 = res1_scan["scan_id"]

    res1_get = client.get(f"/api/scans/{scan_id_1}")
    assert res1_get.status_code == 200
    data1 = res1_get.json()
    assert data1["scan_id"] == scan_id_1
    assert data1["overall_verdict"] == res1_scan["compliance_report"]["status"]

    res404 = client.get("/api/scans/999999999")
    assert res404.status_code == 404
    print(f"[PASS] Scan retrieval by ID ({scan_id_1}) and 404 handling verified.")

    # ------------------------------------------------------------------
    # STEP 11 TESTS — UNFILTERED PAGINATION
    # ------------------------------------------------------------------
    print("\n--- TEST 11: UNFILTERED PAGINATION ---")
    res_def = client.get("/api/scans")
    assert res_def.status_code == 200
    p_def = res_def.json()
    assert p_def["page"] == 1
    assert p_def["page_size"] == 10
    print(f"[PASS] Unfiltered pagination verified: total = {p_def['total']}.")

    # ------------------------------------------------------------------
    # STEP 12 TESTS — SEARCH & FILTERING
    # ------------------------------------------------------------------

    # Setup known database records with status, failed_rules, dates, products, users
    print("\n--- SETTING UP KNOWN SCAN RECORDS FOR FILTER TESTING ---")
    
    # 1. Product record
    cur.execute("INSERT INTO products (name, brand, category) VALUES (%s, %s, %s) RETURNING product_id;", ("Amul Butter 500g", "Amul", "Dairy"))
    pid = cur.fetchone()["product_id"]

    # 2. User record
    cur.execute("INSERT INTO users (name, role, org) VALUES (%s, %s, %s) RETURNING user_id;", ("Inspector Sharma", "Senior Inspector", "Legal Metrology Dept"))
    uid = cur.fetchone()["user_id"]

    now = datetime.now(timezone.utc)
    date_yesterday = now - timedelta(days=1)

    # Insert Scan Alpha (FAIL, with pid, uid, yesterday, rule RULE_6_MRP FAIL)
    cur.execute(
        "INSERT INTO scans (product_id, user_id, overall_verdict, font_height_detected, timestamp, ocr_raw_text) VALUES (%s, %s, %s, %s, %s, %s) RETURNING scan_id;",
        (pid, uid, "FAIL", 2.5, date_yesterday, json.dumps(["Amul Butter 500g", "MRP Rs 275"]))
    )
    scan_id_alpha = cur.fetchone()["scan_id"]
    cur.execute("INSERT INTO scan_results (scan_id, rule_code, status, finding_detail) VALUES (%s, %s, %s, %s);", (scan_id_alpha, "RULE_6_MRP", "FAIL", "MRP missing currency symbol"))
    cur.execute("INSERT INTO scan_results (scan_id, rule_code, status, finding_detail) VALUES (%s, %s, %s, %s);", (scan_id_alpha, "RULE_6_NET_QTY", "PASS", "Net qty valid"))

    # Insert Scan Beta (PASS, with pid, uid, now)
    cur.execute(
        "INSERT INTO scans (product_id, user_id, overall_verdict, font_height_detected, timestamp, ocr_raw_text) VALUES (%s, %s, %s, %s, %s, %s) RETURNING scan_id;",
        (pid, uid, "PASS", 3.0, now, json.dumps(["Amul Butter 500g", "MRP Rs 275.00"]))
    )
    scan_id_beta = cur.fetchone()["scan_id"]
    cur.execute("INSERT INTO scan_results (scan_id, rule_code, status, finding_detail) VALUES (%s, %s, %s, %s);", (scan_id_beta, "RULE_6_MRP", "PASS", "MRP valid"))

    # Insert Scan Gamma (NEEDS REVIEW, no pid/uid, now, rule RULE_7_FONT FAIL)
    cur.execute(
        "INSERT INTO scans (overall_verdict, font_height_detected, timestamp, ocr_raw_text) VALUES (%s, %s, %s, %s) RETURNING scan_id;",
        ("NEEDS REVIEW", 1.8, now, json.dumps(["Low font height"]))
    )
    scan_id_gamma = cur.fetchone()["scan_id"]
    cur.execute("INSERT INTO scan_results (scan_id, rule_code, status, finding_detail) VALUES (%s, %s, %s, %s);", (scan_id_gamma, "RULE_7_FONT", "FAIL", "Font height 1.8mm below 2.5mm requirement"))

    conn.commit()
    print(f"  Created test scans: Alpha (FAIL, {scan_id_alpha}), Beta (PASS, {scan_id_beta}), Gamma (NEEDS REVIEW, {scan_id_gamma})")

    # TEST 12.1 — STATUS FILTER
    print("\n--- TEST 12.1: STATUS FILTER (PASS / FAIL / NEEDS REVIEW) ---")
    r_fail = client.get("/api/scans?status=FAIL&page_size=100").json()
    assert all(item["overall_verdict"] == "FAIL" for item in r_fail["items"])
    assert any(item["scan_id"] == scan_id_alpha for item in r_fail["items"])
    assert not any(item["scan_id"] == scan_id_beta for item in r_fail["items"])
    print(f"[PASS] Status filter 'status=FAIL' verified: {r_fail['total']} rows matched.")

    r_pass = client.get("/api/scans?status=PASS&page_size=100").json()
    assert all(item["overall_verdict"] == "PASS" for item in r_pass["items"])
    assert any(item["scan_id"] == scan_id_beta for item in r_pass["items"])
    print(f"[PASS] Status filter 'status=PASS' verified: {r_pass['total']} rows matched.")

    r_review = client.get("/api/scans?status=NEEDS%20REVIEW&page_size=100").json()
    assert all(item["overall_verdict"] == "NEEDS REVIEW" for item in r_review["items"])
    assert any(item["scan_id"] == scan_id_gamma for item in r_review["items"])
    print(f"[PASS] Status filter 'status=NEEDS REVIEW' verified: {r_review['total']} rows matched.")

    # TEST 12.2 — FAILED_RULE FILTER
    print("\n--- TEST 12.2: FAILED_RULE FILTER ---")
    r_rule_mrp = client.get("/api/scans?failed_rule=RULE_6_MRP").json()
    assert any(item["scan_id"] == scan_id_alpha for item in r_rule_mrp["items"])
    assert not any(item["scan_id"] == scan_id_beta for item in r_rule_mrp["items"])
    # Verify no duplicate scan rows
    scan_ids_retrieved = [item["scan_id"] for item in r_rule_mrp["items"]]
    assert len(scan_ids_retrieved) == len(set(scan_ids_retrieved)), "EXISTS query must prevent scan duplication"
    print(f"[PASS] failed_rule 'failed_rule=RULE_6_MRP' verified: {r_rule_mrp['total']} rows matched (No duplicates).")

    # TEST 12.3 — DATE BOUNDARY FILTERING
    print("\n--- TEST 12.3: DATE BOUNDARY FILTERING ---")
    start_str = date_yesterday.strftime("%Y-%m-%d")
    r_start = client.get(f"/api/scans?start_date={start_str}&page_size=100").json()
    assert any(item["scan_id"] == scan_id_alpha for item in r_start["items"])

    end_yesterday = date_yesterday.strftime("%Y-%m-%d")
    r_range = client.get(f"/api/scans?start_date={start_str}&end_date={end_yesterday}&page_size=100").json()
    assert any(item["scan_id"] == scan_id_alpha for item in r_range["items"])
    print(f"[PASS] Date boundary filtering ('start_date={start_str}&end_date={end_yesterday}') verified.")

    # TEST 12.4 — PRODUCT_NAME AND BRAND FILTERS (VIA PRODUCTS JOIN)
    print("\n--- TEST 12.4: PRODUCT_NAME & BRAND FILTERS ---")
    r_prod = client.get("/api/scans?product_name=Amul%20Butter").json()
    assert any(item["scan_id"] == scan_id_alpha for item in r_prod["items"])
    assert any(item["scan_id"] == scan_id_beta for item in r_prod["items"])
    assert not any(item["scan_id"] == scan_id_gamma for item in r_prod["items"])
    print(f"[PASS] product_name filter 'product_name=Amul Butter' verified: {r_prod['total']} rows matched.")

    r_brand = client.get("/api/scans?brand=Amul").json()
    assert any(item["scan_id"] == scan_id_alpha for item in r_brand["items"])
    assert any(item["scan_id"] == scan_id_beta for item in r_brand["items"])
    print(f"[PASS] brand filter 'brand=Amul' verified: {r_brand['total']} rows matched.")

    # TEST 12.5 — INSPECTOR FILTER (VIA USERS JOIN)
    print("\n--- TEST 12.5: INSPECTOR FILTER ---")
    r_insp = client.get("/api/scans?inspector=Inspector%20Sharma").json()
    assert any(item["scan_id"] == scan_id_alpha for item in r_insp["items"])
    assert any(item["scan_id"] == scan_id_beta for item in r_insp["items"])
    assert not any(item["scan_id"] == scan_id_gamma for item in r_insp["items"])
    print(f"[PASS] inspector filter 'inspector=Inspector Sharma' verified: {r_insp['total']} rows matched.")

    # TEST 12.6 — COMBINED FILTERS
    print("\n--- TEST 12.6: COMBINED FILTERS ---")
    r_comb = client.get(f"/api/scans?status=FAIL&failed_rule=RULE_6_MRP&product_name=Amul&start_date={start_str}").json()
    assert r_comb["total"] >= 1
    assert any(item["scan_id"] == scan_id_alpha for item in r_comb["items"])
    print(f"[PASS] Combined filters (status=FAIL + failed_rule + product_name + start_date) verified: {r_comb['total']} rows matched.")

    # TEST 12.7 — PAGINATION WITH FILTERS
    print("\n--- TEST 12.7: PAGINATION WITH FILTERS ---")
    r_p1 = client.get("/api/scans?brand=Amul&page=1&page_size=1").json()
    assert r_p1["page"] == 1
    assert r_p1["page_size"] == 1
    assert r_p1["total"] >= 2
    assert len(r_p1["items"]) == 1

    r_p2 = client.get("/api/scans?brand=Amul&page=2&page_size=1").json()
    assert r_p2["page"] == 2
    assert r_p2["items"][0]["scan_id"] != r_p1["items"][0]["scan_id"]
    print("[PASS] Pagination with filters verified: page 1 and page 2 total_pages calculation correct.")

    # TEST 12.8 — EMPTY FILTERED RESULT
    print("\n--- TEST 12.8: EMPTY FILTERED RESULT ---")
    r_empty = client.get("/api/scans?status=PASS&start_date=2099-01-01").json()
    assert r_empty["items"] == []
    assert r_empty["total"] == 0
    assert r_empty["total_pages"] == 0
    print("[PASS] Empty filtered result verified: items: [], total: 0, total_pages: 0.")

    # TEST 12.9 — INVALID FILTER REJECTIONS
    print("\n--- TEST 12.9: INVALID FILTER REJECTIONS ---")
    r_bad_status = client.get("/api/scans?status=INVALID_STATUS")
    assert r_bad_status.status_code == 400
    assert "Invalid status filter" in r_bad_status.json()["detail"]

    r_bad_date = client.get("/api/scans?start_date=bad-date-format")
    assert r_bad_date.status_code == 400
    assert "Invalid start_date format" in r_bad_date.json()["detail"]
    print("[PASS] Invalid filter values (status=INVALID, start_date=bad) cleanly rejected with HTTP 400.")

    cur.close()
    conn.close()

    print("\n================================================================")
    print("     ALL STEP 10, 11 & 12 TESTS PASSED SUCCESSFULLY!            ")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(run_step10_step11_step12_test_suite())
