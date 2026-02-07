import os
import threading
from fastapi import APIRouter, HTTPException
from models.task import TranslationConfig, TaskStatus
from services.task_manager import task_manager
from services.translation_service import SubtitleTranslationService
from utils.exceptions import TaskNotFoundException

router = APIRouter()


@router.post("/translate")
async def start_translation(config: TranslationConfig):
    """
    启动字幕翻译（阶段2）
    需要先完成字幕检测和用户确认
    """
    try:
        # 获取任务
        task = task_manager.get_task(config.task_id)

        if task.status != TaskStatus.UPLOADED:
            raise HTTPException(
                status_code=400,
                detail=f"任务状态不正确: {task.status}"
            )

        # 检查是否有确认的字幕数据
        confirmed_path = os.path.join(
            os.path.dirname(task.file_path),
            f"{config.task_id}_confirmed.json"
        )

        if not os.path.exists(confirmed_path):
            raise HTTPException(
                status_code=400,
                detail="请先完成字幕检测和确认"
            )

        # 创建翻译服务
        service = SubtitleTranslationService(
            task_id=config.task_id,
            api_key=config.api_key,
            api_base=config.api_base,
            model=config.model,
            target_lang=config.target_lang
        )

        # 转换 sub_area
        sub_area = tuple(config.sub_area) if config.sub_area else None

        # 输出路径
        input_path = task.file_path
        output_dir = os.path.dirname(input_path)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        output_path = os.path.join(output_dir, f"{name}_translated{ext}")

        # 在独立线程中处理
        def process_thread():
            try:
                service.process_video(
                    video_path=input_path,
                    output_path=output_path,
                    sub_area=sub_area,
                    bg_color=config.bg_color
                )
                # 更新任务状态
                task_manager.update_task(
                    config.task_id,
                    status=TaskStatus.COMPLETED,
                    output_path=output_path
                )
            except Exception as e:
                task_manager.update_task(
                    config.task_id,
                    status=TaskStatus.ERROR,
                    message=str(e)
                )

        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()

        # 注册服务
        task_manager.register_service(config.task_id, service)

        # 更新任务状态
        task_manager.update_task(
            config.task_id,
            status=TaskStatus.PROCESSING
        )

        return {
            "task_id": config.task_id,
            "status": "started",
            "message": "开始翻译字幕"
        }

    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动翻译失败: {str(e)}")
