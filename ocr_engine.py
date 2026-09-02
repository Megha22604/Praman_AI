import io
import gc
import os
import shutil
from PIL import Image, ImageOps
import cv2
import numpy as np
import pytesseract

# Auto-detect Tesseract executable across Windows and Linux / Docker environments
if not shutil.which("tesseract"):
    default_win_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(default_win_path):
        pytesseract.pytesseract.tesseract_cmd = default_win_path


# ---------------------------------------------------------------------------
#  Geometric correction helpers
# ---------------------------------------------------------------------------

def _order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders 4 corner points as: [top-left, top-right, bottom-right, bottom-left].

    Uses the sum (x+y) and difference (y-x) heuristic:
      - Top-left has the smallest sum
      - Bottom-right has the largest sum
      - Top-right has the smallest difference (y - x)
      - Bottom-left has the largest difference (y - x)
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right

    # diff along axis=1 gives (y - x) for each point; flatten to 1-D
    d = (pts[:, 1] - pts[:, 0])
    rect[1] = pts[np.argmin(d)]   # top-right  (smallest y-x)
    rect[3] = pts[np.argmax(d)]   # bottom-left (largest y-x)
    return rect


def _perspective_correct(rgb_img: np.ndarray) -> np.ndarray:
    """
    Detects quadrilateral package/label boundaries in the image and applies
    perspective warp only when genuine trapezoidal/perspective distortion exists.

    Safety guards:
      - Returns original image if no quadrilateral is detected.
      - Requires the detected quad to cover > 35% of the image area.
      - Checks if the quad is already rectangular: if all opposite sides are nearly
        equal (within 5%) and corners are near 90°, skips warping to avoid
        unnecessary resampling blur.
      - Rejects degenerate aspect ratios (> 5:1).
    """
    h, w = rgb_img.shape[:2]
    img_area = float(w * h)

    gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return rgb_img

    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    target_quad = None
    for contour in contours[:5]:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) == 4 and cv2.contourArea(approx) > 0.35 * img_area:
            target_quad = approx
            break

    if target_quad is None:
        return rgb_img

    pts = _order_points(target_quad.reshape(4, 2).astype(np.float32))

    width_top = np.linalg.norm(pts[1] - pts[0])
    width_bot = np.linalg.norm(pts[2] - pts[3])
    max_width = int(max(width_top, width_bot))

    height_left = np.linalg.norm(pts[3] - pts[0])
    height_right = np.linalg.norm(pts[2] - pts[1])
    max_height = int(max(height_left, height_right))

    if max_width < 20 or max_height < 20:
        return rgb_img
    aspect = max(max_width, max_height) / max(1, min(max_width, max_height))
    if aspect > 5.0:
        return rgb_img

    # Check if perspective warp is actually needed (e.g. trapezoid side length difference > 6%)
    w_diff = abs(width_top - width_bot) / max(width_top, width_bot)
    h_diff = abs(height_left - height_right) / max(height_left, height_right)
    
    # If the detected shape is already almost perfectly rectangular, avoid resampling
    if w_diff < 0.06 and h_diff < 0.06:
        return rgb_img

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(pts, dst)
    warped = cv2.warpPerspective(rgb_img, M, (max_width, max_height),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
    return warped


def _deskew_image(gray_img: np.ndarray) -> np.ndarray:
    """
    Corrects small rotational skew by detecting the dominant text-line
    angle via the Probabilistic Hough Line Transform and rotating the
    image to make text horizontal.

    Safety guards:
      - Skips if fewer than 5 line segments are detected.
      - Skips if the median angle is < 0.5° (already straight).
      - Skips if the median angle is > 15° (likely not simple skew).
      - Expands the canvas during rotation to prevent corner cropping.
      - Uses BORDER_REPLICATE to fill new areas with edge pixels.
    """
    h, w = gray_img.shape[:2]

    # Edge detection tuned for text lines
    edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)

    # Detect line segments
    min_line_len = max(30, w // 8)
    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi / 180,
                            threshold=80,
                            minLineLength=min_line_len,
                            maxLineGap=10)

    if lines is None or len(lines) < 5:
        return gray_img

    # Reshape defensively to (N, 4) to support varied OpenCV version shapes
    flat_lines = lines.reshape(-1, 4)

    # Compute angle of each line; keep only near-horizontal ones
    angles = []
    for x1, y1, x2, y2 in flat_lines:
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 30:
            angles.append(angle)

    if len(angles) < 3:
        return gray_img

    median_angle = float(np.median(angles))

    # Too small to matter or too large to be simple skew
    if abs(median_angle) < 0.5 or abs(median_angle) > 15:
        return gray_img

    # Build rotation matrix around the image centre
    cx, cy = w / 2.0, h / 2.0
    M = cv2.getRotationMatrix2D((cx, cy), median_angle, 1.0)

    # Compute expanded canvas size so no corners are clipped
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    # Shift the rotation centre to the new canvas centre
    M[0, 2] += (new_w - w) / 2.0
    M[1, 2] += (new_h - h) / 2.0

    rotated = cv2.warpAffine(gray_img, M, (new_w, new_h),
                             flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    return rotated


# ---------------------------------------------------------------------------
#  Main preprocessing pipeline
# ---------------------------------------------------------------------------

def preprocess_image_with_scale(pil_img: Image.Image) -> tuple[np.ndarray, float]:
    """
    Full preprocessing pipeline for OCR:
      1. EXIF orientation correction
      2. RGB conversion
      3. Smart resize (600–2000 px range)
      4. Perspective correction (flatten tilted labels)
      5. Grayscale conversion
      6. Deskew rotation (straighten text lines)
      7. CLAHE adaptive contrast
      8. Bilateral noise filtering

    Returns:
        tuple[np.ndarray, float]: (preprocessed_grayscale_image, scale_factor)
    """
    # 1. Correct smartphone EXIF orientation
    pil_img = ImageOps.exif_transpose(pil_img)

    # 2. Convert to RGB numpy array
    rgb_img = np.array(pil_img.convert("RGB"))

    # 3. Resize if image is too large or too small
    h, w = rgb_img.shape[:2]
    max_dim = max(h, w)
    min_dim = min(h, w)

    scale_factor = 1.0
    if max_dim > 3600:
        scale_factor = 3600.0 / float(max_dim)
        rgb_img = cv2.resize(rgb_img, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_AREA)
    elif min_dim < 600:
        scale_factor = 600.0 / float(min_dim)
        rgb_img = cv2.resize(rgb_img, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)

    # 4. Perspective correction — flatten tilted / trapezoidal labels (operates on RGB)
    try:
        rgb_img = _perspective_correct(rgb_img)
    except Exception:
        pass  # Fall through with original image if perspective correction fails

    # 5. Convert to Grayscale
    gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)

    # 6. Deskew — straighten small rotational skew (operates on grayscale)
    try:
        gray = _deskew_image(gray)
    except Exception:
        pass  # Fall through with original grayscale if deskew fails

    # 7. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for even lighting
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 8. Gentle bilateral filtering to smooth background noise while keeping text edges crisp
    smoothed = cv2.bilateralFilter(enhanced, d=5, sigmaColor=50, sigmaSpace=50)

    return smoothed, scale_factor


