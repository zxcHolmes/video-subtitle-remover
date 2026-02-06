import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.task_manager import task_manager
from utils.exceptions import TaskNotFoundException
from models.task import TaskStatus

router = APIRouter()


@router.get("/download/{task_id}")
async def download_result(task_id: str):
    """
    Download processed video
    """
    try:
        task = task_manager.get_task(task_id)

        if task.status != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"任务未完成: {task.status}"
            )

        if not task.output_path or not os.path.exists(task.output_path):
            raise HTTPException(
                status_code=404,
                detail="输出文件不存在"
            )

        filename = os.path.basename(task.output_path)

        return FileResponse(
            path=task.output_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")
