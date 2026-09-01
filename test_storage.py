"""
Standalone Test Suite for Supabase Storage Integration (Step 5 / Task 3B)
Reads a local package-label image and uploads it to the 'scan-images' bucket.
Does NOT modify database records or app.py.
"""

import os
import sys
from storage import upload_image, SUPABASE_URL

def test_supabase_storage_upload():
    print("Testing Supabase Storage Integration...")

    # 1. Verify Client Initialization
    if not SUPABASE_URL:
        print("Storage connection: FAIL")
        sys.exit(1)
    print("Storage connection: PASS")

    # 2. Locate local test image
    image_filename = "test_label_food.png"
    image_path = os.path.join(os.getcwd(), image_filename)

    if not os.path.exists(image_path):
        print(f"Image read: FAIL (File {image_filename} not found)")
        sys.exit(1)

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        print("Image read: PASS")
    except Exception as e:
        print(f"Image read: FAIL ({e})")
        sys.exit(1)

    # 3. Target Storage Path & Upload
    target_storage_path = "test/backend-upload-test.png"
    content_type = "image/png"

    try:
        res = upload_image(
            image_bytes=image_bytes,
            storage_path=target_storage_path,
            content_type=content_type
        )
        print("Upload: PASS")
        print("Bucket: scan-images")
        print(f"Path: {target_storage_path}")
        print("\n[OK] STANDALONE STORAGE TEST PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"Upload: FAIL ({e})")
        sys.exit(1)

if __name__ == "__main__":
    test_supabase_storage_upload()
