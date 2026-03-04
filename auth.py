"""
Autenticación básica con JWT.

Flujo:
  1. POST /api/auth/token  →  { username, password }  →  { access_token, token_type }
  2. Endpoints protegidos reciben el header:  Authorization: Bearer <token>

Usuarios se definen en el .env como USERS_JSON:
  USERS_JSON='[{"username":"admin","password":"secret"},{"username":"viewer","password":"view123"}]'

Para producción reemplaza el dict en memoria por una tabla de usuarios en BD.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ─── Configuración ────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion-usa-openssl-rand")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 480))  # 8 horas

# Carga usuarios desde .env  (USERS_JSON)
_raw_users = os.environ.get(
    "USERS_JSON",
    '[{"username":"admin","password":"admin123"}]',
)
_user_list: list[dict] = json.loads(_raw_users)

# ─── Utilidades ───────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _verify_password(plain: str, hashed_or_plain: str) -> bool:
    """Soporta contraseñas en texto plano (dev) y bcrypt hash (prod)."""
    if hashed_or_plain.startswith("$2b$"):
        return pwd_context.verify(plain, hashed_or_plain)
    return plain == hashed_or_plain          # texto plano solo para dev


def _get_user(username: str) -> dict | None:
    for u in _user_list:
        if u["username"] == username:
            return u
    return None


def _create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─── Dependency ───────────────────────────────────────────────────────────────

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = _get_user(username)
    if user is None:
        raise credentials_exc
    return user


# Alias corto para usar como Depends en endpoints
CurrentUser = Annotated[dict, Depends(get_current_user)]

# ─── Schemas ──────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    expires_in_minutes: int


# ─── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Obtener JWT.  Enviar como form-data:  username + password.
    Desde el frontend puedes usar fetch con  Content-Type: application/x-www-form-urlencoded
    """
    user = _get_user(form_data.username)
    if not user or not _verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_access_token({"sub": user["username"]})
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.get("/me")
async def read_me(current_user: CurrentUser):
    """Verificar token y ver usuario actual."""
    return {"username": current_user["username"]}