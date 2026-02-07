import cv2
import sys
import os
import json
import requests
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend import config as backend_config

class WhisperTranslationService:
    """
    基于 Whisper 识别结果的翻译服务
    流程：
    1. 读取 Whisper 识别的时间段和文本
    2. 翻译文本
    3. 在指定时间段内渲染翻译后的字幕到视频
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.progress = 0
        self.status = "pending"
        self.error = None

    def batch_translate_segments(
        self,
        segments: List[Dict],
        target_lang: str,
        api_key: str,
        api_base: str,
        model: str
    ) -> List[Dict]:
        """
        批量翻译所有片段（每批最多2000字符）
        segments: [{'id': 0, 'start': 0.0, 'end': 2.5, 'text': '原文'}, ...]
        返回: [{'start': 0.0, 'end': 2.5, 'text': '原文', 'translated': '译文'}, ...]
        """
        print(f"Task {self.task_id}: Starting batch translation for {len(segments, flush=True)} segments to {target_lang}")

        # 按字符数分批
        batches = []
        current_batch = []
        current_length = 0
        MAX_BATCH_LENGTH = 2000

        for segment in segments:
            text = segment['text']
            text_length = len(text)

            # 如果加入当前segment会超过限制，开始新批次
            if current_length + text_length > MAX_BATCH_LENGTH and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_length = 0

            current_batch.append(segment)
            current_length += text_length

        # 添加最后一批
        if current_batch:
            batches.append(current_batch)

        print(f"Task {self.task_id}: Split into {len(batches, flush=True)} batches")

        # 翻译每一批
        all_translated = []
        for batch_idx, batch in enumerate(batches):
            print(f"Task {self.task_id}: ========== Batch {batch_idx + 1}/{len(batches, flush=True)} ==========")
            print(f"Task {self.task_id}: Segments in this batch: {len(batch, flush=True)}")

            # 构造JSON输入
            batch_input = []
            for seg in batch:
                batch_input.append({
                    'id': seg.get('id', seg.get('start')),  # 使用id或start作为标识
                    'text': seg['text']
                })

            print(f"Task {self.task_id}: Batch input JSON: {json.dumps(batch_input, ensure_ascii=False, flush=True)}")

            # 调用翻译API
            translated_batch = self.translate_batch(
                batch_input,
                target_lang,
                api_key,
                api_base,
                model
            )

            # 合并翻译结果
            for seg in batch:
                seg_id = seg.get('id', seg.get('start'))
                # 在翻译结果中找到对应的翻译
                translated_text = seg['text']  # 默认保留原文
                for trans in translated_batch:
                    if trans['id'] == seg_id:
                        translated_text = trans['translated']
                        break

                all_translated.append({
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text'],
                    'translated': translated_text
                })

                print(f"Task {self.task_id}: [{seg_id}] {seg['text']} -> {translated_text}", flush=True)

            # 更新进度 (0-50%)
            self.progress = 50 * (batch_idx + 1) / len(batches)

        print(f"Task {self.task_id}: All batches translated - {len(all_translated, flush=True)} segments total")
        return all_translated

    def translate_batch(
        self,
        batch: List[Dict],
        target_lang: str,
        api_key: str,
        api_base: str,
        model: str
    ) -> List[Dict]:
        """
        翻译一批segments
        输入: [{'id': 0, 'text': '原文'}, ...]
        输出: [{'id': 0, 'translated': '译文'}, ...]
        """
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # 构造prompt - 要求返回JSON格式
            prompt = f"""请将以下JSON数组中的所有文本翻译成{target_lang}。

输入JSON数组：
{json.dumps(batch, ensure_ascii=False)}

