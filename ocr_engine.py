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



def preprocess_image(pil_img: Image.Image) -> np.ndarray:
    """
    Applies adaptive contrast enhancement and noise reduction
    without creating destructive high-frequency artifacts.
    """
    # 1. Correct smartphone EXIF orientation
    pil_img = ImageOps.exif_transpose(pil_img)

    # 2. Convert to RGB numpy array
    rgb_img = np.array(pil_img.convert("RGB"))

    # 3. Resize if image is too large or too small
    h, w = rgb_img.shape[:2]
    max_dim = max(h, w)
    min_dim = min(h, w)

    if max_dim > 2000:
        scale = 2000.0 / float(max_dim)
        rgb_img = cv2.resize(rgb_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    elif min_dim < 600:
        scale = 600.0 / float(min_dim)
        rgb_img = cv2.resize(rgb_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # 4. Convert to Grayscale
    gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)

    # 5. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for even lighting
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 6. Gentle bilateral filtering to smooth background noise while keeping text edges crisp
    smoothed = cv2.bilateralFilter(enhanced, d=5, sigmaColor=50, sigmaSpace=50)

    return smoothed


def _is_meaningful_line(line: str) -> bool:
    """Filters out pure noise lines containing mostly non-alphanumeric artifacts."""
    cleaned = line.strip()
    if not cleaned or len(cleaned) < 2:
        return False
    alnum_count = sum(1 for c in cleaned if c.isalnum())
    # Require at least 2 alphanumeric characters and at least 35% alphanumeric content
    return alnum_count >= 2 and (alnum_count / len(cleaned)) >= 0.35


def extract_text_lines_from_image(image_bytes: bytes) -> list[str]:
    """
    Extracts high-accuracy text lines using Tesseract OCR with adaptive preprocessing.
    """
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        processed = preprocess_image(pil_image)

        # Primary pass: PSM 3 (Fully automatic page segmentation)
        raw_text = pytesseract.image_to_string(processed, config=r'--oem 3 --psm 3')

        # Fallback pass: if PSM 3 returned few lines, try PSM 11 (Sparse text)
        lines = [line.strip() for line in raw_text.splitlines() if _is_meaningful_line(line)]
        if len(lines) < 3:
            raw_text_sparse = pytesseract.image_to_string(processed, config=r'--oem 3 --psm 11')
            sparse_lines = [line.strip() for line in raw_text_sparse.splitlines() if _is_meaningful_line(line)]
            if len(sparse_lines) > len(lines):
                lines = sparse_lines

        # Cleanup memory
        del pil_image, processed
        gc.collect()

        return lines
    except Exception as e:
        print(f"OCR Error: {e}")
        return []