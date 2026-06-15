from cryptography.hazmat.primitives.ciphers.aead import AESCCM
import os

#generate a aes 256 bit key - one time store this securely

key=AESCCM.generate_key(bit_length=256)
print(f"Key (32 bytes):{key.hex()}")

aesgcm=AESCCM(key)

nonce=os.urandom(12)

#encrypt the API KEY
plain_text=b"sk-my-secret-openai-api-key-12345"
ciphertext=aesgcm.encrypt(nonce,plain_text,None)
print(f"\nCiphertext: {ciphertext.hex()}")

#decrypt
decrypted = aesgcm.decrypt(nonce, ciphertext, None)
print(f"\nDecrypted: {decrypted.decode()}")

#tamper text 
tampered=bytearray(ciphertext)
tampered[0]^=0xFF

try:
    aesgcm.decrypt(nonce,bytes(tampered),None)
except Exception as e:
    print(f"\n Tamper detected:{type(e).__name__}")