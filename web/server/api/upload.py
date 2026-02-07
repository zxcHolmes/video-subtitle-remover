import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from utils.file_utils import is_allowed_file, generate_task_id, ensure_dir
from services.task_manager import task_manager

router = APIRouter()

UPLOAD_DIR = "/tmp/subtitle-remover/uploads"
ensure_dir(UPLOAD_DIR)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a video or image file
    Returns task_id for tracking
    """
    # Validate file type
    is_valid, error_msg = is_allowed_file(file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Generate task ID
    task_id = generate_task_id()

    # Create task directory
    task_dir = os.path.join(UPLOAD_DIR, task_id)
    ensure_dir(task_dir)

    # Save file
    file_path = os.path.join(task_dir, file.filename)

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # Create task (with file deduplication)
    task = task_manager.create_task(task_id, file_path, file.filename)

    return {
        "task_id": task_id,
        "filename": file.filename,
        "status": task.status.value
    }
