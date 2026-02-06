from fastapi import APIRouter, HTTPException
from services.task_manager import task_manager
from utils.exceptions import TaskNotFoundException

router = APIRouter()


@router.get("/status/{task_id}")
async def get_status(task_id: str):
    """
    Get task status and progress
    """
    try:
        progress = await task_manager.get_progress(task_id)
        return progress
    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")
