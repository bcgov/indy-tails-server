# Python3 logging custom formatter.
# For more information, please visit: https://docs.python.org/3/library/logging.html
import json
import logging
import socket
import uuid
from datetime import datetime

hostname = socket.gethostname()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Interpolates record message properly
        record.msg = super().format(record)

        jsonLog = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3]
            + "Z",  # Only 3 Milliseconds
            "level": record.levelname,
            "logId": str(uuid.uuid4()),
            "service": "tails",
            "hostname": hostname,
            "pid": record.process,
            "file": record.filename,
            "function": record.funcName,
            "lineNumber": record.lineno,
            "message": record.msg,
        }

        return json.dumps(jsonLog)
