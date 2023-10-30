import socket
from threading import Thread
from ClientHandler import ClientHandler

SERVER_HOST = "localhost"
SERVER_PORT = 5050

"""
Multi-thread server that keeps track of all client connections.
Assigns each successfully connected client a ClientHandler in a new thread.
"""
class Server():
    def __init__(self, host:str, port:int) -> None:
        self.server_host = host
        self.server_port = port
        self.start()

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.server_host, self.server_port))
        self.server_socket.listen()
        print(f"SERVER: Server hosted at {self.server_host} on port {self.server_port}.")
        self.run()

    def stop(self):
        self.server_socket.close()

    def run(self):
        try:
            client_socket, client_address = self.server_socket.accept()
            print(f"SERVER: A new client {client_address} has joined.")
            clientHandler = ClientHandler(client_socket)
            thread = Thread(target=clientHandler, daemon=True)
            thread.run()
        except socket.error:
            print("SERVER: Something went wrong.")
            self.stop()

if __name__ == "__main__":
    s = Server(SERVER_HOST, SERVER_PORT)