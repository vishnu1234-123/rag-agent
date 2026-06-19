import jwt
import datetime
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

SECRET_KEY=os.getenv("JWT_SECRET_KEY")
ALGORITHM="HS256"


#create a token
def create_access_token(user_id:int,username:str,role:str,expires_minutes:int=60)->str:
    payload={
        "user_id":user_id,
        "username":username,
        "role":role,
        "exp":datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=expires_minutes)
    }
    return jwt.encode(payload,SECRET_KEY,algorithm=ALGORITHM)



#decode 

def verify_token(token:str)->dict|None:
    try:
        return jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        print("Token exppired")
        return None
    except jwt.InvalidTokenError:
        print("Invalid token")
        return None 
    


