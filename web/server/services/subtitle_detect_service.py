import cv2
import numpy as np
import sys
import os
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.main import SubtitleDetect


class SubtitleDetectService:
    """字幕检测服务（仅检测和识别，不翻译）"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.progress = 0
        self.status = "pending"
        self.error = None

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
        返回格式：
        {
            'subtitles': [
                {
                    'text': '字幕文本',
                    'frames': [1, 2, 3, ...],  # 出现的帧号
                    'box': (xmin, xmax, ymin, ymax),  # 位置
                    'id': 0  # 唯一标识
                },
                ...
            ],
            'total_frames': 1000,
            'subtitle_count': 50,
            'unique_count': 20
        }
        """
        try:
            self.status = "processing"
            self.progress = 0

            # 打开视频
            cap = cv2.VideoCapture(video_path)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 初始化检测器
            detector = SubtitleDetect(video_path, sub_area)

            # 存储每帧的字幕
            frame_subtitles = {}  # {frame_no: [{'text': '', 'box': ()}, ...]}

            print("Detecting and recognizing subtitles...")
            frame_no = 0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_no += 1

                # 检测文字框
                dt_boxes, _ = detector.detect_subtitle(frame)
                if dt_boxes is None or len(dt_boxes) == 0:
                    self.progress = 100 * frame_no / frame_count
                    continue

                # 转换坐标
                coordinates = detector.get_coordinates(dt_boxes.tolist())

                # 过滤并识别
                frame_subs = []
                for box in coordinates:
                    # 过滤非字幕区域
                    if not self.is_subtitle_region(box, height, width):
                        continue

                    # 如果指定了sub_area，检查是否在范围内
                    if sub_area:
                        xmin, xmax, ymin, ymax = box
                        s_ymin, s_ymax, s_xmin, s_xmax = sub_area
                        if not (s_xmin <= xmin and xmax <= s_xmax and
                                s_ymin <= ymin and ymax <= s_ymax):
                            continue

                    # OCR识别
                    try:
                        xmin, xmax, ymin, ymax = box
                        roi = frame[ymin:ymax, xmin:xmax]

                        # 使用PaddleOCR识别
                        from paddleocr import PaddleOCR
                        if not hasattr(self, 'ocr'):
                            self.ocr = PaddleOCR(use_angle_cls=True, lang='ch')

                        result = self.ocr.ocr(roi, cls=True)
                        if result and result[0]:
                            texts = [line[1][0] for line in result[0]]
                            text = ' '.join(texts).strip()

                            if text:  # 只保存非空文本
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
                self.progress = 100 * frame_no / frame_count

            cap.release()

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
