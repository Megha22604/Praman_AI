import io
import gc
import numpy as np
from PIL import Image

_reader = None

def get_reader():
    """Lazy load EasyOCR reader only when requested to save RAM."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False, model_storage_directory='/tmp/easyocr_models')
    return _reader

def extract_text_lines_from_image(image_bytes: bytes) -> list[str]:
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image_np = np.array(pil_image)
    
    reader = get_reader()
    detected_lines = reader.readtext(image_np, detail=0)
    
    # Free temporary memory
    del pil_image, image_np
    gc.collect()
    
    return [str(line).strip() for line in detected_lines if str(line).strip()]