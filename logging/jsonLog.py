import json, logging
import socket
import uuid
from datetime import datetime

hostname = socket.gethostname()

class JsonFormatter(logging.Formatter):

  def format(self, record):
    jsonLog = {
      "timestamp": datetime.fromtimestamp(record.created).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z', # Only 3 Milliseconds
      # "time": datetime.fromtimestamp(record.created).isoformat(),   
      "level": record.levelname,
      "logId": str(uuid.uuid4()),
      "service": "acapy",
      "hostname": hostname,
      "pid": record.process,
      "file": record.filename,
      "function": record.funcName,
      "lineNumber": record.lineno,
      "message": record.msg,
    }

    return json.dumps(jsonLog)
    
    