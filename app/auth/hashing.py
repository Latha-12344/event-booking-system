"""
Password hashing using bcrypt directly.

passlib 1.7.4 is incompatible with bcrypt 5.x (missing __about__.__version__).
We call bcrypt directly to avoid the passlib wrapper entirely.
"""
import bcrypt


def get_password_hash(plain_password: str) -> str:
    """Return bcrypt hash of the plain-text password."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plain-text password matches the stored hash."""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)
