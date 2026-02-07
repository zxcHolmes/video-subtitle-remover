import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import requests
import time
import json
import os
import sys
from typing import List, Dict, Tuple, Optional

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.main import SubtitleDetect


class SubtitleTranslationService:
    """字幕翻译服务"""

    def __init__(
        self,
        task_id: str,
        api_key: str,
        api_base: str = "https://ollama.iamdev.cn",
        model: str = "gpt-oss:20b",
        target_lang: str = "中文"
    ):
        self.task_id = task_id
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.target_lang = target_lang
        self.progress = 0
        self.status = "pending"
        self.error = None

    def is_subtitle_region(self, box: Tuple[int, int, int, int], frame_height: int, frame_width: int) -> bool:
        """
        判断是否为字幕区域
        字幕通常位于底部，且宽度较长
        """
        xmin, xmax, ymin, ymax = box
        width = xmax - xmin
        height = ymax - ymin

        # 宽高比：字幕通常比较扁平 (宽度 > 高度 * 3)
        if width < height * 3:
            return False

        # 位置：通常在画面下半部分 (y > height * 0.5)
        if ymin < frame_height * 0.5:
            return False

        # 宽度：通常占画面宽度的一定比例 (> 20%)
        if width < frame_width * 0.2:
            return False

        return True

    def merge_duplicates(self, subtitle_data: Dict[int, List[Dict]]) -> List[Dict]:
        """
        合并相同的字幕，返回去重后的字幕列表
        """
        unique_texts = {}  # text -> {frames: [frame_nos], box: box}

        for frame_no, detections in subtitle_data.items():
            for detection in detections:
                text = detection['text'].strip()
                if not text:
                    continue

                if text in unique_texts:
                    unique_texts[text]['frames'].append(frame_no)
                else:
                    unique_texts[text] = {
                        'frames': [frame_no],
                        'box': detection['box'],
                        'text': text
                    }

        # 转换为列表
        result = []
        for text, data in unique_texts.items():
            result.append({
                'text': text,
                'frames': sorted(data['frames']),
                'box': data['box']
            })

        return result

    def smart_segment(self, subtitles: List[Dict], max_chars: int = 2000) -> List[List[Dict]]:
        """
        智能分段，保持句子完整性
        """
        segments = []
        current_segment = []
        current_length = 0

        for subtitle in subtitles:
            text = subtitle['text']
            text_length = len(text)

            # 如果加上这句话会超过限制
            if current_length + text_length > max_chars and current_segment:
                # 保存当前段，开启新段
                segments.append(current_segment)
                current_segment = [subtitle]
                current_length = text_length
            else:
                current_segment.append(subtitle)
                current_length += text_length

        # 添加最后一段
        if current_segment:
            segments.append(current_segment)

        return segments

    def translate_segment(self, texts: List[str]) -> Dict[str, str]:
        """
        调用大模型翻译一段文本
        返回: {原文: 译文} 的字典
        """
        # 构建翻译请求
        prompt = f"""请将以下字幕翻译成{self.target_lang}。要求：
1. 保持原意，符合{self.target_lang}表达习惯
2. 输出JSON格式，key为原文，value为译文
3. 不要添加任何解释或额外内容

字幕列表：
{json.dumps(texts, ensure_ascii=False, indent=2)}

请只返回JSON对象，格式：{{"原文1": "译文1", "原文2": "译文2", ...}}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"你是一个专业的字幕翻译助手，擅长将字幕翻译成{self.target_lang}。"},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3  # 较低温度保证翻译稳定性
        }

        try:
            response = requests.post(
                f"{self.api_base}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 解析JSON
            translation_map = json.loads(content)
            return translation_map

        except Exception as e:
            print(f"Translation error: {e}")
            # 返回原文
            return {text: text for text in texts}

    def translate_all(self, subtitle_data: List[Dict]) -> Dict[str, str]:
        """
        翻译所有字幕
        """
        # 1. 合并去重
        unique_subtitles = self.merge_duplicates(
            {i: [sub] for i, sub in enumerate(subtitle_data)}
        )

        # 2. 智能分段
        segments = self.smart_segment(unique_subtitles, max_chars=2000)

        # 3. 逐段翻译
        all_translations = {}
        total_segments = len(segments)

        for i, segment in enumerate(segments):
            print(f"Translating segment {i+1}/{total_segments}...")

            texts = [sub['text'] for sub in segment]
            translations = self.translate_segment(texts)

            all_translations.update(translations)

            # 更新进度
            self.progress = 50 + (50 * (i + 1) / total_segments)

            # 避免请求过快
            if i < total_segments - 1:
                time.sleep(1)

        return all_translations

    def render_subtitle(
        self,
        frame: np.ndarray,
        text: str,
        box: Tuple[int, int, int, int],
        bg_color: str = "black",
        text_color: str = "white",
        font_path: Optional[str] = None
    ) -> np.ndarray:
        """
        在视频帧上渲染字幕
        """
        xmin, xmax, ymin, ymax = box
        width = xmax - xmin
        height = ymax - ymin

        # 转换为PIL图像
        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(frame_pil)

        # 绘制背景矩形
        bg_rgb = (0, 0, 0) if bg_color == "black" else (255, 255, 255)
        draw.rectangle([xmin, ymin, xmax, ymax], fill=bg_rgb)

        # 加载字体
        if font_path is None or not os.path.exists(font_path):
            # 尝试使用系统字体
            try:
                # macOS
                if os.path.exists("/System/Library/Fonts/PingFang.ttc"):
                    font_path = "/System/Library/Fonts/PingFang.ttc"
                # Linux
                elif os.path.exists("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
                    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
                # Windows
                elif os.path.exists("C:\\Windows\\Fonts\\msyh.ttc"):
                    font_path = "C:\\Windows\\Fonts\\msyh.ttc"
            except:
                pass

        # 自动调整字体大小
        font_size = int(height * 0.6)
        try:
            if font_path:
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # 计算文本位置（居中）
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = xmin + (width - text_width) // 2
        y = ymin + (height - text_height) // 2

        # 绘制文本
        text_rgb = (255, 255, 255) if text_color == "white" else (0, 0, 0)
        draw.text((x, y), text, fill=text_rgb, font=font)

        # 转回OpenCV格式
        frame_result = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)
        return frame_result

    def process_video(
        self,
        video_path: str,
        output_path: str,
        sub_area: Optional[Tuple[int, int, int, int]] = None,
        bg_color: str = "black"
    ) -> str:
        """
        处理视频，翻译字幕
        """
        try:
            self.status = "processing"
            self.progress = 0

            # 1. 打开视频
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 2. 初始化字幕检测器
            detector = SubtitleDetect(video_path, sub_area)

            # 3. 检测字幕并OCR识别
            print("Detecting and recognizing subtitles...")
            subtitle_data = {}  # {frame_no: [{'text': '', 'box': (x1,x2,y1,y2)}]}

            frame_no = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_no += 1

                # 检测文字框
                dt_boxes, _ = detector.detect_subtitle(frame)
                if dt_boxes is None or len(dt_boxes) == 0:
                    continue

                # 转换坐标
                coordinates = detector.get_coordinates(dt_boxes.tolist())

                # 过滤字幕区域并OCR识别
                frame_subtitles = []
                for box in coordinates:
                    if not self.is_subtitle_region(box, height, width):
                        continue

                    # 如果指定了sub_area，检查是否在范围内
                    if sub_area:
                        xmin, xmax, ymin, ymax = box
                        s_ymin, s_ymax, s_xmin, s_xmax = sub_area
                        if not (s_xmin <= xmin and xmax <= s_xmax and
                                s_ymin <= ymin and ymax <= s_ymax):
                            continue

                    # OCR识别文字
                    xmin, xmax, ymin, ymax = box
                    roi = frame[ymin:ymax, xmin:xmax]

                    # 使用PaddleOCR识别
                    try:
                        from paddleocr import PaddleOCR
                        if not hasattr(self, 'ocr'):
                            self.ocr = PaddleOCR(use_angle_cls=True, lang='ch')

                        result = self.ocr.ocr(roi, cls=True)
                        if result and result[0]:
                            texts = [line[1][0] for line in result[0]]
                            text = ' '.join(texts)

                            frame_subtitles.append({
                                'text': text,
                                'box': box
                            })
                    except Exception as e:
                        print(f"OCR error at frame {frame_no}: {e}")
                        continue

                if frame_subtitles:
                    subtitle_data[frame_no] = frame_subtitles

                # 更新进度 (0-50%)
                self.progress = 50 * frame_no / frame_count

            cap.release()

            if not subtitle_data:
                raise Exception("未检测到字幕")

            # 4. 翻译字幕
            print("Translating subtitles...")
            all_subs = []
            for frame_no, subs in subtitle_data.items():
                for sub in subs:
                    all_subs.append({'frame': frame_no, **sub})

            translations = self.translate_all(all_subs)

            # 5. 渲染翻译后的字幕到视频
            print("Rendering translated subtitles...")
            cap = cv2.VideoCapture(video_path)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            frame_no = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_no += 1

                # 如果该帧有字幕，渲染翻译
                if frame_no in subtitle_data:
                    for sub in subtitle_data[frame_no]:
                        original_text = sub['text']
                        translated_text = translations.get(original_text, original_text)

                        frame = self.render_subtitle(
                            frame,
                            translated_text,
                            sub['box'],
                            bg_color=bg_color
                        )

                out.write(frame)

                # 更新进度 (50-100%)
                self.progress = 50 + 50 * frame_no / frame_count

            cap.release()
            out.release()

            self.status = "completed"
            self.progress = 100
            return output_path

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            raise e

    def get_progress(self) -> dict:
        """获取处理进度"""
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.error if self.error else f"正在处理... {self.progress:.1f}%"
        }
