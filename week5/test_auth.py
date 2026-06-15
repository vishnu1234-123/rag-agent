from auth import create_access_token,verify_token
import time

#valid token

token=create_access_token(user_id=1,username="vishnu",role="admin")
print(f"Valid token decode: {verify_token(token)}")

# expired token (set to expire in -1 minute, i.e. already expired)
expired_token = create_access_token(user_id=1, username="vishnu", role="admin", expires_minutes=-1)
print(f"Expired token decode: {verify_token(expired_token)}")

tampered = token[:-5] + "XXXXX"
print(f"Tampered token decode: {verify_token(tampered)}")