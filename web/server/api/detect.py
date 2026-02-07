import os
import sys
import threading
import json
from fastapi import APIRouter, HTTPException
from models.task import TaskStatus
from services.task_manager import task_manager
from services.subtitle_detect_service import SubtitleDetectService
from services.whisper_subtitle_service import WhisperSubtitleService
from utils.exceptions import TaskNotFoundException

router = APIRouter()


@router.post("/detect")
async def detect_subtitles(request: dict):
    """
    检测视频中的字幕（阶段1）
    支持两种方式：
    1. OCR: PaddleOCR 逐帧识别
    2. Whisper: Faster Whisper 语音识别
    """
    try:
        task_id = request.get('task_id')
        sub_area = request.get('sub_area')
        detection_method = request.get('detection_method', 'ocr')  # 'ocr' or 'whisper'

        if not task_id:
            raise HTTPException(status_code=400, detail="缺少 task_id")

        # 获取任务
        task = task_manager.get_task(task_id)

        if task.status != TaskStatus.UPLOADED:
            raise HTTPException(
                status_code=400,
                detail=f"任务状态不正确: {task.status}"
            )

        # 根据检测方式创建服务
        if detection_method == 'whisper':
            service = WhisperSubtitleService(task_id=task_id)
            print(f"[API] Using Whisper for subtitle detection")
        else:
            service = SubtitleDetectService(task_id=task_id)
            print(f"[API] Using OCR for subtitle detection")

        # 转换 sub_area
        sub_area_tuple = tuple(sub_area) if sub_area else None

        # 在独立线程中检测
        def detect_thread():
            try:
                print(f"\n[Detection Thread] Starting for task {task_id}")
                print(f"[Detection Thread] Method: {detection_method}")
                print(f"[Detection Thread] Video: {task.file_path}")
                print(f"[Detection Thread] Sub area: {sub_area_tuple}")
                sys.stdout.flush()

                if detection_method == 'whisper':
                    print(f"[Detection Thread] Calling Whisper detect_and_transcribe...")
                    sys.stdout.flush()

                    result = service.detect_and_transcribe(
                        video_path=task.file_path,
                        sub_area=sub_area_tuple
                    )
                else:
                    print(f"[Detection Thread] Calling OCR detect_and_recognize...")
                    sys.stdout.flush()

                    result = service.detect_and_recognize(
                        video_path=task.file_path,
                        sub_area=sub_area_tuple
                    )

                # 保存检测结果
                result_path = os.path.join(
                    os.path.dirname(task.file_path),
                    f"{task_id}_detected.json"
                )

                print(f"[Detection Thread] Saving result to: {result_path}")
                sys.stdout.flush()

                with open(result_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                print(f"[Detection Thread] Result saved successfully")
                sys.stdout.flush()

                # 如果是 Whisper 方式，自动确认（不需要用户手动确认）
                if detection_method == 'whisper':
                    confirmed_path = os.path.join(
                        os.path.dirname(task.file_path),
                        f"{task_id}_confirmed.json"
                    )
                    with open(confirmed_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            'method': 'whisper',
                            'auto_confirmed': True
                        }, f, ensure_ascii=False, indent=2)

                # 更新任务
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.UPLOADED,  # 保持为 UPLOADED，等待用户确认
                    message="字幕检测完成，等待确认"
                )

            except Exception as e:
                # 打印完整的错误堆栈到控制台
                import traceback
                print(f"\n{'='*60}")
                print(f"ERROR in detection thread for task {task_id}:")
                print(f"{'='*60}")
                traceback.print_exc()
                print(f"{'='*60}\n")

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
