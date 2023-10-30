from uuid import uuid4, UUID
from datetime import datetime

class Message():
    def __init__(self, text:str, sender_id:UUID, receiver_id:UUID, timestamp:datetime) -> None:
        self.text = text
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.timestamp = timestamp
    
    def __str__(self) -> str:
        return f"{self.text} % {self.sender_id.__str__()} % {self.receiver_id.__str__()} % {self.timestamp.__str__()}"
