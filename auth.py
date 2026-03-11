import os
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict  # NUEVO: ConfigDict
from sqlalchemy import text
from Database import AsyncSessionLocal

# ─── Configuración ────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion-usa-openssl-rand")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 480))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# ─── Utilidades de Password ───────────────────────────────────────────────────

def _verify_password(plain: str, hashed: str) -> bool:
    """Verifica contra MD5 o bcrypt."""
    plain_bytes = plain.encode('utf-8')
    
    # MD5 (32 hex chars) - Usado por restaurantes
    if len(hashed) == 32 and all(c in '0123456789abcdef' for c in hashed.lower()):
        return hashlib.md5(plain_bytes).hexdigest() == hashed.lower()
    
    # Bcrypt - Usado por admin
    if hashed.startswith("$2"):
        try:
            if len(plain_bytes) > 72:
                plain_bytes = plain_bytes[:72]
            return bcrypt.checkpw(plain_bytes, hashed.encode('utf-8'))
        except Exception as e:
            print(f"[DEBUG] Error bcrypt: {e}")
            return False
    
    return False


async def _get_user_from_db(username: str) -> dict | None:
    """Obtiene usuario desde la tabla USERS."""
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


# ─── Dependencies ─────────────────────────────────────────────────────────────

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


async def get_user_restaurant_filter(
    current_user: Annotated[dict, Depends(get_current_user)],
    requested_restaurant: Optional[str] = Query(None, alias="restaurant")
) -> dict:
    """Retorna el filtro de restaurante aplicable al usuario."""
    role = current_user.get("role", "restaurant")
    user_team_sk = current_user.get("unified_team_sk")
    
    print(f"[DEBUG] Filter check: user={current_user.get('username')}, role={role}, team_sk={user_team_sk}, requested={requested_restaurant}")
    
    if role == "admin":
        return {
            "can_view_all": True,
            "restaurant_filter": requested_restaurant if requested_restaurant and requested_restaurant != "all" else "all",
            "user": current_user
        }
    
    if role == "restaurant":
        if not user_team_sk:
            print(f"[ERROR] Usuario {current_user.get('username')} es restaurante pero no tiene unified_team_sk")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario de restaurante sin establecimiento asignado. Contacte al administrador."
            )
        
        if requested_restaurant and requested_restaurant != str(user_team_sk) and requested_restaurant != "all":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes permiso para ver el restaurante {requested_restaurant}"
            )
        
        return {
            "can_view_all": False,
            "restaurant_filter": str(user_team_sk),
            "user": current_user
        }
    
    raise HTTPException(status_code=403, detail="Rol no válido")


CurrentUser = Annotated[dict, Depends(get_current_user)]
RestaurantFilter = Annotated[dict, Depends(get_user_restaurant_filter)]

# ─── Schemas ──────────────────────────────────────────────────────────────────

class Token(BaseModel):
    # NUEVO: Configuración para incluir campos None en el JSON
    model_config = ConfigDict(exclude_none=False)
    
    access_token: str
    token_type: str
    username: str
    role: str
    unified_team_sk: Optional[str] = None
    can_view_all: bool
    expires_in_minutes: int


class UserInfo(BaseModel):
    # NUEVO: Configuración para incluir campos None en el JSON
    model_config = ConfigDict(exclude_none=False)
    
    username: str
    role: str
    unified_team_sk: Optional[str] = None
    can_view_all: bool


