import hashlib, os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
MAGIC=b"X8F1"
def key(secret): return hashlib.sha256(secret.encode()).digest()
def encrypt_bytes(data, secret):
    nonce=os.urandom(12); return MAGIC+nonce+AESGCM(key(secret)).encrypt(nonce,data,None)
def decrypt_bytes(data, secret):
    if not data.startswith(MAGIC): raise ValueError("bad encrypted payload")
    return AESGCM(key(secret)).decrypt(data[4:16],data[16:],None)
def encrypt_file(src,dst,secret): Path(dst).write_bytes(encrypt_bytes(Path(src).read_bytes(),secret))
def decrypt_file(src,dst,secret): Path(dst).write_bytes(decrypt_bytes(Path(src).read_bytes(),secret))
