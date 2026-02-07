import os
import sys
import json
import threading
from fastapi import APIRouter, HTTPException
from models.task import TranslationConfig, TaskStatus
from services.task_manager import task_manager
from services.translation_service import SubtitleTranslationService
from services.whisper_translation_service import WhisperTranslationService
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
        print(f"Task {config.task_id}: Getting task info", flush=True)
        task = task_manager.get_task(config.task_id)
        print(f"Task {config.task_id}: Current status={task.status}", flush=True)

        # 允许在 UPLOADED（检测完成后）或 COMPLETED（重新翻译）状态下启动翻译
        if task.status not in [TaskStatus.UPLOADED, TaskStatus.COMPLETED]:
            print(f"Task {config.task_id}: Invalid status for translation - expected UPLOADED or COMPLETED, got {task.status}", flush=True)
            raise HTTPException(
                status_code=400,
                detail=f"任务状态不正确: {task.status}，只能在检测完成或已完成状态下启动翻译"
            )

        # 检查是否有确认的字幕数据（或 Whisper 检测结果）
        confirmed_path = os.path.join(
            os.path.dirname(task.file_path),
            f"{config.task_id}_confirmed.json"
        )

        detected_path = os.path.join(
            os.path.dirname(task.file_path),
            f"{config.task_id}_detected.json"
        )

        print(f"Task {config.task_id}: Checking detection files", flush=True)
        print(f"Task {config.task_id}: confirmed_path={confirmed_path}, exists={os.path.exists(confirmed_path, flush=True)}")
        print(f"Task {config.task_id}: detected_path={detected_path}, exists={os.path.exists(detected_path, flush=True)}")

        # 判断使用哪种翻译方式
        use_whisper = False
        if os.path.exists(detected_path):
            with open(detected_path, 'r', encoding='utf-8') as f:
                detected_data = json.load(f)
                if detected_data.get('method') == 'whisper':
                    use_whisper = True
                    print(f"Task {config.task_id}: Detected Whisper method", flush=True)

        if not os.path.exists(confirmed_path) and not (use_whisper and os.path.exists(detected_path)):
            print(f"Task {config.task_id}: Missing required detection/confirmation files", flush=True)
            raise HTTPException(
                status_code=400,
                detail="请先完成字幕检测和确认"
            )

        # 根据检测方式创建对应的翻译服务
        if use_whisper:
            print(f"Task {config.task_id}: Using Whisper translation service", flush=True)
            service = WhisperTranslationService(task_id=config.task_id)
        else:
            print(f"Task {config.task_id}: Using OCR translation service", flush=True)
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
                print(f"Task {config.task_id}: Translation thread started", flush=True)
                print(f"Task {config.task_id}: Method={'Whisper' if use_whisper else 'OCR'}", flush=True)
                print(f"Task {config.task_id}: Input={input_path}", flush=True)
                print(f"Task {config.task_id}: Output={output_path}", flush=True)

                if use_whisper:
                    # Whisper 翻译流程
                    print(f"Task {config.task_id}: Calling Whisper translate_and_render", flush=True)

                    service.translate_and_render(
                        video_path=input_path,
                        whisper_result_path=detected_path,
                        output_path=output_path,
                        api_key=config.api_key,
                        api_base=config.api_base,
                        model=config.model,
                        target_lang=config.target_lang,
                        bg_color=config.bg_color
                    )
                else:
                    # OCR 翻译流程
                    print(f"Task {config.task_id}: Calling OCR process_video", flush=True)
                    service.process_video(
                        video_path=input_path,
                        output_path=output_path,
                        sub_area=sub_area,
                        bg_color=config.bg_color
                    )

                # 更新任务状态
                print(f"Task {config.task_id}: ========== Translation Completed Successfully ==========", flush=True)
                print(f"Task {config.task_id}: Method: {'Whisper' if use_whisper else 'OCR'}", flush=True)
                print(f"Task {config.task_id}: Input file: {input_path}", flush=True)
                print(f"Task {config.task_id}: Output file: {output_path}", flush=True)

                # 检查输出文件
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                    print(f"Task {config.task_id}: Output file size: {file_size:.2f} MB", flush=True)
                else:
                    print(f"Task {config.task_id}: Output file does not exist!", flush=True)

                print(f"Task {config.task_id}: =======================================================", flush=True)

                task_manager.update_task(
                    config.task_id,
                    status=TaskStatus.COMPLETED,
                    output_path=output_path
                )
            except Exception as e:
                print(f"Task {config.task_id}: ========== Translation Failed ==========", flush=True)
                print(f"Task {config.task_id}: Method: {'Whisper' if use_whisper else 'OCR'}", flush=True)
                print(f"Task {config.task_id}: Input file: {input_path}", flush=True)
                print(f"Task {config.task_id}: Expected output: {output_path}", flush=True)
                print(f"Translation thread failed for task {config.task_id}", flush=True); import traceback; traceback.print_exc()
                print(f"Task {config.task_id}: =========================================", flush=True)

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
        print(f"Task {config.task_id}: Task not found", flush=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Failed to start translation for task {config.task_id}", flush=True); import traceback; traceback.print_exc()
        error_detail = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
        raise HTTPException(status_code=500, detail=f"启动翻译失败: {error_detail}")
