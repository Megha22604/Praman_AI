"""
PramanAI Database CRUD Access Layer (Step 3)
Provides database access functions for creating and reading scan records.
Functions accept an active psycopg2 connection and do not manage transactions internally.
"""

import json
import math

def create_scan(
    conn,
    product_id=None,
    user_id=None,
    image_url=None,
    overall_verdict=None,
    font_height_detected=None,
    org=None,
    ocr_raw_text=None
):
    """
    Inserts a new record into the scans table and returns the generated scan_id.
    Caller controls the transaction.
    """
    ocr_json = None
    if ocr_raw_text is not None:
        if isinstance(ocr_raw_text, (list, dict)):
            ocr_json = json.dumps(ocr_raw_text)
        elif isinstance(ocr_raw_text, str):
            ocr_json = ocr_raw_text

    with conn.cursor() as cur:
        query = """
        INSERT INTO scans (
            product_id,
            user_id,
            image_url,
            overall_verdict,
            font_height_detected,
            org,
            ocr_raw_text
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING scan_id;
        """
        cur.execute(query, (product_id, user_id, image_url, overall_verdict, font_height_detected, org, ocr_json))
        scan_id = cur.fetchone()[0]
        return scan_id


def create_scan_result(
    conn,
    scan_id,
    rule_code,
    status,
    finding_detail=None
):
    """
    Inserts a new result record into the scan_results table and returns the generated result_id.
    Caller controls the transaction.
    """
    with conn.cursor() as cur:
        query = """
        INSERT INTO scan_results (
            scan_id,
            rule_code,
            status,
            finding_detail
        )
        VALUES (%s, %s, %s, %s)
        RETURNING result_id;
        """
        cur.execute(query, (scan_id, rule_code, status, finding_detail))
        result_id = cur.fetchone()[0]
        return result_id


def get_scan(conn, scan_id):
    """
    Fetches a scan record by scan_id from the scans table.
    Returns a dictionary containing row attributes or None if not found.
    """
    with conn.cursor() as cur:
        query = """
        SELECT
            scan_id,
            product_id,
            user_id,
            image_url,
            timestamp,
            overall_verdict,
            font_height_detected,
            org,
            ocr_raw_text
        FROM scans
        WHERE scan_id = %s;
        """
        cur.execute(query, (scan_id,))
        row = cur.fetchone()
        if not row:
            return None
        
        if isinstance(row, dict):
            return row
            
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


def create_image(
    conn,
    scan_id,
    image_url,
    image_type=None
):
    """
    Inserts an image reference record into the images table and returns the generated image_id.
    Caller controls the transaction.
    """
    with conn.cursor() as cur:
        query = """
        INSERT INTO images (
            scan_id,
            image_url,
            image_type
        )
        VALUES (%s, %s, %s)
        RETURNING image_id;
        """
        cur.execute(query, (scan_id, image_url, image_type))
        image_id = cur.fetchone()[0]
        return image_id


def get_scan_results_for_scan(conn, scan_id):
    """
    Fetches all scan_results records for a given scan_id ordered by result_id ASC.
    Returns a list of dictionaries.
    """
    with conn.cursor() as cur:
        query = """
        SELECT
            result_id,
            scan_id,
            rule_code,
            status,
            finding_detail,
            created_at
        FROM scan_results
        WHERE scan_id = %s
        ORDER BY result_id ASC;
        """
        cur.execute(query, (scan_id,))
        rows = cur.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]


def get_images_for_scan(conn, scan_id):
    """
    Fetches all images records for a given scan_id ordered by image_id ASC.
    Returns a list of dictionaries.
    """
    with conn.cursor() as cur:
        query = """
        SELECT
            image_id,
            scan_id,
            image_url,
            image_type,
            created_at
        FROM images
        WHERE scan_id = %s
        ORDER BY image_id ASC;
        """
        cur.execute(query, (scan_id,))
        rows = cur.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]