def preprocess_image(pil_img: Image.Image) -> np.ndarray:
    """Convenience wrapper returning only the processed image array."""
    processed, _ = preprocess_image_with_scale(pil_img)
    return processed


def _is_meaningful_line(line: str) -> bool:
    """Filters out pure noise lines containing mostly non-alphanumeric artifacts."""
    cleaned = line.strip()
    if not cleaned or len(cleaned) < 2:
        return False
    alnum_count = sum(1 for c in cleaned if c.isalnum())
    # Require at least 2 alphanumeric characters and at least 35% alphanumeric content
    return alnum_count >= 2 and (alnum_count / len(cleaned)) >= 0.35


def _parse_image_data_to_lines(data: dict) -> list[dict]:
    """
    Groups tokenized OCR word boxes by line hierarchy (block, paragraph, line)
    and computes mean confidence score per extracted line.
    """
    lines_dict = {}
    n_boxes = len(data.get('text', []))
    for i in range(n_boxes):
        text = str(data['text'][i]).strip()
        try:
            conf = float(data['conf'][i])
        except (ValueError, TypeError):
            conf = -1.0

        if not text or conf < 0:
            continue

        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        if key not in lines_dict:
            lines_dict[key] = {'words': [], 'confs': []}
        lines_dict[key]['words'].append(text)
        lines_dict[key]['confs'].append(conf)

    results = []
    for key, line_info in lines_dict.items():
        line_str = " ".join(line_info['words']).strip()
        if _is_meaningful_line(line_str):
            avg_conf = float(np.mean(line_info['confs'])) if line_info['confs'] else 0.0
            results.append({
                "text": line_str,
                "confidence": round(avg_conf, 1)
            })
    return results


