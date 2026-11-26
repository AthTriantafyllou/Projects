import os
import psycopg2
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer


#import passlib.handlers.bcrypt  # <-- πρόσθετο import

# --- Force pure-Python bcrypt backend (σταθερό για Alpine) ---
# passlib.handlers.bcrypt.bcrypt.set_backend("pybcrypt")

# --- CONFIG ---
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 ώρες

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Password helpers ---
def hash_password(password: str) -> str:
    if isinstance(password, str):
        password = password.encode("utf-8")[:72]
    else:
        password = password[:72]
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")[:72]
    else:
        plain_password = plain_password[:72]
    return pwd_context.verify(plain_password, hashed_password)

# --- JWT helpers ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


#----NEW

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_user_id_from_token(token: str = Depends(oauth2_scheme)):
    """
    Παίρνει το JWT από το Authorization header
    και επιστρέφει το user_id από το payload.
    """
    payload = decode_token(token)
    print("TOKEN PAYLOAD:", payload)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user_id")

    return user_id
