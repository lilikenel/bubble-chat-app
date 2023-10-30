from uuid import uuid4
from datetime import datetime

class Message():
    sender_id = None # UUID
    receiver_id = None # UUID
    timestamp = None # datetime

    def __init__(self) -> None:
        pass
