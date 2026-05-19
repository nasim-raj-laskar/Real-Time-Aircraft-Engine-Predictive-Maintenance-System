import logging
import json
from datetime import datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for easy parsing."""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields
        if hasattr(record, 'engine_id'):
            log_data['engine_id'] = record.engine_id
        if hasattr(record, 'rul'):
            log_data['rul'] = record.rul
        if hasattr(record, 'risk'):
            log_data['risk'] = record.risk
        if hasattr(record, 'risk_level'):
            log_data['risk_level'] = record.risk_level
        if hasattr(record, 'latency_ms'):
            log_data['latency_ms'] = record.latency_ms
        if hasattr(record, 'confidence'):
            log_data['confidence'] = record.confidence
        
        return json.dumps(log_data)


def setup_inference_logger(name: str = 'inference', log_file: Path = None):
    """
    Setup structured logger for inference service.
    
    Args:
        name: Logger name
        log_file: Path to log file (optional)
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    
    return logger
