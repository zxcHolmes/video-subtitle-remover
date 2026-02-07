from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ProcessMode(str, Enum):
    STTN = "sttn"
    LAMA = "lama"
    PROPAINTER = "propainter"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float = 0.0
    message: Optional[str] = None
    file_path: Optional[str] = None
    output_path: Optional[str] = None


class ProcessConfig(BaseModel):
    task_id: str
    mode: ProcessMode = ProcessMode.STTN
    sub_area: Optional[List[int]] = None
    skip_detection: bool = True


class TranslationConfig(BaseModel):
    task_id: str
    api_key: str
    api_base: str = "https://ollama.iamdev.cn"
    model: str = "gpt-oss:20b"
    target_lang: str = "中文"
    bg_color: str = "black"  # black or white
    sub_area: Optional[List[int]] = None
