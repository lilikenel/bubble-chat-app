from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

class User():
    private_key = None # RSAPrivateKey()
    public_key = None # RSAPublicKey()
    user_name = None # str
    user_id = None # UUID()

    def __init__(self) -> None:
        pass