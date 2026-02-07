import asyncio
from typing import Dict, Optional
from models.task import TaskInfo, TaskStatus
from utils.exceptions import TaskNotFoundException
from database import db


class TaskManager:
    """Manage all tasks with SQLite database persistence"""

    def __init__(self):
        self.services: Dict[str, 'SubtitleRemovalService'] = {}

    def create_task(self, task_id: str, file_path: str, file_name: str) -> TaskInfo:
        """Create a new task (with file deduplication)"""
        # Add file to database (or get existing hash if duplicate)
        file_hash = db.add_or_get_file(file_path, file_name)

        # Get the actual file path (might be different if duplicate)
        actual_file_path = db.get_file_path_by_hash(file_hash)

        # Create task in database
        db.create_task(task_id, file_hash, status='uploaded')

        # Return TaskInfo object
        return TaskInfo(
            task_id=task_id,
            status=TaskStatus.UPLOADED,
            file_path=actual_file_path
        )

    def get_task(self, task_id: str) -> TaskInfo:
        """Get task by ID from database"""
        task_data = db.get_task(task_id)
        if not task_data:
            raise TaskNotFoundException(f"Task {task_id} not found")

        return TaskInfo(
            task_id=task_data['task_id'],
            status=TaskStatus(task_data['status']),
            file_path=task_data['file_path'],
            progress=task_data.get('progress', 0),
            message=task_data.get('message'),
            output_path=task_data.get('output_path')
        )

    def update_task(self, task_id: str, **kwargs):
        """Update task fields in database"""
        # Convert TaskStatus enum to string if present
        if 'status' in kwargs and isinstance(kwargs['status'], TaskStatus):
            kwargs['status'] = kwargs['status'].value

        db.update_task(task_id, **kwargs)

    def register_service(self, task_id: str, service: 'SubtitleRemovalService'):
        """Register a processing service for a task (in-memory only)"""
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
                "status": task.status.value,
                "progress": task.progress,
                "message": task.message
            }

        service = self.services[task_id]
        progress_info = service.get_progress()

        # Update task status in database
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

