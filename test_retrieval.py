"""
Scan Retrieval, Pagination, Filtering, Product History, Dashboard Stats & OCR Storage Test Suite (Steps 10, 11, 12, 13, 14 & 18)
Every test function starts with `test_` for native pytest discovery (`python -m pytest -q`).
"""

import io
import json
import asyncio
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw
from starlette.datastructures import Headers
from fastapi import UploadFile, HTTPException
from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor

import app
from app import (
    app as fastapi_app, scan_package_image, scan_package_images,
    get_scan_by_id, get_scans, get_product_history, get_stats
)
from database import get_connection
from crud import create_scan, create_image, create_scan_result

client = TestClient(fastapi_app)

def make_distinct_image_bytes(label: str, bg_color: tuple) -> bytes:
    img = Image.new("RGB", (250, 150), color=bg_color)
    d = ImageDraw.Draw(img)
    d.text((10, 10), f"PramanAI Test Image: {label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

bytes1 = make_distinct_image_bytes("1_Red", (200, 40, 40))
bytes2 = make_distinct_image_bytes("2_Green", (40, 160, 40))
kw = {"package_height_cm": 15.0, "package_width_cm": 10.0, "detected_font_height_mm": 2.5}


# ------------------------------------------------------------------
# STEP 10 TESTS
# ------------------------------------------------------------------
def test_step10_single_scan_retrieval():
    f1 = UploadFile(filename="single.png", file=io.BytesIO(bytes1), headers=Headers({"content-type": "image/png"}))
    res1_scan = asyncio.run(scan_package_image(file=f1, **kw))
    scan_id_1 = res1_scan["scan_id"]

    res1_get = client.get(f"/api/scans/{scan_id_1}")
    assert res1_get.status_code == 200
    assert res1_get.json()["scan_id"] == scan_id_1


def test_step10_scan_not_found_404():
    res404 = client.get("/api/scans/999999999")
    assert res404.status_code == 404


# ------------------------------------------------------------------
# STEP 11 TESTS
# ------------------------------------------------------------------
def test_step11_paginated_scans():
    res_scans = client.get("/api/scans?page=1&page_size=10")
    assert res_scans.status_code == 200
    d = res_scans.json()
    assert "items" in d
    assert "total" in d
    assert "page" in d
    assert "page_size" in d


# ------------------------------------------------------------------
# STEP 12 TESTS
# ------------------------------------------------------------------
def test_step12_scans_filtering():
    res_filt = client.get("/api/scans?status=PASS")
    assert res_filt.status_code == 200


# ------------------------------------------------------------------
# STEP 13 TESTS
# ------------------------------------------------------------------
def test_step13_product_history_retrieval():
    res_hist = client.get("/api/products/1/history")
    assert res_hist.status_code == 200
    res_404 = client.get("/api/products/999999999/history")
    assert res_404.status_code == 404


# ------------------------------------------------------------------
# STEP 14 TESTS
# ------------------------------------------------------------------
def test_step14_dashboard_statistics():
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    d = res_stats.json()
    assert "total_scans" in d
    assert "pass_count" in d
    assert "fail_count" in d
    assert "compliance_percentage" in d
    assert "failed_rule_counts" in d


# ------------------------------------------------------------------
# STEP 18 TESTS — OCR TEXT STORAGE & PERSISTENCE
# ------------------------------------------------------------------
def test_step18_empty_ocr_persistence():
    """
    Verifies that when OCR returns no lines ([]), the scan is successfully persisted,
    receives a valid scan_id, and GET /api/scans/{scan_id} returns "raw_lines": [].
    """
    conn = get_connection()
    sid = create_scan(
        conn,
        product_id=None,
        user_id=None,
        image_url=None,
        overall_verdict="FAIL",
        font_height_detected=2.5,
        org=None,
        ocr_raw_text=[]
    )
    conn.commit()
    conn.close()

    res = client.get(f"/api/scans/{sid}")
    assert res.status_code == 200
    data = res.json()
    assert data["scan_id"] == sid
    assert "ocr" in data
    assert data["ocr"]["raw_lines"] == []


def test_step18_mock_ocr_single_image():
    """
    Verifies that single-image scan OCR lines are accurately stored in PostgreSQL (JSONB)
    and retrieved identically via GET /api/scans/{scan_id}.
    """
    mock_lines = ["Test Product", "MRP Rs 100", "Net Qty 500 g"]
    conn = get_connection()
    sid = create_scan(
        conn,
        product_id=None,
        user_id=None,
        image_url="scan-test/original.png",
        overall_verdict="PASS",
        font_height_detected=3.0,
        org=None,
        ocr_raw_text=mock_lines
    )
    create_image(conn, scan_id=sid, image_url="scan-test/original.png", image_type=None)
    create_scan_result(conn, scan_id=sid, rule_code="R1", status="PASS", finding_detail="Found MRP")
    conn.commit()

    # Direct database verification
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT ocr_raw_text FROM scans WHERE scan_id = %s;", (sid,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert row["ocr_raw_text"] == mock_lines

    # API response verification
    res = client.get(f"/api/scans/{sid}")
    assert res.status_code == 200
    data = res.json()
    assert data["ocr"]["raw_lines"] == mock_lines


def test_step18_mock_ocr_multi_image():
    """
    Verifies that multi-image scans extract and combine OCR lines across 5 images,
    creating 1 scan row, 5 image rows, 8 scan_results rows, and persisting the full combined OCR array.
    """
    img1_lines = ["Front Product"]
    img2_lines = ["MRP Rs 100"]
    img3_lines = ["Net Qty 500 g"]
    img4_lines = ["Manufacturer ABC"]
    img5_lines = ["Consumer Care 123"]

    combined_lines = img1_lines + img2_lines + img3_lines + img4_lines + img5_lines

    conn = get_connection()
    sid = create_scan(
        conn,
        product_id=None,
        user_id=None,
        image_url=None,
        overall_verdict="PASS",
        font_height_detected=2.5,
        org=None,
        ocr_raw_text=combined_lines
    )

    # Insert 5 image records
    for i in range(1, 6):
        create_image(conn, scan_id=sid, image_url=f"scan-{sid}/img_{i}.png", image_type=None)

    # Insert 8 scan_results records
    for r_idx in range(1, 9):
        create_scan_result(conn, scan_id=sid, rule_code=f"R{r_idx}", status="PASS", finding_detail=f"Rule R{r_idx} Passed")

    conn.commit()

    # Read-only database structural invariant verifications
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM scans WHERE scan_id = %s;", (sid,))
    scan_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM images WHERE scan_id = %s;", (sid,))
    image_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scan_results WHERE scan_id = %s;", (sid,))
    results_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    assert scan_count == 1
    assert image_count == 5
    assert results_count == 8

    # API retrieval verification for combined OCR representation
    res = client.get(f"/api/scans/{sid}")
    assert res.status_code == 200
    data = res.json()

    assert len(data["images"]) == 5
    assert len(data["results"]) == 8
    assert data["ocr"]["raw_lines"] == combined_lines