def extract_text_lines_with_confidence(image_bytes: bytes) -> list[dict]:
    """
    Extracts high-accuracy text lines along with their per-line confidence scores (0-100%)
    using Tesseract OCR and adaptive computer vision preprocessing.
    
    Returns:
        list[dict]: e.g. [{"text": "MRP Rs. 10/-", "confidence": 94.2}, ...]
    """
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        processed = preprocess_image(pil_image)

        # Primary pass: PSM 3 (Fully automatic page segmentation)
        data_primary = pytesseract.image_to_data(
            processed,
            config=r'--oem 3 --psm 3',
            output_type=pytesseract.Output.DICT
        )
        lines = _parse_image_data_to_lines(data_primary)

        # Fallback pass: if PSM 3 returned few lines, try PSM 11 (Sparse text)
        if len(lines) < 3:
            data_sparse = pytesseract.image_to_data(
                processed,
                config=r'--oem 3 --psm 11',
                output_type=pytesseract.Output.DICT
            )
            sparse_lines = _parse_image_data_to_lines(data_sparse)
            if len(sparse_lines) > len(lines):
                lines = sparse_lines

        # Cleanup memory
        del pil_image, processed
        gc.collect()

        return lines
    except Exception as e:
        print(f"OCR Error: {e}")
        return []


def extract_text_lines_from_image(image_bytes: bytes) -> list[str]:
    """
    Extracts high-accuracy text lines as raw strings (retains full backwards compatibility).
    """
    return [item["text"] for item in extract_text_lines_with_confidence(image_bytes)]


def measure_font_height_mm(image_bytes: bytes, pixels_per_mm: float) -> dict:
    """
    Automatically calculates physical font height (in mm) of packaging text declarations
    using character bounding boxes from Tesseract and the ArUco calibration scale factor.
    
    Pursuant to Legal Metrology Rule 7(2) / Second Schedule, font height is evaluated
    on uppercase letters (A-Z) and numerals (0-9).
    
    Returns:
        dict: {
            "success": bool,
            "measured_font_height_mm": float | None,
            "min_font_height_mm": float | None,
            "characters_sampled": int,
            "message": str
        }
    """
    if not pixels_per_mm or pixels_per_mm <= 0:
        return {
            "success": False,
            "measured_font_height_mm": None,
            "min_font_height_mm": None,
            "characters_sampled": 0,
            "message": "Invalid or missing pixels_per_mm calibration scale."
        }

    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        processed, scale_factor = preprocess_image_with_scale(pil_image)

        # Adjust scale for any resize applied during preprocessing
        effective_ppm = pixels_per_mm * scale_factor

        # Extract character-level bounding boxes: [char, left, bottom, right, top, page_num]
        boxes_raw = pytesseract.image_to_boxes(processed, config=r'--oem 3 --psm 3')
        if not boxes_raw.strip():
            boxes_raw = pytesseract.image_to_boxes(processed, config=r'--oem 3 --psm 11')

        char_entries = [line.split() for line in boxes_raw.splitlines() if len(line.split()) >= 6]

        # Filter for Uppercase letters and Numerals per Legal Metrology standards
        heights_mm = []
        for entry in char_entries:
            char = entry[0]
            if char.isupper() or char.isdigit():
                try:
                    bottom = int(entry[2])
                    top = int(entry[4])
                    h_px = top - bottom
                    h_mm = h_px / effective_ppm
                    # Filter noise outliers (< 0.5 mm specks or giant > 50 mm graphic banners)
                    if 0.5 <= h_mm <= 50.0:
                        heights_mm.append(h_mm)
                except (ValueError, IndexError):
                    continue

        # Cleanup memory
        del pil_image, processed
        gc.collect()

        if not heights_mm or len(heights_mm) < 5:
            return {
                "success": False,
                "measured_font_height_mm": None,
                "min_font_height_mm": None,
                "characters_sampled": len(heights_mm),
                "message": "Insufficient character samples detected for reliable font height measurement."
            }

        median_h = float(np.median(heights_mm))
        p10_h = float(np.percentile(heights_mm, 10))

        return {
            "success": True,
            "measured_font_height_mm": round(median_h, 2),
            "min_font_height_mm": round(p10_h, 2),
            "characters_sampled": len(heights_mm),
            "message": f"Successfully measured from {len(heights_mm)} character samples."
        }
    except Exception as e:
        return {
            "success": False,
            "measured_font_height_mm": None,
            "min_font_height_mm": None,
            "characters_sampled": 0,
            "message": f"Font height measurement error: {str(e)}"
        }