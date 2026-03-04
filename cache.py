"""
cache.py  —  Wrapper de caché usando aiocache + Redis.

Uso en endpoints:
    from cache import cached, get_cache

    @router.get("/mi-endpoint")
    @cached(ttl=300, key="mi_endpoint:{param}")
    async def mi_endpoint(param: str):
        ...
"""

import os
import json
import hashlib
import functools
from typing import Callable, Optional

from aiocache import Cache
from aiocache.serializers import JsonSerializer

_cache: Optional[Cache] = None

REDIS_URL = os.environ.get("CACHE_REDIS_URL", "redis://localhost:6379/0")


async def init_cache():
    """Inicializar la conexion al cache. Llamar en el lifespan de FastAPI."""
    global _cache
    try:
        _cache = Cache.from_url(REDIS_URL)
        _cache.serializer = JsonSerializer()
        # Verificar conexion
        await _cache.set("_ping", "pong", ttl=5)
        result = await _cache.get("_ping")
        if result != "pong":
            raise RuntimeError("Redis no responde correctamente")
        print("  Redis conectado correctamente")
    except Exception as e:
        print(f"  Redis no disponible ({e}). Usando cache en memoria.")
        _cache = Cache(Cache.MEMORY)
        _cache.serializer = JsonSerializer()


def get_cache() -> Cache:
    """Obtener instancia del cache."""
    if _cache is None:
        raise RuntimeError("Cache no inicializado. Llama a init_cache() primero.")
    return _cache


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorador de cache para endpoints FastAPI async.
    
    Genera la cache key automaticamente desde el nombre de la funcion
    y los argumentos del request (query params).
    
    Uso:
        @router.get("/dashboard/daily")
        @cached(ttl=300, key_prefix="daily")
        async def dashboard_daily(date: str = "today", ...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Construir cache key desde prefix + kwargs relevantes
            # Filtramos los objetos no serializables (db session, current_user)
            serializable_kwargs = {}
            for k, v in kwargs.items():
                try:
                    json.dumps(v)
                    serializable_kwargs[k] = v
                except (TypeError, ValueError):
                    pass  # Ignorar objetos como AsyncSession, dict de usuario
            
            key_data = f"{key_prefix or func.__name__}:{json.dumps(serializable_kwargs, sort_keys=True)}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Intentar obtener del cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Ejecutar funcion y guardar resultado
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl=ttl)
            return result
        
        return wrapper
    return decorator