import os
import threading
import json
from fastapi import APIRouter, HTTPException
from models.task import TaskStatus
from services.task_manager import task_manager
from services.subtitle_detect_service import SubtitleDetectService
from utils.exceptions import TaskNotFoundException

router = APIRouter()


@router.post("/detect")
async def detect_subtitles(request: dict):
    """
    检测视频中的字幕（阶段1）
    返回识别结果供用户确认
    """
    try:
        task_id = request.get('task_id')
        sub_area = request.get('sub_area')

        if not task_id:
            raise HTTPException(status_code=400, detail="缺少 task_id")

        # 获取任务
        task = task_manager.get_task(task_id)

        if task.status != TaskStatus.UPLOADED:
            raise HTTPException(
                status_code=400,
                detail=f"任务状态不正确: {task.status}"
            )

        # 创建检测服务
        service = SubtitleDetectService(task_id=task_id)

        # 转换 sub_area
        sub_area_tuple = tuple(sub_area) if sub_area else None

        # 在独立线程中检测
        def detect_thread():
            try:
                result = service.detect_and_recognize(
                    video_path=task.file_path,
                    sub_area=sub_area_tuple
                )

                # 保存检测结果
                result_path = os.path.join(
                    os.path.dirname(task.file_path),
                    f"{task_id}_detected.json"
                )

                with open(result_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                # 更新任务
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.UPLOADED,  # 保持为 UPLOADED，等待用户确认
                    message="字幕检测完成，等待确认"
                )

            except Exception as e:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.ERROR,
                    message=f"检测失败: {str(e)}"
                )

        thread = threading.Thread(target=detect_thread, daemon=True)
        thread.start()

        # 注册服务
        task_manager.register_service(task_id, service)

        # 更新任务状态
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            message="正在检测字幕..."
        )

        return {
            "task_id": task_id,
            "status": "started",
            "message": "开始检测字幕"
        }

    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动检测失败: {str(e)}")


@router.get("/detect/{task_id}")
async def get_detection_result(task_id: str):
    """
    获取字幕检测结果
    """
    try:
        task = task_manager.get_task(task_id)

        # 检查任务状态
        if task.status == TaskStatus.ERROR:
            return {
                "task_id": task_id,
                "status": "error",
                "message": task.message or "检测失败"
            }

        # 检查检测结果文件
        result_path = os.path.join(
            os.path.dirname(task.file_path),
            f"{task_id}_detected.json"
        )

        if not os.path.exists(result_path):
            # 获取服务进度
            service = task_manager.get_service(task_id)
            if service:
                progress_info = service.get_progress()
                return {
                    "task_id": task_id,
                    "status": "detecting",
                    "message": progress_info.get('message', '正在检测中...'),
                    "progress": progress_info.get('progress', 0)
                }
            else:
                return {
                    "task_id": task_id,
                    "status": "detecting",
                    "message": "正在检测中..."
                }

        # 读取结果
        with open(result_path, 'r', encoding='utf-8') as f:
            result = json.load(f)

        return {
            "task_id": task_id,
            "status": "completed",
            "subtitles": result['subtitles'],
            "total_frames": result['total_frames'],
            "subtitle_count": result['subtitle_count'],
            "unique_count": result['unique_count']
        }

    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取检测结果失败: {str(e)}")


@router.post("/detect/confirm")
async def confirm_detection(request: dict):
    """
    用户确认检测结果
    可以选择性删除某些误识别的字幕
    """
    try:
        task_id = request.get('task_id')
        confirmed_subtitles = request.get('confirmed_subtitles', [])

        if not task_id:
            raise HTTPException(status_code=400, detail="缺少 task_id")

        task = task_manager.get_task(task_id)

        # 保存确认后的字幕
        confirmed_path = os.path.join(
            os.path.dirname(task.file_path),
            f"{task_id}_confirmed.json"
        )

        with open(confirmed_path, 'w', encoding='utf-8') as f:
            json.dump({
                'subtitles': confirmed_subtitles,
                'confirmed_at': 'user_confirmed'
            }, f, ensure_ascii=False, indent=2)

        return {
            "task_id": task_id,
            "status": "confirmed",
            "message": f"已确认 {len(confirmed_subtitles)} 条字幕"
        }

    except TaskNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认失败: {str(e)}")
