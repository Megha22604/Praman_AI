"""
PramanAI Supabase Storage Integration Module (Step 5)
Provides standalone storage upload functions to interact with Supabase Storage buckets.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment variables.")

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def upload_image(image_bytes: bytes, storage_path: str, content_type: str = "image/jpeg"):
    """
    Uploads raw image binary bytes to the 'scan-images' Supabase Storage bucket.
    
    Parameters:
        image_bytes (bytes): Binary payload of the image.
        storage_path (str): Target path in the bucket (e.g. 'test/backend-upload-test.jpg').
        content_type (str): MIME type of the file (e.g. 'image/jpeg' or 'image/png').
        
    Returns:
        Storage API response object or path string.
    """
    bucket_name = "scan-images"
    try:
        response = supabase.storage.from_(bucket_name).upload(
            file=image_bytes,
            path=storage_path,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to upload image to Supabase Storage: {e}") from e


def delete_image(storage_path: str):
    """
    Deletes an object from the 'scan-images' Supabase Storage bucket by storage_path.
    Used for cleanup if a database transaction fails after storage upload.
    """
    bucket_name = "scan-images"
    try:
        response = supabase.storage.from_(bucket_name).remove([storage_path])
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to delete image from Supabase Storage ({storage_path}): {e}") from e
