from auth import create_access_token
from rbac import check_access

admin_token = create_access_token(user_id=1, username="vishnu", role="admin")
user_token  = create_access_token(user_id=2, username="guest_user", role="user")

print("admin trying delete:", check_access(admin_token, "delete"))
print("user trying delete: ", check_access(user_token, "delete"))
print("user trying read:   ", check_access(user_token, "read"))
print("admin trying read:  ", check_access(admin_token, "read"))