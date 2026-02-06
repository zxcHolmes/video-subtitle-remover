import threading
import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '../../../backend')
sys.path.insert(0, backend_path)

from backend.main import SubtitleRemover
from backend import config


class SubtitleRemovalService:
    """Wrapper for SubtitleRemover with async support"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.remover = None
        self.thread = None
        self.error = None
        self.output_path = None

    def process(self, video_path: str, sub_area=None, mode="sttn", skip_detection=True):
        """Start processing video in a separate thread"""

        # Set configuration based on mode
        if mode == "sttn":
            config.MODE = config.InpaintMode.STTN
            config.STTN_SKIP_DETECTION = skip_detection
        elif mode == "lama":
            config.MODE = config.InpaintMode.LAMA
        elif mode == "propainter":
            config.MODE = config.InpaintMode.PROPAINTER

        # Create SubtitleRemover instance
        self.remover = SubtitleRemover(video_path, sub_area=sub_area, gui_mode=False)

        # Run in separate thread
        self.thread = threading.Thread(target=self._run_remover)
        self.thread.daemon = True
        self.thread.start()

    def _run_remover(self):
        """Run the remover in thread"""
        try:
            self.remover.run()
            self.output_path = self.remover.video_out_name
        except Exception as e:
            self.error = str(e)

    def get_progress(self) -> dict:
        """Get current progress"""
        if self.remover is None:
            return {
                "status": "pending",
                "progress": 0,
                "message": "等待开始处理"
            }

        if self.error:
            return {
                "status": "error",
                "progress": 0,
                "message": self.error
            }

        if self.remover.isFinished:
            return {
                "status": "completed",
                "progress": 100,
                "message": "处理完成",
                "output_path": self.output_path
            }

        # Get progress from remover
        progress = self.remover.progress_total

        return {
            "status": "processing",
            "progress": progress,
            "message": f"正在处理... {progress:.1f}%"
        }

    def is_running(self) -> bool:
        """Check if processing is still running"""
        return self.thread is not None and self.thread.is_alive()
