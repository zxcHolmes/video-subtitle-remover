import asyncio
from typing import Dict, Optional
from models.task import TaskInfo, TaskStatus
from utils.exceptions import TaskNotFoundException


class TaskManager:
    """Manage all tasks in memory"""

    def __init__(self):
        self.tasks: Dict[str, TaskInfo] = {}
        self.services: Dict[str, 'SubtitleRemovalService'] = {}

    def create_task(self, task_id: str, file_path: str) -> TaskInfo:
        """Create a new task"""
        task = TaskInfo(
            task_id=task_id,
            status=TaskStatus.UPLOADED,
            file_path=file_path
        )
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> TaskInfo:
        """Get task by ID"""
        if task_id not in self.tasks:
            raise TaskNotFoundException(f"Task {task_id} not found")
        return self.tasks[task_id]

    def update_task(self, task_id: str, **kwargs):
        """Update task fields"""
        if task_id not in self.tasks:
            raise TaskNotFoundException(f"Task {task_id} not found")

        for key, value in kwargs.items():
            if hasattr(self.tasks[task_id], key):
                setattr(self.tasks[task_id], key, value)

    def register_service(self, task_id: str, service: 'SubtitleRemovalService'):
        """Register a processing service for a task"""
        self.services[task_id] = service

    def get_service(self, task_id: str) -> Optional['SubtitleRemovalService']:
        """Get processing service for a task"""
        return self.services.get(task_id)

    async def get_progress(self, task_id: str) -> dict:
        """Get progress for a task"""
        if task_id not in self.services:
            task = self.get_task(task_id)
            return {
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress,
                "message": task.message
            }

        service = self.services[task_id]
        progress_info = service.get_progress()

        # Update task status
        self.update_task(
            task_id,
            status=progress_info["status"],
            progress=progress_info.get("progress", 0),
            message=progress_info.get("message"),
            output_path=progress_info.get("output_path")
        )

        return {
            "task_id": task_id,
            **progress_info
        }


# Global task manager instance
task_manager = TaskManager()
