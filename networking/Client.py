import socket
from Server import SERVER_HOST, SERVER_PORT

ADDRESS = (SERVER_HOST, SERVER_PORT)

class Client():
    def __init__(self, address:(str,int)) -> None:
        self.address = address
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect()

    def connect(self):
        try:
            self.client_socket.connect(self.address)
            self.run()
        except socket.error:
            print("Couldn't connect.")
            return

    def sendMessage(self, text:str):
        bytes = text.encode('utf8')
        self.client_socket.send(bytes)

    def run(self):
        text = input("Message: ")
        self.sendMessage(text)

    def listen(self):
        bytes = self.client_socket.recv(1024)
        text = bytes.decode()
        print(f"SERVER: {text}")

if __name__ == "__main__":
    c = Client(ADDRESS)