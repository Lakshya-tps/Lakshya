import sys
sys.path.append(r"d:\Lakshya\Block-Chain\Block-Chain\secure_identity_system\backend")
from database import get_all_encodings

admins = get_all_encodings("admin")
users = get_all_encodings("user")

print(f"Admins length: {len(admins)}")
for admin in admins:
    print(f"Admin: {admin['email']}")

print(f"Users length: {len(users)}")
for user in users:
    print(f"User: {user['email']}")
