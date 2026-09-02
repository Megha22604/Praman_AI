import io
import cv2
import numpy as np
from PIL import Image

# ArUco Configuration
ARUCO_DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_MARKER_ID = 0
DEFAULT_MARKER_SIZE_MM = 40.0


def _load_cv_image(image_bytes: bytes) -> np.ndarray:
    """
    Opens raw image bytes with PIL, converts to RGB,
    and returns a BGR numpy array for OpenCV processing.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        rgb_array = np.array(image)
        return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    except Exception:
        # Fallback to OpenCV native decode
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            return img
        raise ValueError("Invalid or unreadable image data.")


def detect_aruco_marker(
    image_bytes: bytes,
    marker_size_mm: float = DEFAULT_MARKER_SIZE_MM
) -> dict | None:
    """
    Detects the ArUco marker in the image and calculates the pixel-to-millimeter ratio.

    Returns:
        dict with keys:
            - marker_id (int)
            - pixels_per_mm (float)
            - marker_bbox_px (tuple: (x0, y0, x1, y1))
            - image_shape (tuple: (height, width))
        or None if no marker is detected or image cannot be read.
    """
    try:
        img = _load_cv_image(image_bytes)
    except Exception:
        return None

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(ARUCO_DICTIONARY, detector_params)
    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is None or len(ids) == 0:
        return None

    # Defensive flattening for inconsistent shape across OpenCV versions ((N, 1) vs (N,))
    flat_ids = np.asarray(ids).flatten()
    marker_id = int(flat_ids[0])

    # Corner points for the first detected marker (shape: 4, 2)
    pts = corners[0].reshape((4, 2))

    # Compute average side length across 4 edges
    e0 = np.linalg.norm(pts[0] - pts[1])
    e1 = np.linalg.norm(pts[1] - pts[2])
    e2 = np.linalg.norm(pts[2] - pts[3])
    e3 = np.linalg.norm(pts[3] - pts[0])
    avg_side_px = float(np.mean([e0, e1, e2, e3]))

    if marker_size_mm <= 0:
        pixels_per_mm = 0.0
    else:
        pixels_per_mm = float(avg_side_px / marker_size_mm)

    x0 = int(np.min(pts[:, 0]))
    y0 = int(np.min(pts[:, 1]))
    x1 = int(np.max(pts[:, 0]))
    y1 = int(np.max(pts[:, 1]))

    return {
        "marker_id": marker_id,
        "pixels_per_mm": pixels_per_mm,
        "marker_bbox_px": (x0, y0, x1, y1),
        "image_shape": (h, w)
    }


def detect_package_bbox_px(
    image_bytes: bytes,
    exclude_bbox_px: tuple | None = None
) -> tuple | None:
    """
    Detects the package bounding box in pixels from the image.

    Args:
        image_bytes: Raw image file bytes.
        exclude_bbox_px: Optional tuple (x0, y0, x1, y1) representing the marker region to exclude.

    Returns:
        tuple (x, y, w, h) in pixels for the largest candidate object, or None if no valid package is found.
    """
    try:
        img = _load_cv_image(image_bytes)
    except Exception:
        return None

    orig_h, orig_w = img.shape[:2]
    max_dim = max(orig_h, orig_w)
    scale = 1600.0 / float(max_dim) if max_dim > 1600 else 1.0
    if scale < 1.0:
        small_img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small_img = img

    h, w = small_img.shape[:2]
    img_area = float(w * h)

    gray = cv2.cvtColor(small_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate edges to close small gaps in contours
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    min_area = 0.01 * img_area
    max_area = 0.95 * img_area

    # Scale exclude_bbox_px to small_img coordinate system
    scaled_exclude = None
    if exclude_bbox_px is not None:
        scaled_exclude = (
            int(round(exclude_bbox_px[0] * scale)),
            int(round(exclude_bbox_px[1] * scale)),
            int(round(exclude_bbox_px[2] * scale)),
            int(round(exclude_bbox_px[3] * scale))
        )

    candidates = []

    for contour in contours:
        x, y, box_w, box_h = cv2.boundingRect(contour)
        box_area = float(box_w * box_h)

        if box_area < min_area or box_area > max_area:
            continue

        if scaled_exclude is not None:
            mx0, my0, mx1, my1 = scaled_exclude
            cx0, cy0, cx1, cy1 = x, y, x + box_w, y + box_h

            ix0 = max(cx0, mx0)
            iy0 = max(cy0, my0)
            ix1 = min(cx1, mx1)
            iy1 = min(cy1, my1)

            inter_w = max(0, ix1 - ix0)
            inter_h = max(0, iy1 - iy0)
            inter_area = float(inter_w * inter_h)

            marker_area = max(1.0, float((mx1 - mx0) * (my1 - my0)))
            if (inter_area / box_area > 0.2) or (inter_area / marker_area > 0.2):
                continue

        candidates.append((box_area, (x, y, box_w, box_h)))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_x, best_y, best_w, best_h = candidates[0][1]

    inv_scale = 1.0 / scale
    return (
        int(round(best_x * inv_scale)),
        int(round(best_y * inv_scale)),
        int(round(best_w * inv_scale)),
        int(round(best_h * inv_scale))
    )


# Indian Circulation Coin Reference Standards (RBI Specifications)
INR_10_COIN_DIAMETER_MM = 27.0  # Bi-metallic ₹10 Coin (27.0 mm diameter)
INR_5_COIN_DIAMETER_MM = 25.0   # Standard ₹5 Coin (25.0 mm diameter)


def detect_coin_reference(
    image_bytes: bytes,
    coin_type: str = "5_rupee"
) -> dict | None:
    """
    Detects a circular Indian reference coin (₹5: 25mm or ₹10: 27mm) in the image
    and computes the physical pixels-per-mm calibration scale.
    Optimized with scale normalization for fast, sub-second execution on high-res photos.
    """
    try:
        img = _load_cv_image(image_bytes)
    except Exception:
        return None

    orig_h, orig_w = img.shape[:2]
    
    # Scale normalize image so Hough transform runs in < 1 second even on 4K/12MP photos
    max_dim = max(orig_h, orig_w)
    scale = 1200.0 / float(max_dim) if max_dim > 1200 else 1.0
    if scale < 1.0:
        small_img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
    else:
        small_img = img

    h, w = small_img.shape[:2]
    gray = cv2.cvtColor(small_img, cv2.COLOR_BGR2GRAY)
    
    # Contrast boost + smooth local engraving
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (9, 9), 2.0)

    min_dim = min(h, w)
    min_radius = max(15, int(min_dim * 0.02))
    max_radius = max(60, int(min_dim * 0.18))

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_radius * 2,
        param1=120,
        param2=42,
        minRadius=min_radius,
        maxRadius=max_radius
    )

    if circles is None or len(circles) == 0:
        return None

    diameter_mm = INR_5_COIN_DIAMETER_MM if coin_type == "5_rupee" else INR_10_COIN_DIAMETER_MM
    ref_name = "₹5 Coin (25mm)" if coin_type == "5_rupee" else "₹10 Coin (27mm)"

    # Pick the strongest candidate and map back to full original image coordinates
    cx_s, cy_s, r_s = circles[0][0]
    inv_scale = 1.0 / scale
    
    cx = int(round(cx_s * inv_scale))
    cy = int(round(cy_s * inv_scale))
    r = float(r_s * inv_scale)

    x0 = max(0, int(cx - r))
    y0 = max(0, int(cy - r))
    x1 = min(orig_w, int(cx + r))
    y1 = min(orig_h, int(cy + r))

    diameter_px = 2.0 * r
    if diameter_px <= 0:
        return None

    ppm = float(diameter_px / diameter_mm)

    return {
        "reference_type": coin_type,
        "reference_name": ref_name,
        "pixels_per_mm": ppm,
        "marker_bbox_px": (x0, y0, x1, y1),
        "center": (cx, cy),
        "radius_px": r,
        "image_shape": (orig_h, orig_w)
    }


def calibrate_package_dimensions(
    image_bytes: bytes,
    marker_size_mm: float = DEFAULT_MARKER_SIZE_MM,
    default_coin: str = "10_rupee"
) -> dict:
    """
    Orchestrates physical dimension calibration and package bounding box measurement
    using either:
      1. ArUco Marker (40mm) [Primary reference]
      2. Indian ₹10 / ₹5 Coin [Zero-setup fallback reference]

    Returns:
        dict with success status, measured dimensions or descriptive error message.
    """
    # 1. Primary: Check for ArUco Marker
    marker_info = detect_aruco_marker(image_bytes, marker_size_mm=marker_size_mm)
    ref_name = f"ArUco Marker ({int(marker_size_mm)}mm)"
    ref_type = "aruco_marker"

    # 2. Fallback: Check for Indian Circulation Coin
    if marker_info is None:
        coin_info = detect_coin_reference(image_bytes, coin_type=default_coin)
        if coin_info is not None:
            marker_info = coin_info
            ref_name = coin_info["reference_name"]
            ref_type = coin_info["reference_type"]

    if marker_info is None:
        size_display = int(marker_size_mm) if marker_size_mm.is_integer() else marker_size_mm
        return {
            "success": False,
            "message": (
                f"No calibration reference detected. Place a {size_display}mm ArUco marker OR an Indian ₹10 / ₹5 coin "
                "flat next to the product (fully visible, not tilted), and rescan."
            )
        }

    exclude_bbox = marker_info["marker_bbox_px"]
    package_bbox = detect_package_bbox_px(image_bytes, exclude_bbox_px=exclude_bbox)

    if package_bbox is None:
        return {
            "success": False,
            "message": (
                f"{ref_name} detected, but the package outline could not be isolated. "
                "Retake the photo with the product and reference both flat, well-lit, and against a plain background."
            )
        }

    x, y, w_px, h_px = package_bbox
    px_per_mm = marker_info["pixels_per_mm"]

    if px_per_mm <= 0:
        return {
            "success": False,
            "message": "Invalid calibration ratio calculated."
        }

    # Convert px -> mm -> cm
    width_mm = w_px / px_per_mm
    height_mm = h_px / px_per_mm

    width_cm = round(width_mm / 10.0, 2)
    height_cm = round(height_mm / 10.0, 2)
    area_cm2 = round(width_cm * height_cm, 2)

    return {
        "success": True,
        "height_cm": height_cm,
        "width_cm": width_cm,
        "area_cm2": area_cm2,
        "pixels_per_mm": round(px_per_mm, 3),
        "reference_type": ref_type,
        "reference_name": ref_name,
        "marker_id": marker_info.get("marker_id")
    }


def generate_marker_png_bytes(
    marker_size_px: int = 600,
    marker_size_mm: float = DEFAULT_MARKER_SIZE_MM
) -> bytes:
    """
    Generates a printable PNG containing the ArUco calibration marker
    with a quiet-zone border and physical print dimension instructions.
    """
    marker = cv2.aruco.generateImageMarker(ARUCO_DICTIONARY, ARUCO_MARKER_ID, marker_size_px)
    quiet_zone = max(50, int(marker_size_px * 0.12))
    caption_height = max(70, int(marker_size_px * 0.15))

    total_w = marker_size_px + 2 * quiet_zone
    total_h = marker_size_px + 2 * quiet_zone + caption_height

    # Create white canvas
    canvas = np.ones((total_h, total_w, 3), dtype=np.uint8) * 255

    # Paste marker into canvas
    marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    canvas[quiet_zone:quiet_zone + marker_size_px, quiet_zone:quiet_zone + marker_size_px] = marker_bgr

    # Draw border around marker quiet zone for easy cutting guide
    cv2.rectangle(canvas, (quiet_zone // 2, quiet_zone // 2),
                  (total_w - quiet_zone // 2, quiet_zone + marker_size_px + quiet_zone // 2),
                  (220, 220, 220), 1, cv2.LINE_AA)

    # Caption text
    size_str = f"{int(marker_size_mm) if marker_size_mm.is_integer() else marker_size_mm}mm"
    caption = f"Print at 100% scale - marker must measure {size_str} x {size_str}"

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.65
    thickness = 2
    (tw, th), _ = cv2.getTextSize(caption, font, font_scale, thickness)
    tx = max(10, (total_w - tw) // 2)
    ty = quiet_zone + marker_size_px + quiet_zone // 2 + (caption_height // 2)

    cv2.putText(canvas, caption, (tx, ty), font, font_scale, (30, 30, 30), thickness, cv2.LINE_AA)

    ok, buf = cv2.imencode(".png", canvas)
    if not ok:
        raise RuntimeError("Failed to encode calibration marker PNG.")

    return buf.tobytes()




