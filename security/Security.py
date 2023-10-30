from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

"""
Class that will handle end-to-end encryption of messages.
"""
class Security:
    def __init__(self) -> None:
        pass

    def keygen(self) -> (RSAPrivateKey, RSAPublicKey):
        #TODO
        pass

    def encrypt(self, message: str, public_key: RSAPublicKey) -> bytes:
        #TODO
        pass

    def decrypt(self, encrypted_message: bytes, private_key: RSAPrivateKey) -> str:
        #TODO
        pass

    def validate(self, message: str, signature: bytes, public_key: RSAPublicKey) -> bool:
        #TODO
        pass

    def sign(self, message: str, private_key: RSAPrivateKey) -> bytes:
        #TODO
        pass
