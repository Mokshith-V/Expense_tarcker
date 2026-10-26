"""Password hashing and JWT tokens. No FastAPI or database code here."""
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from .config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, username: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": str(user_id),   # the JWT standard says "sub" must be a string
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Returns the payload. Raises jose.JWTError if the token is invalid or expired."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
