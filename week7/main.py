from typing import Annotated
from fastapi import FastAPI,HTTPException,Depends
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from pydantic import BaseModel
import sys,os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'week5'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'week6'))
from query_routing import smart_rag

from auth import verify_token,create_access_token
from rbac import ROLE_PERMISSIONS, check_access_by_role

app=FastAPI(title="FilingsIQ API",version="1.0.0")
security=HTTPBearer()

#request/response models

class QueryRequest(BaseModel):
    question:str
    dataset:str="apple_10k"

class QueryResponse(BaseModel):
    question:str
    answer:str
    route:str
    confidence:str|None=None
    source_section:str|None=None

class LoginRequest(BaseModel):
    username:str
    password:str 

class TokenResponse(BaseModel):
    access_token:str
    token_type:str
    role:str

#auth dependency

def get_current_user(credentials:HTTPAuthorizationCredentials=Depends(security))->dict:
    token=credentials.credentials
    user=verify_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    return user

#endpoints
@app.get("/")
def root():
    return{"service":"FilingsIQ","status":"running","version":"1.0.0"}

@app.get("/health")
def health():
    return {"status":"healthy"}

@app.post("/token",response_model=TokenResponse)
def login(request:LoginRequest):
    users={
        "admin":{"password":"password123","role":"admin","user_id":1},
        "user":{"password":"password456","role":"user","user_id":2}
    }

    user_data=users.get(request.username)

    if not user_data or user_data["password"]!=request.password:
        raise HTTPException(status_code=401,detail="Invalid credentials")
    
    token=create_access_token(
        user_id=user_data["user_id"],
        username=request.username,
        role=user_data["role"]
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user_data["role"]
    )

@app.get("/me")
def get_me(user:dict=Depends(get_current_user)):
    return{
        "user_id":user["user_id"],
        "username":user["username"],
        "role":user["role"],
        "permissions":ROLE_PERMISSIONS.get(user["role"],[])
    }
@app.post("/query",response_model=QueryResponse)
def query(request:QueryRequest,user:Annotated[dict,Depends(get_current_user)]):

    role=user["role"]
    allowed,message=check_access_by_role(role,"read")

    if not allowed:
        raise HTTPException(status_code=403,detail=message)
    result=smart_rag(request.question)
    return QueryResponse(
        question=request.question,
        answer=result["answer"],
        route=result["route"],
        confidence=result.get("confidence"),
        source_section=result.get("source_section")
    )
@app.get("/permissions")
def get_permissions(user:dict=Depends(get_current_user)):
    role=user["role"]

    return {
        "role":role,
        "permissions":ROLE_PERMISSIONS.get(role,[]),
        "can_query":"read" in ROLE_PERMISSIONS.get(role,[]),
        "can_delete":"delete" in ROLE_PERMISSIONS.get(role,[])
    }

