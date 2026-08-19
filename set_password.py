"""
Generates the environment variable values you should set before deploying
this app anywhere beyond your own machine.

Usage:
    python3 set_password.py "your-new-password"

Then set the two printed lines as real environment variables on whatever
host you're using (PythonAnywhere: Web tab -> "Environment variables";
Render: Environment tab; locally: export them in your shell before running
`python3 app.py`).
"""
import sys
import secrets
from werkzeug.security import generate_password_hash

if len(sys.argv) != 2:
    print("Usage: python3 set_password.py <your-new-password>")
    sys.exit(1)

password = sys.argv[1]
if len(password) < 8:
    print("Choose a password of at least 8 characters.")
    sys.exit(1)

print("\nSet these as environment variables wherever you run/host this app:\n")
print(f"ADMIN_USERNAME=admin")
print(f"ADMIN_PASSWORD_HASH={generate_password_hash(password)}")
print(f"SECRET_KEY={secrets.token_hex(32)}")
print("\n(Change ADMIN_USERNAME too if you don't want to log in as 'admin'.)\n")
