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
        策略：每秒采样1帧进行检测和识别（字幕不可能1秒换一次）
        """
        try:
            self.status = "processing"
            self.progress = 0

            print(f"Starting subtitle detection for task {self.task_id}")

            # 打开视频获取信息
            cap = cv2.VideoCapture(video_path)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_seconds = frame_count / fps

            print(f"Video: {width}x{height}, {fps} FPS, {frame_count} frames, {duration_seconds:.1f}s")
            print(f"Sampling strategy: 1 frame per second = ~{int(duration_seconds)} frames to process")

            # 初始化检测器和 OCR（使用 GPU）
            detector = SubtitleDetect(video_path, sub_area)
            ocr = self.ocr_engine

            # 采样：每秒取1帧
            frame_subtitles = {}
            sample_frames = list(range(0, frame_count, fps))  # 0, fps, 2*fps, 3*fps, ...
            total_samples = len(sample_frames)

            print(f"Processing {total_samples} sampled frames...")

            for idx, frame_no in enumerate(sample_frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                ret, frame = cap.read()
                if not ret:
                    continue

                # 检测文字框（GPU 加速）
                dt_boxes, _ = detector.detect_subtitle(frame)
                if dt_boxes is None or len(dt_boxes) == 0:
                    self.progress = 100 * (idx + 1) / total_samples
                    continue

                # 转换坐标
                coordinates = detector.get_coordinates(dt_boxes.tolist())

                # 过滤并识别
                frame_subs = []
                for box in coordinates:
                    xmin, xmax, ymin, ymax = box

                    # 过滤非字幕区域
                    if not self.is_subtitle_region(box, height, width):
                        continue

                    # OCR 识别（GPU 加速）
                    try:
                        roi = frame[ymin:ymax, xmin:xmax]
                        result = ocr.ocr(roi, cls=True)

                        if result and result[0]:
                            texts = [line[1][0] for line in result[0]]
                            text = ' '.join(texts).strip()

                            if text and len(text) > 0:
                                frame_subs.append({
                                    'text': text,
                                    'box': box
                                })
                    except Exception as e:
                        print(f"OCR error at frame {frame_no}: {e}")
                        continue

                if frame_subs:
                    frame_subtitles[frame_no] = frame_subs

                # 更新进度
                self.progress = 100 * (idx + 1) / total_samples

                if (idx + 1) % max(1, total_samples // 10) == 0 or idx + 1 == total_samples:
                    print(f"Progress: {idx + 1}/{total_samples} frames ({self.progress:.1f}%)")

            cap.release()
            print(f"Found subtitles in {len(frame_subtitles)} sampled frames")


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