# ─── Router ───────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Login endpoint."""
    print(f"[DEBUG] Login attempt: username={form_data.username}")
    
    user = await _get_user_from_db(form_data.username)
    if not user:
        print(f"[DEBUG] User not found: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    password_valid = _verify_password(form_data.password, user["password"])
    print(f"[DEBUG] Password valid: {password_valid}")
    
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    role = user.get("role", "restaurant")
    
    if role == "restaurant" and not user.get("unified_team_sk"):
        print(f"[WARNING] Usuario {user['username']} es restaurante pero no tiene unified_team_sk asignado")
    
    token_data = {
        "sub": user["username"],
        "role": role,
        "unified_team_sk": user.get("unified_team_sk")
    }
    
    token = _create_access_token(token_data)
    
    print(f"[DEBUG] Login successful: {user['username']}, role={role}, team_sk={user.get('unified_team_sk')}")
    
    return Token(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=role,
        unified_team_sk=user.get("unified_team_sk"),  # Ahora se incluye en JSON aunque sea None
        can_view_all=(role == "admin"),
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
# Agregar al final de auth.py, antes del cierre

# ─── Schemas adicionales ──────────────────────────────────────────────────────

class UserListItem(BaseModel):
    model_config = ConfigDict(exclude_none=False)
    username: str
    role: str
    unified_team_sk: Optional[str] = None
    is_active: bool
    restaurant_name: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    target_username: str
    new_password: str


class PasswordChangeResponse(BaseModel):
    success: bool
    message: str


# ─── Admin Endpoints ─────────────────────────────────────────────────────────

@router.get("/admin/users", response_model=list[UserListItem])
async def list_users(current_user: CurrentUser):
    """Listar todos los usuarios (solo admin)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden ver la lista de usuarios"
        )
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT 
                    u.username, 
                    u.role, 
                    u.unified_team_sk, 
                    u.is_active,
                    r.restaurant_name
                FROM users u
                LEFT JOIN unified_restaurant_map r 
                    ON u.unified_team_sk = r.unified_team_sk
                ORDER BY 
                    CASE u.role WHEN 'admin' THEN 0 ELSE 1 END,
                    u.username
            """)
        )
        rows = result.fetchall()
        
        return [
            UserListItem(
                username=r.username,
                role=r.role or "restaurant",
                unified_team_sk=r.unified_team_sk,
                is_active=r.is_active,
                restaurant_name=r.restaurant_name
            )
            for r in rows
        ]


@router.post("/admin/users/reset-password", response_model=PasswordChangeResponse)
async def reset_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser
):
    """Cambiar contraseña de cualquier usuario (solo admin)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden cambiar contraseñas"
        )
    
    # Validar que la contraseña no esté vacía
    if not request.new_password or len(request.new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 4 caracteres"
        )
    
    async with AsyncSessionLocal() as session:
        # Verificar que el usuario objetivo existe
        check_result = await session.execute(
            text("SELECT username, role FROM users WHERE username = :username"),
            {"username": request.target_username}
        )
        target = check_result.fetchone()
        
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario '{request.target_username}' no encontrado"
            )
        
        # Generar hash según el rol del usuario objetivo
        # Admin usa bcrypt, restaurante usa MD5 (para compatibilidad)
        new_hash = ""
        if target.role == "admin":
            # Bcrypt para admins
            plain_bytes = request.new_password.encode('utf-8')
            if len(plain_bytes) > 72:
                plain_bytes = plain_bytes[:72]
            new_hash = bcrypt.hashpw(plain_bytes, bcrypt.gensalt(rounds=12)).decode('utf-8')
        else:
            # MD5 para restaurantes (mantener compatibilidad)
            new_hash = hashlib.md5(request.new_password.encode('utf-8')).hexdigest()
        
        # Actualizar contraseña
        await session.execute(
            text("""
                UPDATE users 
                SET password_hash = :new_hash,
                    updated_at = NOW()
                WHERE username = :username
            """),
            {
                "username": request.target_username,
                "new_hash": new_hash
            }
        )
        await session.commit()
        
        # Limpiar cache del usuario si existe
        try:
            cache = get_cache()
            # Invalidar cualquier cache relacionado con este usuario
            await cache.delete(f"restaurants_list:{request.target_username}")
        except Exception:
            pass
        
        print(f"[ADMIN] Password changed for {request.target_username} by {current_user['username']}")
        
        return PasswordChangeResponse(
            success=True,
            message=f"Contraseña de '{request.target_username}' actualizada exitosamente"
        )