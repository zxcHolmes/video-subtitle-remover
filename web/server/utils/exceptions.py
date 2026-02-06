class TaskNotFoundException(Exception):
    """Task not found"""
    pass


class InvalidFileException(Exception):
    """Invalid file format"""
    pass


class ProcessingException(Exception):
    """Error during processing"""
    pass
