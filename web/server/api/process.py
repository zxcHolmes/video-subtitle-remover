from fastapi import APIRouter, HTTPException
from models.task import ProcessConfig, TaskStatus
from services.task_manager import task_manager
from services.subtitle_service import SubtitleRemovalService
from utils.exceptions import TaskNotFoundException

router = APIRouter()


@router.post("/process")
async def start_processing(config: ProcessConfig):
    """
    Start processing a video
    """
    try:
        # Get task
        task = task_manager.get_task(config.task_id)

        if task.status != TaskStatus.UPLOADED:
            raise HTTPException(
                status_code=400,
                detail=f"任务状态不正确: {task.status}"
            )

        # Create service
        service = SubtitleRemovalService(config.task_id)

        # Convert sub_area to tuple if provided
        sub_area = tuple(config.sub_area) if config.sub_area else None

        # Start processing
        service.process(
            video_path=task.file_path,
            sub_area=sub_area,
            mode=config.mode,
            skip_detection=config.skip_detection
        )

        # Register service
        task_manager.register_service(config.task_id, service)

        # Update task status
        task_manager.update_task(
            config.task_id,
            status=TaskStatus.PROCESSING
        )

        return {
            "task_id": config.task_id,
            "status": "started",
            "message": "开始处理"
        }

    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动处理失败: {str(e)}")
