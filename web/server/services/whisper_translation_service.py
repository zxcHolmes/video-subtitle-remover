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

    def translate_text(
        self,
        text: str,
        target_lang: str,
        api_key: str,
        api_base: str,
        model: str
    ) -> str:
        """翻译单条文本"""
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # 使用 JSON 模式确保输出格式
            prompt = f"""请将以下文本翻译成{target_lang}，只返回翻译结果，不要添加任何解释：

原文：{text}

翻译："""

            data = {
                'model': model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3
            }

            response = requests.post(
                f"{api_base}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                translated = result['choices'][0]['message']['content'].strip()
                return translated
            else:
                print(f"[Translation] API error: {response.status_code} - {response.text}")
                return text  # 翻译失败，返回原文

        except Exception as e:
            print(f"[Translation] Error: {e}")
            return text

    def batch_translate_segments(
        self,
        segments: List[Dict],
        target_lang: str,
        api_key: str,
        api_base: str,
        model: str
    ) -> List[Dict]:
        """
        批量翻译所有片段
        segments: [{'start': 0.0, 'end': 2.5, 'text': '原文'}, ...]
        返回: [{'start': 0.0, 'end': 2.5, 'text': '原文', 'translated': '译文'}, ...]
        """
        print(f"[Translation] Translating {len(segments)} segments to {target_lang}...")
        sys.stdout.flush()

        translated_segments = []
        total = len(segments)

        for i, segment in enumerate(segments):
            original_text = segment['text']

            print(f"[Translation] [{i+1}/{total}] Translating: {original_text[:30]}...")
            sys.stdout.flush()

            translated_text = self.translate_text(
                original_text,
                target_lang,
                api_key,
                api_base,
                model
            )

            translated_segments.append({
                'start': segment['start'],
                'end': segment['end'],
                'text': original_text,
                'translated': translated_text
            })

            print(f"[Translation] Translated: {translated_text[:30]}...")
            sys.stdout.flush()

            # 更新进度 (0-50%)
            self.progress = 50 * (i + 1) / total

        return translated_segments

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
        print(f"[Rendering] Processing video with {len(translated_segments)} subtitle segments...")
        sys.stdout.flush()

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 创建临时输出文件
        temp_output = output_path.replace('.mp4', '_temp.mp4')

        # 使用 mp4v 编码器（跨平台兼容）
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

        # 创建时间段到字幕的映射
        print(f"[Rendering] Creating frame-to-subtitle mapping...")
        sys.stdout.flush()

        time_to_subtitle = {}
        for segment in translated_segments:
            start_frame = int(segment['start'] * fps)
            end_frame = int(segment['end'] * fps)
            for frame_no in range(start_frame, end_frame + 1):
                time_to_subtitle[frame_no] = segment['translated']

        print(f"[Rendering] Mapped {len(time_to_subtitle)} frames with subtitles")
        sys.stdout.flush()

        # 处理每一帧
        frame_no = 0
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

            out.write(frame)
            frame_no += 1

            # 更新进度 (50-100%)
            self.progress = 50 + 50 * frame_no / total_frames

            if frame_no % 100 == 0:
                print(f"[Rendering] Progress: {frame_no}/{total_frames} frames ({self.progress:.1f}%)")
                sys.stdout.flush()

        cap.release()
        out.release()

        print(f"[Rendering] Video processing completed, re-encoding with FFmpeg...")
        sys.stdout.flush()

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

        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            print(f"[Rendering] FFmpeg encoding completed")
            sys.stdout.flush()
        except subprocess.CalledProcessError as e:
            print(f"[Rendering] FFmpeg error: {e.stderr.decode()}")
            sys.stdout.flush()
            # 如果 FFmpeg 失败，使用临时文件作为输出
            import shutil
            shutil.move(temp_output, output_path)
        else:
            # 删除临时文件
            if os.path.exists(temp_output):
                os.remove(temp_output)

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

            print(f"[WhisperTranslation] Starting translation and rendering for task {self.task_id}")
            sys.stdout.flush()

            # 读取 Whisper 识别结果
            print(f"[WhisperTranslation] Loading Whisper result from: {whisper_result_path}")
            sys.stdout.flush()

            with open(whisper_result_path, 'r', encoding='utf-8') as f:
                whisper_result = json.load(f)

            subtitle_region = whisper_result.get('subtitle_region')
            segments = whisper_result.get('segments', [])

            print(f"[WhisperTranslation] Loaded: {len(segments)} segments, region: {subtitle_region}")
            sys.stdout.flush()

            if not subtitle_region:
                error_msg = "No subtitle region found in Whisper result"
                print(f"[WhisperTranslation ERROR] {error_msg}")
                sys.stdout.flush()
                raise ValueError(error_msg)

            if not segments:
                error_msg = "No subtitle segments found in Whisper result"
                print(f"[WhisperTranslation ERROR] {error_msg}")
                sys.stdout.flush()
                raise ValueError(error_msg)

            # 步骤1: 翻译所有片段
            print(f"[WhisperTranslation] Step 1: Translating {len(segments)} segments...")
            sys.stdout.flush()

            translated_segments = self.batch_translate_segments(
                segments,
                target_lang,
                api_key,
                api_base,
                model
            )

            print(f"[WhisperTranslation] Step 1 completed: {len(translated_segments)} segments translated")
            sys.stdout.flush()

            # 步骤2: 渲染到视频
            print(f"[WhisperTranslation] Step 2: Rendering to video...")
            sys.stdout.flush()

            output_file = self.process_video_with_translations(
                video_path,
                translated_segments,
                subtitle_region,
                output_path,
                bg_color
            )

            self.status = "completed"
            self.progress = 100

            print(f"[WhisperTranslation] Completed: {output_file}")
            sys.stdout.flush()

            return output_file

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            import traceback
            traceback.print_exc()
            raise e

    def get_progress(self) -> dict:
        """获取处理进度"""
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.error if self.error else f"正在处理... {self.progress:.1f}%"
        }
