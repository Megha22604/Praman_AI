import easyocr
import numpy as np
from PIL import Image
import io

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'], gpu=False)

def extract_text_lines_from_image(image_bytes: bytes) -> list[str]:
    """
    Takes raw image bytes, converts them to a numpy array, 
    and returns a list of detected text strings.
    """
    # 1. Load image from bytes via PIL and convert to RGB
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # 2. Convert PIL Image to a NumPy array for EasyOCR
    image_np = np.array(pil_image)
    
    # 3. Run OCR inference
    detected_lines = reader.readtext(image_np, detail=0)
    
    return [str(line).strip() for line in detected_lines if str(line).strip()]