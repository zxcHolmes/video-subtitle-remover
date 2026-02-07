import cv2
import numpy as np
import sys
import os
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from functools import cached_property

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.main import SubtitleDetect
from backend import config


class SubtitleDetectService:
    """字幕检测服务（仅检测和识别，不翻译）"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.progress = 0
        self.status = "pending"
        self.error = None
        self._ocr = None

    @cached_property
    def ocr_engine(self):
        """初始化完整的 OCR 引擎（检测+识别，使用 GPU）"""
        from paddleocr import PaddleOCR

        # 根据配置决定是否使用 GPU
        use_gpu = False
        if config.ONNX_PROVIDERS:
            print(f"Using GPU providers: {config.ONNX_PROVIDERS}")

        # 检查是否有 CUDA
        try:
            import paddle
            if paddle.is_compiled_with_cuda():
                use_gpu = True
                print("CUDA available, using GPU for OCR")
        except:
            pass

        print(f"Initializing PaddleOCR (GPU: {use_gpu})...")
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='ch',
            use_gpu=use_gpu,
            show_log=False,
            det_model_dir=str(config.DET_MODEL_PATH) if hasattr(config, 'DET_MODEL_PATH') else None
        )
        print("PaddleOCR initialized")
        return ocr

    def is_subtitle_region(
        self,
        box: Tuple[int, int, int, int],
        frame_height: int,
        frame_width: int
    ) -> bool:
        """
        判断是否为字幕区域
        """
        xmin, xmax, ymin, ymax = box
        width = xmax - xmin
        height = ymax - ymin

        # 宽高比：字幕通常比较扁平
        if width < height * 3:
            return False

        # 位置：通常在画面下半部分
        if ymin < frame_height * 0.5:
            return False

        # 宽度：通常占画面宽度的一定比例
        if width < frame_width * 0.2:
            return False

        return True

    def detect_and_recognize(
        self,
        video_path: str,
        sub_area: Optional[Tuple[int, int, int, int]] = None
    ) -> Dict:
        """
        检测并识别视频中的字幕
        使用和去除字幕一样的方式：
        1. 快速检测所有帧（GPU 加速）
        2. 只对有字幕的帧做 OCR 识别
        """
        try:
            self.status = "processing"
            self.progress = 0

            print(f"Starting subtitle detection for task {self.task_id}")

            # 初始化检测器（会使用 GPU）
            detector = SubtitleDetect(video_path, sub_area)

            # 第一步：快速检测所有帧，找到有字幕的帧（使用 GPU，很快）
            print("Step 1: Fast detection (GPU accelerated)...")
            subtitle_frame_no_box_dict = detector.find_subtitle_frame_no()
            self.progress = 50

            print(f"Found subtitles in {len(subtitle_frame_no_box_dict)} frames")

            if len(subtitle_frame_no_box_dict) == 0:
                return {
                    'subtitles': [],
                    'total_frames': 0,
                    'subtitle_count': 0,
                    'unique_count': 0
                }

            # 第二步：只对有字幕的帧做 OCR 识别
            print("Step 2: OCR recognition on detected frames...")
            cap = cv2.VideoCapture(video_path)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 初始化 OCR 引擎（检测+识别，GPU 加速）
            ocr = self.ocr_engine

            # 存储识别结果
            frame_subtitles = {}
            total_detect_frames = len(subtitle_frame_no_box_dict)
            processed_frames = 0

            for frame_no, boxes in subtitle_frame_no_box_dict.items():
                # 读取指定帧
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no - 1)
                ret, frame = cap.read()
                if not ret:
                    continue

                frame_subs = []
                for box in boxes:
                    xmin, xmax, ymin, ymax = box

                    # 过滤非字幕区域
                    if not self.is_subtitle_region(box, height, width):
                        continue

                    # OCR 识别
                    try:
                        roi = frame[ymin:ymax, xmin:xmax]

                        # 使用 PaddleOCR 识别（GPU 加速）
                        result = ocr.ocr(roi, cls=True)
                        if result and result[0]:
                            # 提取所有文本行
                            texts = [line[1][0] for line in result[0]]
                            text = ' '.join(texts).strip()

                            if text and len(text) > 0:
                                frame_subs.append({
                                    'text': text,
                                    'box': box
                                })
                                if processed_frames < 5:  # 只打印前几个
                                    print(f"Frame {frame_no}: '{text}' at {box}")
                    except Exception as e:
                        print(f"OCR error at frame {frame_no}, box {box}: {e}")
                        continue

                if frame_subs:
                    frame_subtitles[frame_no] = frame_subs

                processed_frames += 1
                # 更新进度（50-100%）
                self.progress = 50 + (50 * processed_frames / total_detect_frames)

                if processed_frames % max(1, total_detect_frames // 10) == 0 or processed_frames == total_detect_frames:
                    print(f"OCR Progress: {processed_frames}/{total_detect_frames} frames ({self.progress:.1f}%)")

            cap.release()
            print(f"Detection completed: {len(frame_subtitles)} frames with recognized text")

            # 合并相同字幕
            unique_subtitles = self._merge_duplicates(frame_subtitles)

            # 生成结果
            result = {
                'subtitles': unique_subtitles,
                'total_frames': frame_count,
                'subtitle_count': sum(len(subs) for subs in frame_subtitles.values()),
                'unique_count': len(unique_subtitles)
            }

            self.status = "completed"
            self.progress = 100

            return result

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            raise e

    def _merge_duplicates(self, frame_subtitles: Dict[int, List[Dict]]) -> List[Dict]:
        """
        合并相同的字幕
        """
        # 按文本内容分组
        text_groups = defaultdict(lambda: {
            'frames': [],
            'boxes': [],
            'text': ''
        })

        for frame_no, subs in frame_subtitles.items():
            for sub in subs:
                text = sub['text']
                text_groups[text]['frames'].append(frame_no)
                text_groups[text]['boxes'].append(sub['box'])
                text_groups[text]['text'] = text

        # 转换为列表
        unique_subtitles = []
        for idx, (text, data) in enumerate(sorted(text_groups.items())):
            # 使用最常见的box（众数）
            box_counts = defaultdict(int)
            for box in data['boxes']:
                box_counts[box] += 1
            most_common_box = max(box_counts.items(), key=lambda x: x[1])[0]

            unique_subtitles.append({
                'id': idx,
                'text': text,
                'frames': sorted(data['frames']),
                'frame_count': len(data['frames']),
                'box': most_common_box
            })

        # 按首次出现帧号排序
        unique_subtitles.sort(key=lambda x: x['frames'][0])

        # 重新分配ID
        for idx, sub in enumerate(unique_subtitles):
            sub['id'] = idx

        return unique_subtitles

    def get_progress(self) -> dict:
        """获取检测进度"""
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.error if self.error else f"正在检测... {self.progress:.1f}%"
        }
