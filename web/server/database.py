import sqlite3
import hashlib
import os
from contextlib import contextmanager
from typing import Optional, Dict
import tempfile


class Database:
    """SQLite database for task and file management"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(tempfile.gettempdir(), 'vsr_tasks.db')
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 文件表：存储上传的文件信息（去重）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    file_hash TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 任务表：存储处理任务
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0,
                    message TEXT,
                    output_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_hash) REFERENCES files(file_hash)
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)')

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 64kb chunks for large files
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def add_or_get_file(self, file_path: str, file_name: str) -> str:
        """
        Add file to database or get existing hash if duplicate
        Returns: file_hash
        """
        file_hash = self.calculate_file_hash(file_path)
        file_size = os.path.getsize(file_path)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check if file already exists
            cursor.execute('SELECT file_hash, file_path FROM files WHERE file_hash = ?', (file_hash,))
            existing = cursor.fetchone()

            if existing:
                print(f"[DB] File already exists with hash {file_hash[:8]}... (skipping duplicate)")
                # 如果旧文件路径不同，可以删除新上传的文件（节省空间）
                if existing['file_path'] != file_path and os.path.exists(file_path):
                    print(f"[DB] Removing duplicate file: {file_path}")
                    os.remove(file_path)
                return file_hash
            else:
                # Insert new file
                cursor.execute('''
                    INSERT INTO files (file_hash, file_path, file_name, file_size)
                    VALUES (?, ?, ?, ?)
                ''', (file_hash, file_path, file_name, file_size))
                print(f"[DB] New file added with hash {file_hash[:8]}...")
                return file_hash

    def create_task(self, task_id: str, file_hash: str, status: str = 'uploaded') -> None:
        """Create a new task"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (task_id, file_hash, status)
                VALUES (?, ?, ?)
            ''', (task_id, file_hash, status))
            print(f"[DB] Task {task_id} created")

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, f.file_path, f.file_name
                FROM tasks t
                JOIN files f ON t.file_hash = f.file_hash
                WHERE t.task_id = ?
            ''', (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_task(self, task_id: str, **kwargs) -> None:
        """Update task fields"""
        if not kwargs:
            return

        # Build SET clause dynamically
        set_parts = []
        values = []
        for key, value in kwargs.items():
            if key in ['status', 'progress', 'message', 'output_path']:
                set_parts.append(f"{key} = ?")
                values.append(value)

        if not set_parts:
            return

        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        values.append(task_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE tasks
                SET {', '.join(set_parts)}
                WHERE task_id = ?
            ''', values)
            print(f"[DB] Task {task_id} updated: {kwargs}")

    def get_file_path_by_hash(self, file_hash: str) -> Optional[str]:
        """Get file path by hash"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT file_path FROM files WHERE file_hash = ?', (file_hash,))
            row = cursor.fetchone()
            return row['file_path'] if row else None

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """Delete tasks older than specified days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM tasks
                WHERE created_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            deleted_count = cursor.rowcount
            print(f"[DB] Cleaned up {deleted_count} old tasks")
            return deleted_count


# Global database instance
db = Database()
