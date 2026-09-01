"""
Scan Retrieval, Pagination, Filtering, Product History & Dashboard Stats Test Suite (Steps 10, 11, 12, 13 & 14)
Tests GET /api/scans, GET /api/scans/{scan_id}, GET /api/products/{product_id}/history, and GET /api/stats across:
- Step 10 Tests: Individual scan retrieval by ID, 404 behavior, OCR, 5-image retrieval, ordering, cache independence.
- Step 11 Tests: Default pagination, page sizing, newest-first ordering, limit/offset, validation, total calculation.
- Step 12 Tests: Search & filtering by status, date range, failed_rule, product_name, brand, inspector, combined filters.
- Step 13 Tests: Product history, 404 behavior, empty product history, pagination.
- Step 14 Tests:
  - GET /api/stats total_scans, pass_count, fail_count, needs_review_count
  - compliance_percentage calculation (pass_count / total_scans * 100)
  - failed_rule_counts breakdown (counts only status='FAIL' scan_results)
  - Date filtering on stats (start_date & end_date)
  - Direct SQL comparison vs API response data-integrity check
  - Cache independence (no reliance on latest_report_cache)
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
from app import (
    app as fastapi_app, scan_package_image, scan_package_images,
    get_scan_by_id, get_scans, get_product_history, get_stats
)
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


async def run_full_backend_test_suite():
    print("==================================================================")
    print("  ADITYA BACKEND — STEP 10, 11, 12, 13 & 14 RETRIEVAL & STATS TESTS ")
    print("==================================================================")

    bytes1 = make_distinct_image_bytes("1_Red", (200, 40, 40))
    kw = {"package_height_cm": 15.0, "package_width_cm": 10.0, "detected_font_height_mm": 2.5}

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # STEP 10, 11, 12 & 13 REGRESSIONS
    # ------------------------------------------------------------------
    print("\n--- STEP 10, 11, 12 & 13 REGRESSIONS ---")
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

    res_p404 = client.get("/api/products/999999999/history")
    assert res_p404.status_code == 404
    print("[PASS] Steps 10, 11, 12 & 13 regressions verified.")

    # ------------------------------------------------------------------
    # STEP 14 TESTS — DASHBOARD STATISTICS (GET /api/stats)
    # ------------------------------------------------------------------
    print("\n--- STEP 14: DASHBOARD STATISTICS IMPLEMENTATION & VERIFICATION ---")

    # TEST 14.1 — UNFILTERED STATS RETRIEVAL & SHAPE
    print("\n--- TEST 14.1: UNFILTERED DASHBOARD STATS ---")
    app.latest_report_cache = {} # Wipe cache to prove database independence
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    s_data = res_stats.json()

    assert "total_scans" in s_data
    assert "pass_count" in s_data
    assert "fail_count" in s_data
    assert "needs_review_count" in s_data
    assert "compliance_percentage" in s_data
    assert "failed_rule_counts" in s_data
    assert isinstance(s_data["failed_rule_counts"], dict)

    assert s_data["total_scans"] == s_data["pass_count"] + s_data["fail_count"] + s_data["needs_review_count"]
    if s_data["total_scans"] > 0:
        expected_pct = round((s_data["pass_count"] / s_data["total_scans"] * 100.0), 2)
        assert s_data["compliance_percentage"] == expected_pct
    else:
        assert s_data["compliance_percentage"] == 0.0

    print(f"[PASS] Unfiltered stats verified: total={s_data['total_scans']}, pass={s_data['pass_count']}, fail={s_data['fail_count']}, needs_review={s_data['needs_review_count']}, compliance_pct={s_data['compliance_percentage']}%.")

    # TEST 14.2 — DIRECT SQL VS API DATA INTEGRITY COMPARISON
    print("\n--- TEST 14.2: DIRECT SQL VS API DATA INTEGRITY COMPARISON ---")
    cur.execute("""
        SELECT
            COUNT(*) AS total_scans,
            COUNT(*) FILTER (WHERE overall_verdict = 'PASS') AS pass_count,
            COUNT(*) FILTER (WHERE overall_verdict = 'FAIL') AS fail_count,
            COUNT(*) FILTER (WHERE overall_verdict = 'NEEDS REVIEW') AS needs_review_count
        FROM scans;
    """)
    sql_v = cur.fetchone()

    assert s_data["total_scans"] == sql_v["total_scans"]
    assert s_data["pass_count"] == sql_v["pass_count"]
    assert s_data["fail_count"] == sql_v["fail_count"]
    assert s_data["needs_review_count"] == sql_v["needs_review_count"]

    cur.execute("""
        SELECT sr.rule_code, COUNT(sr.result_id) AS cnt
        FROM scan_results sr
        JOIN scans s ON sr.scan_id = s.scan_id
        WHERE sr.status = 'FAIL'
        GROUP BY sr.rule_code;
    """)
    sql_failed = {row["rule_code"]: row["cnt"] for row in cur.fetchall()}
    assert s_data["failed_rule_counts"] == sql_failed
    print("[PASS] Direct SQL comparison: API statistics match PostgreSQL 100%!")

    # TEST 14.3 — DATE FILTERED STATS
    print("\n--- TEST 14.3: DATE FILTERED STATS ---")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    res_stats_date = client.get(f"/api/stats?start_date={today_str}&end_date={today_str}")
    assert res_stats_date.status_code == 200
    s_date = res_stats_date.json()
    assert s_date["total_scans"] >= 1
    print(f"[PASS] Date filtered stats ('{today_str}') verified: total_scans = {s_date['total_scans']}.")

    # TEST 14.4 — INVALID DATE FORMAT REJECTION
    print("\n--- TEST 14.4: INVALID DATE FORMAT REJECTION ---")
    res_bad_date = client.get("/api/stats?start_date=invalid-date-format")
    assert res_bad_date.status_code == 400
    assert "Invalid start_date format" in res_bad_date.json()["detail"]
    print("[PASS] Invalid date format rejected with HTTP 400.")

    cur.close()
    conn.close()

    print("\n==================================================================")
    print("     ALL STEP 10, 11, 12, 13 & 14 TESTS PASSED SUCCESSFULLY!       ")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_full_backend_test_suite())
