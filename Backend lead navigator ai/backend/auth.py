from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt  # Direct bcrypt usage
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
from . import models, schemas
from .database import get_db

# Load environment variables
# load_dotenv(dotenv_path="../.env")
SECRET_KEY="bEQN1U7jkWA_ayKsVCbTT3cVMQgqBs84scCi6wRYtqs"
print(f"Loaded env - SECRET_KEY: {os.getenv('SECRET_KEY')}, ALGORITHM: {os.getenv('ALGORITHM')}, EXPIRY: {os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')}")

# SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 43200))

# OAuth2PasswordBearer for legacy compatibility
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt directly with 72-byte limit"""
    # Truncate to 72 bytes if necessary
    plain_bytes = plain_password.encode('utf-8')
    if len(plain_bytes) > 72:
        plain_bytes = plain_bytes[:72]
    
    # Ensure hashed_password is bytes
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    
    return bcrypt.checkpw(plain_bytes, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt directly with 72-byte limit"""
    # Truncate to 72 bytes if necessary
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Hash with bcrypt
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    
    # Return as UTF-8 string for database storage
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Existing function for header-based token (used by /auth/login)
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        print(f"Decoded token for email: {email}")  # Debug print
    except JWTError as e:
        print(f"JWT Error: {e}")  # Debug print
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        print(f"User not found for email: {email}")  # Debug print
        raise credentials_exception
    return user

# Existing function to check user activity
async def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# New function for query parameter-based token validation
def get_current_active_user_from_query(token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        print(f"Decoded query token for email: {email}")  # Debug print
    except JWTError as e:
        print(f"JWT Error: {e}")  # Debug print
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        print(f"User not found for email: {email}")  # Debug print
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def create_magic_link_token(email: str):
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode = {
        "sub": email,
        "type": "magic_link",  
        "exp": expire
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_magic_link_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")  # ← YE HONA CHAHIYE

        if not email or token_type != "magic_link":
            raise HTTPException(status_code=400, detail="Invalid magic link")

        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=400, detail="User not found")

        return user
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")