要求：
1. 保持原有的id
2. 只翻译text字段的内容
3. 返回JSON对象格式：{{"translations": [{{"id": 0, "translated": "翻译结果"}}, {{"id": 1, "translated": "翻译结果"}}, ...]}}"""

            data = {
                'model': model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'response_format': {'type': 'json_object'}  # OpenAI standard
            }

            print(f"Task {self.task_id}: Sending batch translation request with response_format=json_object", flush=True)
            print(f"Task {self.task_id}: API: {api_base}/v1/chat/completions", flush=True)
            print(f"Task {self.task_id}: Model: {model}", flush=True)

            response = requests.post(
                f"{api_base}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60  # 批量翻译可能需要更长时间
            )

            print(f"Task {self.task_id}: API response status: {response.status_code}", flush=True)

            if response.status_code == 200:
                result = response.json()
                response_text = result['choices'][0]['message']['content'].strip()

                print(f"Task {self.task_id}: API response: {response_text}", flush=True)

                # 解析JSON响应 - OpenAI response_format 保证返回 JSON object
                try:
                    response_data = json.loads(response_text)

                    # 期望格式: {"translations": [...]}
                    if 'translations' in response_data:
                        translated_batch = response_data['translations']
                    else:
                        print(f"Task {self.task_id}: Missing 'translations' key in response", flush=True)
                        print(f"Task {self.task_id}: Response keys: {list(response_data.keys(, flush=True))}")
                        # 返回原文
                        return [{'id': item['id'], 'translated': item['text']} for item in batch]

                    print(f"Task {self.task_id}: Successfully parsed {len(translated_batch, flush=True)} translations")
                    return translated_batch

                except json.JSONDecodeError as e:
                    print(f"Task {self.task_id}: Failed to parse JSON response: {e}", flush=True)
                    print(f"Task {self.task_id}: Response text: {response_text}", flush=True)
                    # 返回原文
                    return [{'id': item['id'], 'translated': item['text']} for item in batch]
            else:
                print(f"Task {self.task_id}: ========== Translation API Error ==========", flush=True)
                print(f"Task {self.task_id}: Status code: {response.status_code}", flush=True)
                print(f"Task {self.task_id}: Response: {response.text}", flush=True)
                print(f"Task {self.task_id}: =========================================", flush=True)
                # 返回原文
                return [{'id': item['id'], 'translated': item['text']} for item in batch]

        except Exception as e:
            print(f"Task {self.task_id}: ========== Batch Translation Exception ==========", flush=True)
            print(f"Batch translation failed for task {self.task_id}", flush=True); import traceback; traceback.print_exc()
            print(f"Task {self.task_id}: ================================================", flush=True)
            # 返回原文
            return [{'id': item['id'], 'translated': item['text']} for item in batch]

    def render_subtitle_on_frame(
        self,
        frame: np.ndarray,
        text: str,
        subtitle_region: Tuple[int, int, int, int],
        bg_color: str = 'black',
        font_size: int = 28
    ) -> np.ndarray:
        """
        在帧上渲染字幕（添加在下方，不覆盖原字幕）
        subtitle_region: (ymin, ymax, xmin, xmax)
        """
        ymin, ymax, xmin, xmax = subtitle_region
        height, width = frame.shape[:2]

        # 转换为 PIL Image
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)

        # 绘制半透明背景（让原视频内容可见，但字幕清晰）
        bg_rgb = (0, 0, 0, 180) if bg_color == 'black' else (255, 255, 255, 180)
        overlay = Image.new('RGBA', img_pil.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([xmin, ymin, xmax, ymax], fill=bg_rgb)
        img_pil = img_pil.convert('RGBA')
        img_pil = Image.alpha_composite(img_pil, overlay)
        draw = ImageDraw.Draw(img_pil)

        # 加载中文字体
        try:
            # 尝试加载系统字体
            if sys.platform == 'darwin':  # macOS
                font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', font_size)
            elif sys.platform == 'win32':  # Windows
                font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', font_size)
            else:  # Linux
                font = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', font_size)
        except:
            # 使用默认字体
            font = ImageFont.load_default()

        # 计算文本位置（居中）
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # 旧版本 PIL
            text_width, text_height = draw.textsize(text, font=font)

        text_x = xmin + (xmax - xmin - text_width) // 2
        text_y = ymin + (ymax - ymin - text_height) // 2

        # 绘制文本
        text_color = (255, 255, 255) if bg_color == 'black' else (0, 0, 0)
        draw.text((text_x, text_y), text, font=font, fill=text_color)

        # 转回 OpenCV 格式
        frame_with_subtitle = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        return frame_with_subtitle

    def process_video_with_translations(
        self,
        video_path: str,
        translated_segments: List[Dict],
        subtitle_region: Tuple[int, int, int, int],
        output_path: str,
        bg_color: str = 'black'
    ) -> str:
        """
        处理视频，在指定时间段渲染翻译字幕
        """
        print(f"Task {self.task_id}: ========== Starting Video Rendering ==========", flush=True)
        print(f"Task {self.task_id}: Input video: {video_path}", flush=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            error_msg = f"Failed to open video file: {video_path}"
            print(f"Task {self.task_id}: {error_msg}", flush=True)
            raise RuntimeError(error_msg)

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"Task {self.task_id}: Video info - FPS: {fps}, Resolution: {width}x{height}, Total frames: {total_frames}", flush=True)
        print(f"Task {self.task_id}: Subtitle region: {subtitle_region}", flush=True)
        print(f"Task {self.task_id}: Segments to render: {len(translated_segments, flush=True)}")

        # 创建临时输出文件
        temp_output = output_path.replace('.mp4', '_temp.mp4')
        print(f"Task {self.task_id}: Temp output: {temp_output}", flush=True)

        # 使用 mp4v 编码器（跨平台兼容）
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

        if not out.isOpened():
            error_msg = f"Failed to create VideoWriter for: {temp_output}"
            print(f"Task {self.task_id}: {error_msg}", flush=True)
            raise RuntimeError(error_msg)

        print(f"Task {self.task_id}: VideoWriter created successfully", flush=True)

        # 创建时间段到字幕的映射
        print(f"Task {self.task_id}: Creating frame-to-subtitle mapping", flush=True)

        time_to_subtitle = {}
        for i, segment in enumerate(translated_segments):
            start_frame = int(segment['start'] * fps)
            end_frame = int(segment['end'] * fps)
            frame_count = end_frame - start_frame + 1

            print(f"Task {self.task_id}: Segment {i}: frames {start_frame}-{end_frame} ({frame_count} frames, flush=True) -> '{segment['translated']}'")

            for frame_no in range(start_frame, end_frame + 1):
                time_to_subtitle[frame_no] = segment['translated']

        print(f"Task {self.task_id}: Mapped {len(time_to_subtitle, flush=True)} frames with subtitles")

        # 处理每一帧
        print(f"Task {self.task_id}: Starting frame-by-frame rendering", flush=True)

        frame_no = 0
        subtitle_frame_count = 0
        last_log_percent = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 检查当前帧是否需要渲染字幕
            if frame_no in time_to_subtitle:
                subtitle_text = time_to_subtitle[frame_no]
                frame = self.render_subtitle_on_frame(
                    frame,
                    subtitle_text,
                    subtitle_region,
                    bg_color
                )
                subtitle_frame_count += 1

            out.write(frame)
            frame_no += 1

            # 更新进度 (50-100%)
            self.progress = 50 + 50 * frame_no / total_frames

            # 每10%打印一次进度
            current_percent = int(self.progress - 50)  # 0-50范围
            if current_percent >= last_log_percent + 10:
                print(f"Task {self.task_id}: Rendering progress {frame_no}/{total_frames} frames ({self.progress:.1f}%, flush=True), subtitles rendered: {subtitle_frame_count}")
                last_log_percent = current_percent

        cap.release()
        out.release()

        print(f"Task {self.task_id}: Frame rendering completed", flush=True)
        print(f"Task {self.task_id}: Total frames processed: {frame_no}", flush=True)
        print(f"Task {self.task_id}: Frames with subtitles: {subtitle_frame_count}", flush=True)
        print(f"Task {self.task_id}: Starting FFmpeg re-encoding", flush=True)

        # 使用 FFmpeg 重新编码（高质量 + 音频）
        import subprocess

        ffmpeg_cmd = [
            backend_config.FFMPEG_PATH,
            '-i', temp_output,
            '-i', video_path,  # 原视频（用于提取音频）
            '-map', '0:v:0',   # 使用处理后的视频流
            '-map', '1:a:0?',  # 使用原视频的音频流（如果有）
            '-c:v', 'libx264',
            '-crf', '18',
            '-preset', 'slow',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-y',
            output_path
        ]

        print(f"Task {self.task_id}: FFmpeg command: {' '.join(ffmpeg_cmd, flush=True)}")

        try:
            result = subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            print(f"Task {self.task_id}: FFmpeg encoding completed successfully", flush=True)

            if result.stdout:
                print(f"Task {self.task_id}: FFmpeg stdout: {result.stdout.decode(, flush=True)}")

            # 检查输出文件
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                print(f"Task {self.task_id}: Final output file: {output_path} ({output_size:.2f} MB, flush=True)")
            else:
                print(f"Task {self.task_id}: FFmpeg succeeded but output file does not exist!", flush=True)

        except subprocess.CalledProcessError as e:
            print(f"Task {self.task_id}: ========== FFmpeg Failed ==========", flush=True)
            print(f"Task {self.task_id}: Return code: {e.returncode}", flush=True)
            print(f"Task {self.task_id}: stderr: {e.stderr.decode(, flush=True)}")
            if e.stdout:
                print(f"Task {self.task_id}: stdout: {e.stdout.decode(, flush=True)}")
            print(f"Task {self.task_id}: ===================================", flush=True)

            # 如果 FFmpeg 失败，使用临时文件作为输出
            print(f"Task {self.task_id}: Falling back to temp file", flush=True)
            import shutil
            shutil.move(temp_output, output_path)
            print(f"Task {self.task_id}: Moved {temp_output} -> {output_path}", flush=True)
        else:
            # 删除临时文件
            if os.path.exists(temp_output):
                os.remove(temp_output)
                print(f"Task {self.task_id}: Removed temp file: {temp_output}", flush=True)

        return output_path

    def translate_and_render(
        self,
        video_path: str,
        whisper_result_path: str,
        output_path: str,
        api_key: str,
        api_base: str,
        model: str,
        target_lang: str,
        bg_color: str = 'black'
    ) -> str:
        """
        完整流程：翻译 + 渲染
        """
        try:
            self.status = "processing"
            self.progress = 0

            print(f"Task {self.task_id}: Starting translation and rendering", flush=True)

            # 读取 Whisper 识别结果
            print(f"Task {self.task_id}: Loading Whisper result from {whisper_result_path}", flush=True)

            with open(whisper_result_path, 'r', encoding='utf-8') as f:
                whisper_result = json.load(f)

            subtitle_region = whisper_result.get('subtitle_region')
            segments = whisper_result.get('segments', [])

            print(f"Task {self.task_id}: Loaded {len(segments, flush=True)} segments, region={subtitle_region}")

            if not subtitle_region:
                error_msg = "No subtitle region found in Whisper result"
                print(f"Task {self.task_id}: {error_msg}", flush=True)
                raise ValueError(error_msg)

            if not segments:
                error_msg = "No subtitle segments found in Whisper result"
                print(f"Task {self.task_id}: {error_msg}", flush=True)
                raise ValueError(error_msg)

            # 步骤1: 翻译所有片段
            print(f"Task {self.task_id}: Step 1 - Translating {len(segments, flush=True)} segments")

            translated_segments = self.batch_translate_segments(
                segments,
                target_lang,
                api_key,
                api_base,
                model
            )

            print(f"Task {self.task_id}: Step 1 completed - {len(translated_segments, flush=True)} segments translated")

            # 步骤2: 渲染到视频
            print(f"Task {self.task_id}: Step 2 - Rendering to video", flush=True)

            output_file = self.process_video_with_translations(
                video_path,
                translated_segments,
                subtitle_region,
                output_path,
                bg_color
            )

            self.status = "completed"
            self.progress = 100

            print(f"Task {self.task_id}: ========== Translation & Rendering Summary ==========", flush=True)
            print(f"Task {self.task_id}: Input video: {video_path}", flush=True)
            print(f"Task {self.task_id}: Output video: {output_file}", flush=True)
            print(f"Task {self.task_id}: Segments translated: {len(translated_segments, flush=True)}")
            print(f"Task {self.task_id}: Target language: {target_lang}", flush=True)
            print(f"Task {self.task_id}: Subtitle region: {subtitle_region}", flush=True)

            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
                print(f"Task {self.task_id}: Output file size: {file_size:.2f} MB", flush=True)
            else:
                print(f"Task {self.task_id}: Output file does not exist!", flush=True)

            print(f"Task {self.task_id}: =====================================================", flush=True)

            return output_file

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            print(f"Task {self.task_id}: ========== Translation & Rendering Failed ==========", flush=True)
            print(f"Translation and rendering failed for task {self.task_id}", flush=True); import traceback; traceback.print_exc()
            print(f"Task {self.task_id}: ====================================================", flush=True)
            raise e

    def get_progress(self) -> dict:
        """获取处理进度"""
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.error if self.error else f"正在处理... {self.progress:.1f}%"
        }
