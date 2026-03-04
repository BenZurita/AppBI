import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import text
from Database import AsyncSessionLocal

# ─── Configuración ────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion-usa-openssl-rand")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 480))

# ─── Utilidades ───────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _verify_password(plain: str, hashed: str) -> bool:
    """Verifica contra MD5 o bcrypt."""
    # Bcrypt
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return pwd_context.verify(plain, hashed)
    # MD5 (32 hex chars)
    if len(hashed) == 32 and all(c in '0123456789abcdef' for c in hashed.lower()):
        return hashlib.md5(plain.encode()).hexdigest() == hashed.lower()
    return False


async def _get_user_from_db(username: str) -> dict | None:
    """
    Obtiene usuario desde la tabla USERS.
    Ahora usa unified_team_sk en lugar de restaurant_code.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT username, password_hash, unified_team_sk, role, is_active 
                FROM users 
                WHERE username = :username AND is_active = TRUE
            """),
            {"username": username}
        )
        row = result.fetchone()
        if row:
            return {
                "username": row.username,
                "password": row.password_hash,
                "role": row.role or "restaurant",
                "unified_team_sk": row.unified_team_sk,
                "is_active": row.is_active
            }
        return None


def _create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─── Dependency: Usuario actual ───────────────────────────────────────────────

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

    user = await _get_user_from_db(username)
    if user is None:
        raise credentials_exc
    return user


# ─── Dependency: Verificar acceso a restaurante ─────────────────────────────────

async def get_user_restaurant_filter(
    current_user: Annotated[dict, Depends(get_current_user)],
    requested_restaurant: Optional[str] = Query(None, alias="restaurant")
) -> dict:
    """
    Retorna el filtro de restaurante aplicable al usuario.
    Admin puede ver todo, restaurant user solo el suyo (por unified_team_sk).
    """
    role = current_user.get("role", "restaurant")
    user_team_sk = current_user.get("unified_team_sk")
    
    if role == "admin":
        return {
            "can_view_all": True,
            "restaurant_filter": requested_restaurant if requested_restaurant and requested_restaurant != "all" else "all",
            "user": current_user
        }
    
    if role == "restaurant":
        if requested_restaurant and requested_restaurant != str(user_team_sk) and requested_restaurant != "all":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes permiso para ver el restaurante {requested_restaurant}"
            )
        return {
            "can_view_all": False,
            "restaurant_filter": str(user_team_sk) if user_team_sk else None,
            "user": current_user
        }
    
    raise HTTPException(status_code=403, detail="Rol no válido")


# Alias cortos para Depends
CurrentUser = Annotated[dict, Depends(get_current_user)]
RestaurantFilter = Annotated[dict, Depends(get_user_restaurant_filter)]

# ─── Schemas ──────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str
    unified_team_sk: Optional[str] = None
    expires_in_minutes: int


class UserInfo(BaseModel):
    username: str
    role: str
    unified_team_sk: Optional[str] = None
    can_view_all: bool


# ─── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Login: 
    - Admin: username='admin', password='admin123'
    - Restaurante: username=código_restaurante, password=código_restaurante x 2
    """
    user = await _get_user_from_db(form_data.username)
    if not user or not _verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = {
        "sub": user["username"],
        "role": user.get("role", "restaurant"),
        "unified_team_sk": user.get("unified_team_sk")
    }
    
    token = _create_access_token(token_data)
    
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=token_data["role"],
        unified_team_sk=token_data["unified_team_sk"],
        expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.get("/me", response_model=UserInfo)
async def read_me(current_user: CurrentUser):
    """Verificar token y obtener info del usuario actual."""
    role = current_user.get("role", "restaurant")
    unified_team_sk = current_user.get("unified_team_sk")
    
    return UserInfo(
        username=current_user["username"],
        role=role,
        unified_team_sk=unified_team_sk,
        can_view_all=(role == "admin")
    )