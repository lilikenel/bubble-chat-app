import unittest
from networking.Server import *

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.host = "localhost"
        self.port = 5050
        self.server_socket = Server.start(self.host, self.port)

    def canConnectClient():
        s = Server()
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.host))
        except ConnectionRefusedError:
            self.fail
