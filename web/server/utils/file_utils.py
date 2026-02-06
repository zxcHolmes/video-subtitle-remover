import os
import uuid
from typing import Tuple


ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}


def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase"""
    return os.path.splitext(filename)[1].lower()


def is_allowed_file(filename: str) -> Tuple[bool, str]:
    """
    Check if file is allowed
    Returns: (is_allowed, error_message)
    """
    ext = get_file_extension(filename)

    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return True, ""
    elif ext in ALLOWED_IMAGE_EXTENSIONS:
        return True, ""
    else:
        return False, f"不支持的文件格式: {ext}"


def generate_task_id() -> str:
    """Generate unique task ID"""
    return str(uuid.uuid4())


def ensure_dir(path: str):
    """Create directory if not exists"""
    os.makedirs(path, exist_ok=True)
