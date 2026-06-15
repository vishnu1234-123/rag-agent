from auth import verify_token

ROLE_PERMISSIONS={
    "admin":["read","write","delete","manage_users"],
    "user":["read"],
    "guest":[]
}

def has_permission(role:str,action:str)->bool:
    return action in ROLE_PERMISSIONS.get(role,[])

def check_access(token:str,required_permission:str)->tuple[bool,str]:
    "returns (allowed,message)"
    decoded=verify_token(token)
    if decoded is None:
        return "Invalid or expired token"
    role=decoded.get("role")
    if has_permission(role,required_permission):
        return True,f"Access granted for role '{role}'"
    else:
        return False,f"Role '{role}' lacks permission '{required_permission}'"
