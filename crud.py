"""
PramanAI Database CRUD Access Layer (Step 3)
Provides database access functions for creating and reading scan records.
Functions accept an active psycopg2 connection and do not manage transactions internally.
"""

def create_scan(
    conn,
    product_id=None,
    user_id=None,
    image_url=None,
    overall_verdict=None,
    font_height_detected=None,
    org=None
):
    """
    Inserts a new record into the scans table and returns the generated scan_id.
    Caller controls the transaction.
    """
    with conn.cursor() as cur:
        query = """
        INSERT INTO scans (
            product_id,
            user_id,
            image_url,
            overall_verdict,
            font_height_detected,
            org
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING scan_id;
        """
        cur.execute(query, (product_id, user_id, image_url, overall_verdict, font_height_detected, org))
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
            org
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
