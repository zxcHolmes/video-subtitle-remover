import cv2
import sys
import os
from typing import List, Dict, Tuple, Optional

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.main import SubtitleDetect
from backend import config


class WhisperSubtitleService:
    """
    使用 Faster Whisper 进行语音识别的字幕服务
    优势：
    1. 准确的时间段定位
    2. 高质量的文字识别
    3. 不受字幕动态效果影响
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.progress = 0
        self.status = "pending"
        self.error = None

    def detect_subtitle_region(
        self,
        video_path: str,
        sub_area: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        检测字幕区域（只需要一次）
        返回: (ymin, ymax, xmin, xmax)
        """
        print("[Whisper] Step 1: Detecting subtitle region...")
        sys.stdout.flush()

        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))

        # 如果指定了区域，直接返回
        if sub_area:
            print(f"[Whisper] Using specified region: {sub_area}")
            return sub_area

        # 暂时跳过 OCR 检测，使用默认区域（底部 15%，为翻译字幕预留空间）
        # 原字幕通常在 80%-95% 位置，翻译字幕放在 95%-100% 位置
        default_region = (
            int(height * 0.95),  # ymin: 从 95% 高度开始
            height,              # ymax: 到底部
            50,                  # xmin: 左边留 50px 边距
            width - 50           # xmax: 右边留 50px 边距
        )

        print(f"[Whisper] Using default region for translated subtitles (bottom 5%)")
        print(f"[Whisper] Region: Y:{default_region[0]}-{default_region[1]}, X:{default_region[2]}-{default_region[3]}")
        sys.stdout.flush()

        cap.release()
        return default_region

    def transcribe_with_whisper(
        self,
        video_path: str,
        language: str = "zh"
    ) -> List[Dict]:
        """
        使用 Faster Whisper 识别语音
        返回: [
            {
                'start': 0.0,
                'end': 2.5,
                'text': '狼一脚踢开了嘴边的肥羊'
            },
            ...
        ]
        """
        print("[Whisper] Step 2: Transcribing audio with Faster Whisper...")
        sys.stdout.flush()

        try:
            from faster_whisper import WhisperModel

            # 使用 medium 模型（平衡速度和准确率）
            # 可选: tiny, base, small, medium, large-v2, large-v3
            model_size = "medium"
            print(f"[Whisper] Loading {model_size} model...")
            sys.stdout.flush()

            # 强制使用 GPU
            device = "cuda"
            compute_type = "float16"

            print(f"[Whisper] Using device: {device}, compute_type: {compute_type}")
            sys.stdout.flush()

            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            print(f"[Whisper] Model loaded on {device}")
            sys.stdout.flush()

            # 转录音频
            segments, info = model.transcribe(
                video_path,
                language=language,
                beam_size=5,
                vad_filter=True,  # 语音活动检测，过滤静音
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            print(f"[Whisper] Detected language: {info.language} (probability: {info.language_probability:.2f})")
            sys.stdout.flush()

            # 转换为列表
            results = []
            for i, segment in enumerate(segments):
                results.append({
                    'id': i,
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text.strip()
                })
                print(f"[Whisper] [{segment.start:.1f}s - {segment.end:.1f}s] {segment.text.strip()}")
                sys.stdout.flush()

                self.progress = 50 + (50 * (i + 1) / len(list(segments)))

            print(f"[Whisper] Transcription completed: {len(results)} segments")
            sys.stdout.flush()

            return results

        except ImportError:
            error_msg = "Faster Whisper not installed. Please run: pip install faster-whisper"
            print(f"[Whisper ERROR] {error_msg}")
            sys.stdout.flush()
            raise ImportError(error_msg)

    def detect_and_transcribe(
        self,
        video_path: str,
        sub_area: Optional[Tuple[int, int, int, int]] = None,
        language: str = "zh"
    ) -> Dict:
        """
        完整流程：检测字幕区域 + Whisper 语音识别
        """
        try:
            self.status = "processing"
            self.progress = 0

            print(f"[Whisper] Starting Whisper-based subtitle detection for task {self.task_id}")
            sys.stdout.flush()

            # Step 1: 检测字幕区域
            subtitle_region = self.detect_subtitle_region(video_path, sub_area)
            self.progress = 30

            # Step 2: Whisper 语音识别
            segments = self.transcribe_with_whisper(video_path, language)
            self.progress = 90

            # 组合结果
            result = {
                'subtitle_region': subtitle_region,
                'segments': segments,
                'total_segments': len(segments),
                'method': 'whisper'
            }

            self.status = "completed"
            self.progress = 100

            return result

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            raise e

    def get_progress(self) -> dict:
        """获取检测进度"""
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.error if self.error else f"正在处理... {self.progress:.1f}%"
        }