def get_paginated_scans(
    conn,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    failed_rule: str | None = None,
    start_date=None,
    end_date=None,
    product_name: str | None = None,
    brand: str | None = None,
    inspector: str | None = None
):
    """
    Fetches paginated scan records ordered by timestamp DESC, scan_id DESC with optional filters.
    Returns a dictionary containing items, page, page_size, total, and total_pages.
    Uses SQL LIMIT, OFFSET, and parameterized WHERE conditions.
    """
    where_clauses = []
    params = []

    if status:
        where_clauses.append("s.overall_verdict = %s")
        params.append(status)

    if start_date:
        where_clauses.append("s.timestamp >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("s.timestamp <= %s")
        params.append(end_date)

    if failed_rule:
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM scan_results sr 
                WHERE sr.scan_id = s.scan_id 
                AND sr.rule_code = %s 
                AND sr.status = 'FAIL'
            )
        """)
        params.append(failed_rule)

    if product_name:
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM products p 
                WHERE p.product_id = s.product_id 
                AND p.name ILIKE %s
            )
        """)
        params.append(f"%{product_name.strip()}%")

    if brand:
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM products p 
                WHERE p.product_id = s.product_id 
                AND p.brand ILIKE %s
            )
        """)
        params.append(f"%{brand.strip()}%")

    if inspector:
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM users u 
                WHERE u.user_id = s.user_id 
                AND (u.name ILIKE %s OR CAST(u.user_id AS TEXT) = %s)
            )
        """)
        insp_val = inspector.strip()
        params.extend([f"%{insp_val}%", insp_val])

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    offset = (page - 1) * page_size

    with conn.cursor() as cur:
        # 1. Count query
        count_query = f"SELECT COUNT(*) FROM scans s {where_sql};"
        cur.execute(count_query, tuple(params))
        count_row = cur.fetchone()
        total = count_row[0] if not isinstance(count_row, dict) else list(count_row.values())[0]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        # 2. Paginated data query
        data_query = f"""
        SELECT
            s.scan_id,
            s.product_id,
            s.user_id,
            s.image_url,
            s.timestamp,
            s.overall_verdict,
            s.font_height_detected,
            s.org,
            s.ocr_raw_text
        FROM scans s
        {where_sql}
        ORDER BY s.timestamp DESC, s.scan_id DESC
        LIMIT %s OFFSET %s;
        """
        data_params = tuple(params) + (page_size, offset)
        cur.execute(data_query, data_params)
        rows = cur.fetchall()

        items = []
        if rows:
            if isinstance(rows[0], dict):
                items = rows
            else:
                columns = [desc[0] for desc in cur.description]
                items = [dict(zip(columns, row)) for row in rows]

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }


def get_product(conn, product_id: int):
    """
    Fetches a single product record by product_id from the products table.
    Returns a dictionary or None if not found.
    """
    with conn.cursor() as cur:
        query = """
        SELECT product_id, name, brand, category, created_at
        FROM products
        WHERE product_id = %s;
        """
        cur.execute(query, (product_id,))
        row = cur.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return row
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


def get_paginated_scans_for_product(conn, product_id: int, page: int = 1, page_size: int = 10):
    """
    Fetches paginated scan records for a specific product_id ordered by timestamp DESC, scan_id DESC.
    Returns a dictionary containing items, page, page_size, total, and total_pages.
    """
    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        # 1. Total count query
        cur.execute("SELECT COUNT(*) FROM scans WHERE product_id = %s;", (product_id,))
        count_row = cur.fetchone()
        total = count_row[0] if not isinstance(count_row, dict) else list(count_row.values())[0]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        # 2. Paginated data query
        query = """
        SELECT
            scan_id,
            product_id,
            user_id,
            image_url,
            timestamp,
            overall_verdict,
            font_height_detected,
            org,
            ocr_raw_text
        FROM scans
        WHERE product_id = %s
        ORDER BY timestamp DESC, scan_id DESC
        LIMIT %s OFFSET %s;
        """
        cur.execute(query, (product_id, page_size, offset))
        rows = cur.fetchall()

        items = []
        if rows:
            if isinstance(rows[0], dict):
                items = rows
            else:
                columns = [desc[0] for desc in cur.description]
                items = [dict(zip(columns, row)) for row in rows]

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
