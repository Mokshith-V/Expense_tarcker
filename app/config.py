"""Settings, read from environment variables (or a .env file).

Secrets such as the database password and the JWT key live in .env,
never in the source code.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # copies the values from .env into os.environ (existing env vars win)


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


DATABASE_URL: str = _required("DATABASE_URL")
# Optional: path to the CA certificate of a hosted MySQL that requires SSL
# (e.g. Aiven's ca.pem), relative to the project folder. Leave unset for local MySQL.
DATABASE_SSL_CA: str | None = os.getenv("DATABASE_SSL_CA") or None
SECRET_KEY: str = _required("SECRET_KEY")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
