from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import text

from cache import get_cache
from Database import AsyncSessionLocal
from auth import RestaurantFilter, get_current_user, CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])


# ============================================================
# HELPERS - ZONA HORARIA CARACAS UTC-4
# ============================================================

# Caracas UTC-4 (no usa horario de verano)
CARACAS_OFFSET = timedelta(hours=-4)
CARACAS_TZ = timezone(CARACAS_OFFSET)


def get_caracas_now() -> datetime:
    """Obtiene la hora actual en zona Caracas UTC-4"""
    return datetime.now(CARACAS_TZ)


def date_to_date_id(d: datetime) -> int:
    """Convierte datetime a date_id (YYYYMMDD) en zona Caracas"""
    # Asegurar que la fecha esté en zona Caracas
    if d.tzinfo is None:
        d = d.replace(tzinfo=CARACAS_TZ)
    return int(d.strftime("%Y%m%d"))


def date_id_to_date(date_id: int) -> datetime:
    """Convierte date_id a datetime en zona Caracas"""
    d = datetime.strptime(str(date_id), "%Y%m%d")
    return d.replace(tzinfo=CARACAS_TZ)


def get_week_range(date_id: int) -> Tuple[int, int]:
    """Retorna inicio (lunes) y fin (domingo) de la semana en Caracas"""
    d = date_id_to_date(date_id)
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return date_to_date_id(monday), date_to_date_id(sunday)


def get_month_range(date_id: int) -> Tuple[int, int]:
    """Retorna inicio y fin del mes en Caracas"""
    d = date_id_to_date(date_id)
    start = d.replace(day=1)
    if d.month == 12:
        end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
    return date_to_date_id(start), date_to_date_id(end)


# ============================================================
# ENDPOINT: Restaurantes (con filtro de seguridad)
# ============================================================

@router.get("/restaurants")
async def restaurants_list(current_user: CurrentUser):
    """Lista de restaurantes desde unified_restaurant_map"""
    cache_key = f"restaurants_list:{current_user['username']}"
    
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit:
            return hit
    except Exception:
        cache = None

    async with AsyncSessionLocal() as session:
        # Si es admin, mostrar todos
        if current_user.get("role") == "admin":
            result = await session.execute(text("""
                SELECT unified_team_sk as id, restaurant_name as name, region, city_name
                FROM unified_restaurant_map
                WHERE is_active = TRUE
                ORDER BY restaurant_name
            """))
        else:
            # Para usuarios de restaurante: mostrar SOLO su restaurante
            user_team_sk = current_user.get("unified_team_sk")
            logger.debug("restaurants_list for user: %s, team_sk: %s", current_user.get('username'), user_team_sk)
            
            if not user_team_sk:
                return {"success": True, "data": []}  # No tiene restaurante asignado
            
            result = await session.execute(
                text("""
                    SELECT unified_team_sk as id, restaurant_name as name, region, city_name
                    FROM unified_restaurant_map
                    WHERE unified_team_sk = :team_sk AND is_active = TRUE
                    ORDER BY restaurant_name
                """),
                {"team_sk": user_team_sk}
            )
        
        rows = result.fetchall()
        
        response = {
            "success": True,
            "data": [{"id": r.id, "name": r.name, "region": r.region, "city": r.city_name} for r in rows]
        }
        
        if cache:
            await cache.set(cache_key, response, ttl=86400)
        return response


# ============================================================
# ENDPOINT: Daily Dashboard (con filtro de seguridad)
# ============================================================

@router.get("/dashboard/daily")
@router.get("/dashboard/ventas")
async def dashboard_daily(
    date: Optional[str] = Query(None),
    preset: str = Query("today"),
    restaurant: str = Query("all"),
    restaurant_filter: RestaurantFilter = None
):
    """
    Dashboard diario optimizado - zona horaria Caracas UTC-4
    """
    # Aplicar filtro de seguridad
    effective_restaurant = restaurant
    if restaurant_filter:
        if not restaurant_filter["can_view_all"]:
            effective_restaurant = restaurant_filter["restaurant_filter"]
            logger.debug("Dashboard restricted to: %s", effective_restaurant)
        else:
            logger.debug("Admin view, restaurant param: %s", restaurant)
    
    # Obtener fecha en zona Caracas
    now_caracas = get_caracas_now()
    
    if date:
        try:
            parsed = datetime.strptime(date, "%Y-%m-%d")
            hoy = parsed.replace(tzinfo=CARACAS_TZ)
            preset = "custom"
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")
    else:
        hoy = now_caracas
    
    hoy_id = date_to_date_id(hoy)
    
    logger.debug("Caracas now: %s", now_caracas.strftime('%Y-%m-%d %H:%M %z'))
    logger.debug("Effective date: %s", hoy.strftime('%Y-%m-%d'))
    logger.debug("Date ID: %s", hoy_id)
    
    # unified_team_sk para filtrar (None si es "all")
    unified_team_sk = None if effective_restaurant == "all" else effective_restaurant

    # Cache
    cache_key = hashlib.md5(f"daily:{hoy_id}:{effective_restaurant}:{restaurant_filter['user']['username'] if restaurant_filter else 'unknown'}".encode()).hexdigest()
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit:
            return hit
    except Exception:
        cache = None

    async with AsyncSessionLocal() as session:
        # Calcular fechas de comparación en zona Caracas
        
        # AYER: restar 1 día
        ayer = hoy - timedelta(days=1)
        ayer_id = date_to_date_id(ayer)
        
        # MISMO DÍA SEMANA PASADA: restar 7 días
        hoy_sp = hoy - timedelta(days=7)
        hoy_sp_id = date_to_date_id(hoy_sp)
        
        # AYER de la semana pasada: restar 8 días
        ayer_sp = hoy - timedelta(days=8)
        ayer_sp_id = date_to_date_id(ayer_sp)
        
        # Semanas
        sem_inicio, sem_fin = get_week_range(hoy_id)
        sem_pas_inicio, sem_pas_fin = get_week_range(hoy_sp_id)
        
        # Meses
        mes_inicio, mes_fin = get_month_range(hoy_id)
        mes_pas_date = hoy.replace(day=1) - timedelta(days=1)
        mes_pas_inicio, mes_pas_fin = get_month_range(date_to_date_id(mes_pas_date))

        # Query helper: obtener métricas de un día específico
        async def get_day_metrics(date_id: int):
            params = {"date_id": date_id}
            filter_team = ""
            if unified_team_sk:
                filter_team = "AND d.unified_team_sk = :team_sk"
                params["team_sk"] = unified_team_sk
            
            sql = text(f"""
                SELECT 
                    COALESCE(SUM(d.gmv), 0) as gmv,
                    COALESCE(SUM(d.trx), 0) as trx,
                    CASE WHEN SUM(d.trx) > 0 THEN ROUND(SUM(d.gmv)/SUM(d.trx), 2) ELSE 0 END as aov,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN b.pct_barquillas_combo IS NOT NULL 
                                THEN b.pct_barquillas_combo 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as barquilla_pct,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN c.pct_cambio_pz IS NOT NULL 
                                THEN c.pct_cambio_pz 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as cambio_pct,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN q.pct_queso IS NOT NULL 
                                THEN q.pct_queso 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as queso_pct,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN g.pct_gde IS NOT NULL 
                                THEN g.pct_gde 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as gde_pct,
                    COUNT(b.pct_barquillas_combo) as barquilla_count,
                    COUNT(c.pct_cambio_pz) as cambio_count,
                    COUNT(q.pct_queso) as queso_count,
                    COUNT(g.pct_gde) as gde_count
                FROM daily_metrics d
                LEFT JOIN barquilla_combo b ON d.date_id = b.date_id AND d.unified_team_sk = b.unified_team_sk
                LEFT JOIN cambio_pz c ON d.date_id = c.date_id AND d.unified_team_sk = c.unified_team_sk
                LEFT JOIN queso_metric q ON d.date_id = q.date_id AND d.unified_team_sk = q.unified_team_sk
                LEFT JOIN gde_metric g ON d.date_id = g.date_id AND d.unified_team_sk = g.unified_team_sk
                WHERE d.date_id = :date_id {filter_team}
            """)
            row = (await session.execute(sql, params)).fetchone()
            
            if row.gmv is None and row.trx is None:
                return {
                    "gmv": 0.0,
                    "trx": 0,
                    "aov": 0.0,
                    "barquilla": 0.0,
                    "cambio": 0.0,
                    "queso": 0.0,
                    "gde": 0.0
                }
            
            return {
                "gmv": float(row.gmv or 0),
                "trx": int(row.trx or 0),
                "aov": float(row.aov or 0),
                "barquilla": float(row.barquilla_pct or 0),
                "cambio": float(row.cambio_pct or 0),
                "queso": float(row.queso_pct or 0),
                "gde": float(row.gde_pct or 0)
            }

        # Query helper: métricas de delivery por tipo_delivery para un día o rango
        # IMPORTANTE: Ahora agrupa por tipo_delivery, filtra NULLs y resta IVA (16%)
        async def get_delivery_metrics(start_id: int, end_id: int) -> dict:
            """
            Retorna para tipo_pago='Delivery':
              - Una entrada por tipo_delivery (ARMI, PedidosYA, YUMMY, etc.)
              - GMV = amount_usd / 1.16 (descuento IVA 16%)
              - Excluye filas con tipo_delivery NULL
            """
            params_d = {"start": start_id, "end": end_id}
            filter_team_d = ""
            if unified_team_sk:
                filter_team_d = "AND unified_team_sk = :team_sk"
                params_d["team_sk"] = unified_team_sk

            sql_d = text(f"""
                SELECT
                    pm.tipo_delivery,
                    COALESCE(SUM(pm.amount_usd / 1.16), 0)  AS gmv,
                    COALESCE(SUM(pm.ordenes), 0)             AS trx
                FROM daily_payment_metrics pm
                WHERE pm.tipo_pago = 'Delivery'
                  AND pm.date_id BETWEEN :start AND :end
                  AND pm.tipo_delivery IS NOT NULL
                  {filter_team_d}
                GROUP BY pm.tipo_delivery
                ORDER BY SUM(pm.amount_usd / 1.16) DESC
            """)
            rows_d = (await session.execute(sql_d, params_d)).fetchall()

            methods = []
            total_gmv = 0.0
            total_trx = 0.0
            for r in rows_d:
                gmv = float(r.gmv or 0)
                trx = float(r.trx or 0)
                total_gmv += gmv
                total_trx += trx
                methods.append({
                    "name": r.tipo_delivery,
                    "gmv": gmv,
                    "trx": trx,
                    "aov": round(gmv / trx, 2) if trx > 0 else 0.0,
                })

            return {
                "methods": methods,
                "total": {
                    "gmv": round(total_gmv, 2),
                    "trx": total_trx,
                    "aov": round(total_gmv / total_trx, 2) if total_trx > 0 else 0.0,
                }
            }

        # Query helper: agregar por rango de fechas
        async def get_range_metrics(start_id: int, end_id: int):
            params = {"start": start_id, "end": end_id}
            filter_team = ""
            if unified_team_sk:
                filter_team = "AND d.unified_team_sk = :team_sk"
                params["team_sk"] = unified_team_sk
            
            sql = text(f"""
                SELECT 
                    COALESCE(SUM(d.gmv), 0) as gmv,
                    COALESCE(SUM(d.trx), 0) as trx,
                    CASE WHEN SUM(d.trx) > 0 THEN ROUND(SUM(d.gmv)/SUM(d.trx), 2) ELSE 0 END as aov,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN b.pct_barquillas_combo IS NOT NULL 
                                THEN b.pct_barquillas_combo 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as barquilla_pct,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN c.pct_cambio_pz IS NOT NULL 
                                THEN c.pct_cambio_pz 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as cambio_pct,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN q.pct_queso IS NOT NULL 
                                THEN q.pct_queso 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as queso_pct,
                    COALESCE(
                        AVG(
                            CASE 
                                WHEN g.pct_gde IS NOT NULL 
                                THEN g.pct_gde 
                                ELSE NULL 
                            END
                        ) * 100, 
                        0
                    ) as gde_pct
                FROM daily_metrics d
                LEFT JOIN barquilla_combo b ON d.date_id = b.date_id AND d.unified_team_sk = b.unified_team_sk
                LEFT JOIN cambio_pz c ON d.date_id = c.date_id AND d.unified_team_sk = c.unified_team_sk
                LEFT JOIN queso_metric q ON d.date_id = q.date_id AND d.unified_team_sk = q.unified_team_sk
                LEFT JOIN gde_metric g ON d.date_id = g.date_id AND d.unified_team_sk = g.unified_team_sk
                WHERE d.date_id BETWEEN :start AND :end {filter_team}
            """)
            row = (await session.execute(sql, params)).fetchone()
            
            if row.gmv is None:
                return {
                    "gmv": 0.0,
                    "trx": 0,
                    "aov": 0.0,
                    "barquilla": 0.0,
                    "cambio": 0.0,
                    "queso": 0.0,
                    "gde": 0.0
                }
            
            return {
                "gmv": float(row.gmv or 0),
                "trx": int(row.trx or 0),
                "aov": float(row.aov or 0),
                "barquilla": float(row.barquilla_pct or 0),
                "cambio": float(row.cambio_pct or 0),
                "queso": float(row.queso_pct or 0),
                "gde": float(row.gde_pct or 0)
            }

        # Obtener todas las métricas
        hoy_m = await get_day_metrics(hoy_id)
        hoy_sp_m = await get_day_metrics(hoy_sp_id)
        ayer_m = await get_day_metrics(ayer_id)
        ayer_sp_m = await get_day_metrics(ayer_sp_id)
        sem_m = await get_range_metrics(sem_inicio, sem_fin)
        sem_pas_m = await get_range_metrics(sem_pas_inicio, sem_pas_fin)
        mes_m = await get_range_metrics(mes_inicio, mes_fin)
        mes_pas_m = await get_range_metrics(mes_pas_inicio, mes_pas_fin)

        # Delivery: solo el período activo (la fecha seleccionada) y su GMV total
        deliv_hoy_m  = await get_delivery_metrics(hoy_id,  hoy_id)
        deliv_ayer_m = await get_delivery_metrics(ayer_id, ayer_id)

        # Helper para calcular diferencias
        def calc_diff(current, previous, tipo="gmv"):
            diff = current - previous
            pct = round((diff / previous) * 100, 1) if previous > 0 else 0.0
            return diff, pct

        def fmt_kpi(current, previous, nombre, comp, tipo="gmv"):
            diff, pct = calc_diff(current[tipo], previous[tipo])
            if tipo in ("gmv", "aov"):
                return {
                    "nombre": nombre, "comparacion": comp,
                    "valor": f"${current[tipo]:,.0f}",
                    "diff_monto": f"+${diff:,.0f}" if diff >= 0 else f"${diff:,.0f}",
                    "diff_pct": pct,
                    "trend": "up" if current[tipo] >= previous[tipo] else "down",
                }
            return {
                "nombre": nombre, "comparacion": comp,
                "valor": f"{int(current[tipo]):,}",
                "diff_monto": f"{int(diff):+,}",
                "diff_pct": pct,
                "trend": "up" if current[tipo] >= previous[tipo] else "down",
            }

        def fmt_sec(current, previous, nombre):
            diff = current - previous
            pct = (diff / previous * 100) if previous != 0 else 0
            return {
                "nombre": nombre,
                "valor": f"{current:.2f}%",
                "comparacion": "vs per. anterior",
                "diff_monto": f"{diff:+.2f}%",
                "diff_pct": round(abs(pct), 2),
                "trend": "up" if current >= previous else "down",
            }

        # Formatear respuesta
        hoy_sp_str = hoy_sp.strftime("%d/%m")
        ayer_sp_str = ayer_sp.strftime("%d/%m")
        mes_pasado_str = mes_pas_date.strftime("%b %Y")

        result = {
            "success": True,
            "meta": {
                "reference_date": hoy.strftime("%Y-%m-%d"),
                "caracas_time": now_caracas.strftime("%Y-%m-%d %H:%M %z"),
                "preset": preset,
                "restaurant_filter": effective_restaurant,
                "generated_at": get_caracas_now().strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": "America/Caracas (UTC-4)",
            },
            "data": {
                "kpis": [
                    {
                        "id": "gmv",
                        "title": "GMV (Ingresos)",
                        "icon": "fas fa-dollar-sign",
                        "color": "green",
                        "periodos": [
                            fmt_kpi(hoy_m, hoy_sp_m, "Hoy", f"vs {hoy_sp_str}", "gmv"),
                            fmt_kpi(ayer_m, ayer_sp_m, "Ayer", f"vs {ayer_sp_str}", "gmv"),
                            fmt_kpi(sem_m, sem_pas_m, "Semana", "vs semana pasada", "gmv"),
                            fmt_kpi(mes_m, mes_pas_m, "Mes", f"vs {mes_pasado_str}", "gmv"),
                        ]
                    },
                    {
                        "id": "trx",
                        "title": "TRX (Órdenes)",
                        "icon": "fas fa-receipt",
                        "color": "blue",
                        "periodos": [
                            fmt_kpi(hoy_m, hoy_sp_m, "Hoy", f"vs {hoy_sp_str}", "trx"),
                            fmt_kpi(ayer_m, ayer_sp_m, "Ayer", f"vs {ayer_sp_str}", "trx"),
                            fmt_kpi(sem_m, sem_pas_m, "Semana", "vs semana pasada", "trx"),
                            fmt_kpi(mes_m, mes_pas_m, "Mes", f"vs {mes_pasado_str}", "trx"),
                        ]
                    },
                    {
                        "id": "aov",
                        "title": "AOV (Ticket Promedio)",
                        "icon": "fas fa-calculator",
                        "color": "purple",
                        "periodos": [
                            fmt_kpi(hoy_m, hoy_sp_m, "Hoy", f"vs {hoy_sp_str}", "aov"),
                            fmt_kpi(ayer_m, ayer_sp_m, "Ayer", f"vs {ayer_sp_str}", "aov"),
                            fmt_kpi(sem_m, sem_pas_m, "Semana", "vs semana pasada", "aov"),
                            fmt_kpi(mes_m, mes_pas_m, "Mes", f"vs {mes_pasado_str}", "aov"),
                        ]
                    },
                ],
                "secondary_metrics": [
                    {
                        "id": "barquilla",
                        "title": "Barquilla Extra",
                        "icon": "fas fa-cookie",
                        "color": "orange",
                        "periodos": [
                            fmt_sec(hoy_m["barquilla"], hoy_sp_m["barquilla"], "Hoy"),
                            fmt_sec(ayer_m["barquilla"], ayer_sp_m["barquilla"], "Ayer"),
                            fmt_sec(sem_m["barquilla"], sem_pas_m["barquilla"], "Semana"),
                            fmt_sec(mes_m["barquilla"], mes_pas_m["barquilla"], "Mes"),
                        ]
                    },
                    {
                        "id": "cambio",
                        "title": "Cambio de Pieza",
                        "icon": "fas fa-exchange-alt",
                        "color": "cyan",
                        "periodos": [
                            fmt_sec(hoy_m["cambio"], hoy_sp_m["cambio"], "Hoy"),
                            fmt_sec(ayer_m["cambio"], ayer_sp_m["cambio"], "Ayer"),
                            fmt_sec(sem_m["cambio"], sem_pas_m["cambio"], "Semana"),
                            fmt_sec(mes_m["cambio"], mes_pas_m["cambio"], "Mes"),
                        ]
                    },
                    {
                        "id": "queso",
                        "title": "Queso Extra",
                        "icon": "fas fa-cheese",
                        "color": "yellow",
                        "periodos": [
                            fmt_sec(hoy_m["queso"], hoy_sp_m["queso"], "Hoy"),
                            fmt_sec(ayer_m["queso"], ayer_sp_m["queso"], "Ayer"),
                            fmt_sec(sem_m["queso"], sem_pas_m["queso"], "Semana"),
                            fmt_sec(mes_m["queso"], mes_pas_m["queso"], "Mes"),
                        ]
                    },
                    {
                        "id": "agrandado",
                        "title": "Agrandado",
                        "icon": "fas fa-expand-arrows-alt",
                        "color": "red",
                        "periodos": [
                            fmt_sec(hoy_m["gde"], hoy_sp_m["gde"], "Hoy"),
                            fmt_sec(ayer_m["gde"], ayer_sp_m["gde"], "Ayer"),
                            fmt_sec(sem_m["gde"], sem_pas_m["gde"], "Semana"),
                            fmt_sec(mes_m["gde"], mes_pas_m["gde"], "Mes"),
                        ]
                    },
                ],
                "charts": [],
                "delivery_metrics": _build_delivery_metrics(
                    deliv_hoy_m,  hoy_m["gmv"],
                    deliv_ayer_m, ayer_m["gmv"],
                    preset
                ),
            },
        }

        if cache:
            try:
                await cache.set(cache_key, result, ttl=300)
            except Exception:
                pass

        return result


# ============================================================
# HELPER: Construir delivery_metrics para la respuesta del dashboard daily
# ============================================================

def _build_delivery_metrics(
    active_d: dict,  gmv_active: float,
    prev_d:   dict,  gmv_prev:   float,
    preset:   str
) -> list:
    """
    Devuelve una lista de cards de Delivery para el frontend.
    Una card por tipo_delivery (ARMI, PedidosYA, YUMMY) + una card Total.

    Cada card:
    {
      "id":       str,
      "title":    str,
      "icon":     str,
      "color":    str,
      "is_total": bool,
      "gmv":      str,   # formateado "$1,234"
      "trx":      str,
      "aov":      str,
      "pct_gmv_total": float,   # % de este método vs GMV total del período
      "label_periodo":  str,    # "Hoy" | "Ayer" | fecha custom
    }
    """
    METHOD_META = {
        "ARMI":       {"icon": "fas fa-motorcycle",  "color": "blue"},
        "PedidosYA":  {"icon": "fas fa-box",          "color": "green"},
        "YUMMY":      {"icon": "fas fa-hamburger",    "color": "red"},
    }
    DEFAULT_META = {"icon": "fas fa-credit-card", "color": "blue"}

    # Etiqueta legible según el preset activo
    label = "Hoy" if preset in ("today", "custom") else "Ayer"

    # Período fuente: si el usuario eligió "yesterday", mostramos ayer_d
    src = prev_d if preset == "yesterday" else active_d
    gmv_total = gmv_prev if preset == "yesterday" else gmv_active

    def _fmt_card(method_name: str, gmv: float, trx: float, aov: float, is_total: bool) -> dict:
        pct = round((gmv / gmv_total) * 100, 1) if gmv_total > 0 else 0.0
        meta = METHOD_META.get(method_name, DEFAULT_META) if not is_total else {
            "icon": "fas fa-motorcycle", "color": "orange"
        }
        return {
            "id":            "delivery_total" if is_total else f"delivery_{method_name.lower().replace(' ', '_')}",
            "title":         "Delivery Total" if is_total else method_name,
            "icon":          meta["icon"],
            "color":         meta["color"],
            "is_total":      is_total,
            "gmv":           f"${gmv:,.0f}",
            "trx":           f"{int(trx):,}",
            "aov":           f"${aov:,.2f}",
            "pct_gmv_total": pct,
            "label_periodo": label,
        }

    cards = []

    # Sub-cards por método (orden fijo: ARMI, PYA/Pedidos Ya, YUMMY)
    ORDER = ["ARMI", "PedidosYA", "YUMMY"]
    methods_sorted = sorted(
        src["methods"],
        key=lambda m: ORDER.index(m["name"]) if m["name"] in ORDER else 99
    )
    for m in methods_sorted:
        cards.append(_fmt_card(m["name"], m["gmv"], m["trx"], m["aov"], is_total=False))

    # Card de total
    t = src["total"]
    cards.append(_fmt_card("__total__", t["gmv"], t["trx"], t["aov"], is_total=True))

    return cards


# ============================================================
# ENDPOINT: Product Mix
# ============================================================

@router.get("/dashboard/productmix")
async def dashboard_product_mix(
    start_date: str = Query(...),
    end_date: str = Query(...),
    restaurant: str = Query("all"),
    restaurant_filter: RestaurantFilter = None
):
    """
    Product Mix: Ventas por producto en un rango de fechas (zona Caracas)
    """
    # Aplicar filtro de seguridad
    effective_restaurant = restaurant
    if restaurant_filter:
        if not restaurant_filter["can_view_all"]:
            effective_restaurant = restaurant_filter["restaurant_filter"]
            logger.debug("Product Mix restricted to: %s", effective_restaurant)
        else:
            logger.debug("Admin Product Mix, restaurant: %s", restaurant)
    
    try:
        # Convertir fechas usando zona Caracas
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=CARACAS_TZ)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=CARACAS_TZ)
        date_start = int(start_dt.strftime("%Y%m%d"))
        date_end = int(end_dt.strftime("%Y%m%d"))
    except ValueError:
        raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")

    cache_key = hashlib.md5(f"productmix:{date_start}:{date_end}:{effective_restaurant}:{restaurant_filter['user']['username'] if restaurant_filter else 'unknown'}".encode()).hexdigest()
    
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit:
            return hit
    except Exception:
        cache = None

    async with AsyncSessionLocal() as session:
        restaurant_filter_sql = ""
        params = {"start": date_start, "end": date_end}
        
        if effective_restaurant and effective_restaurant != "all":
            restaurant_filter_sql = "AND pm.unified_team_sk = :restaurant"
            params["restaurant"] = effective_restaurant

        # Query principal: agregar ventas por producto
        sql = text(f"""
            SELECT 
                COALESCE(p.producto_final, p.product_name, pm.product_sk_n) AS product_name,
                COALESCE(p.category_name, 'Sin Categoría') AS category_name,
                SUM(pm.cantidad) AS cantidad,
                SUM(pm.total_price_subtotal_usd) AS total_usd
            FROM product_mix_daily pm
            LEFT JOIN dim_product p ON pm.product_sk_n = p.product_sk_n
            WHERE pm.date_id BETWEEN :start AND :end
            {restaurant_filter_sql}
            GROUP BY COALESCE(p.producto_final, p.product_name, pm.product_sk_n), 
                     COALESCE(p.category_name, 'Sin Categoría')
            HAVING SUM(pm.total_price_subtotal_usd) > 0
            ORDER BY SUM(pm.total_price_subtotal_usd) DESC
        """)
        
        result = await session.execute(sql, params)
        rows = result.fetchall()

        # Calcular total para porcentajes
        total_gmv = sum(float(r.total_usd or 0) for r in rows)
        
        # Preparar datos con porcentaje
        table_data = []
        for row in rows:
            gmv = float(row.total_usd or 0)
            qty = int(row.cantidad or 0)
            pct_weight = round((gmv / total_gmv) * 100, 2) if total_gmv > 0 else 0
            
            table_data.append({
                "product_name": row.product_name,
                "category_name": row.category_name,
                "cantidad": qty,
                "total_usd": round(gmv, 2),
                "pct_weight": pct_weight
            })

        # Fila de totales
        if table_data:
            total_qty = sum(r["cantidad"] for r in table_data)
            table_data.append({
                "product_name": "** TOTAL **",
                "category_name": "",
                "cantidad": total_qty,
                "total_usd": round(total_gmv, 2),
                "pct_weight": 100.0,
                "isTotal": True
            })

        response = {
            "success": True,
            "data": {
                "table": table_data,
                "period": {"start": start_date, "end": end_date},
                "restaurant_filter": effective_restaurant,
                "total_products": len(table_data) - 1,
                "timezone": "America/Caracas (UTC-4)"
            },
        }

        if cache:
            try:
                await cache.set(cache_key, response, ttl=300)
            except Exception:
                pass

        return response


# ============================================================
# ENDPOINT: Ventas por Hora
# ============================================================

@router.get("/dashboard/hours")
async def dashboard_hours(
    start_date: str = Query(...),
    end_date: str = Query(...),
    restaurant: str = Query("all"),
    restaurant_filter: RestaurantFilter = None
):
    """
    Ventas por Hora: Análisis de ventas por período del día (zona Caracas)
    """
    # Aplicar filtro de seguridad
    effective_restaurant = restaurant
    if restaurant_filter:
        if not restaurant_filter["can_view_all"]:
            effective_restaurant = restaurant_filter["restaurant_filter"]
            logger.debug("Hours restricted to: %s", effective_restaurant)
        else:
            logger.debug("Admin Hours, restaurant: %s", restaurant)
    
    try:
        # Convertir fechas usando zona Caracas
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=CARACAS_TZ)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=CARACAS_TZ)
        date_start = int(start_dt.strftime("%Y%m%d"))
        date_end = int(end_dt.strftime("%Y%m%d"))
    except ValueError:
        raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")

    cache_key = hashlib.md5(f"hours:{date_start}:{date_end}:{effective_restaurant}:{restaurant_filter['user']['username'] if restaurant_filter else 'unknown'}".encode()).hexdigest()
    
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit:
            return hit
    except Exception:
        cache = None

    async with AsyncSessionLocal() as session:
        restaurant_filter_sql = ""
        params = {"start": date_start, "end": date_end}
        
        if effective_restaurant and effective_restaurant != "all":
            restaurant_filter_sql = "AND sh.unified_team_sk = :restaurant"
            params["restaurant"] = effective_restaurant

        # Query: Datos por hora para el gráfico de líneas
        hourly_sql = text(f"""
            SELECT 
                sh.hora,
                SUM(sh.total_ordenes) AS total_ordenes,
                SUM(sh.total_ventas_usd) AS total_ventas_usd
            FROM sales_by_hour sh
            WHERE sh.date_id BETWEEN :start AND :end
            {restaurant_filter_sql}
            GROUP BY sh.hora
            ORDER BY sh.hora
        """)
        
        hourly_result = await session.execute(hourly_sql, params)
        hourly_rows = hourly_result.fetchall()

        # Query: Datos agregados por período para la tabla
        period_sql = text(f"""
            WITH period_data AS (
                SELECT 
                    CASE 
                        WHEN sh.hora >= 11 AND sh.hora < 15 THEN 'Almuerzo'
                        WHEN sh.hora >= 15 AND sh.hora < 18 THEN 'Media Tarde'
                        WHEN sh.hora >= 18 AND sh.hora < 22 THEN 'Cena'
                        WHEN sh.hora >= 22 OR sh.hora < 1 THEN 'Late Night'
                        ELSE 'Otro'
                    END AS periodo,
                    sh.total_ordenes,
                    sh.total_ventas_usd,
                    sh.date_id
                FROM sales_by_hour sh
                WHERE sh.date_id BETWEEN :start AND :end
                {restaurant_filter_sql}
            )
            SELECT 
                periodo,
                SUM(total_ordenes) AS total_ordenes,
                SUM(total_ventas_usd) AS total_ventas_usd,
                COUNT(DISTINCT date_id) AS dias_con_ventas
            FROM period_data
            WHERE periodo != 'Otro'
            GROUP BY periodo
            ORDER BY 
                CASE periodo
                    WHEN 'Almuerzo' THEN 1
                    WHEN 'Media Tarde' THEN 2
                    WHEN 'Cena' THEN 3
                    WHEN 'Late Night' THEN 4
                END
        """)
        
        period_result = await session.execute(period_sql, params)
        period_rows = period_result.fetchall()

        # Preparar datos para gráfico de líneas (todas las horas 0-23)
        hours_chart = []
        sales_chart = []
        orders_chart = []
        
        # Crear mapa de horas existentes
        hourly_map = {row.hora: row for row in hourly_rows}
        
        for h in range(24):
            row = hourly_map.get(h)
            hours_chart.append(f"{h:02d}:00")
            sales_chart.append(float(row.total_ventas_usd) if row else 0)
            orders_chart.append(int(row.total_ordenes) if row else 0)

        # Preparar datos de períodos para tabla
        period_data = []
        total_ordenes_all = 0
        total_ventas_all = 0
        
        period_colors = {
            'Almuerzo': '#f59e0b',      # Naranja
            'Media Tarde': '#3b82f6',   # Azul
            'Cena': '#10b981',          # Verde
            'Late Night': '#8b5cf6'     # Púrpura
        }
        
        for row in period_rows:
            ordenes = int(row.total_ordenes or 0)
            ventas = float(row.total_ventas_usd or 0)
            dias = int(row.dias_con_ventas or 0)
            
            total_ordenes_all += ordenes
            total_ventas_all += ventas
            
            period_data.append({
                "periodo": row.periodo,
                "horario": get_period_hours(row.periodo),
                "total_ordenes": ordenes,
                "total_ventas_usd": round(ventas, 2),
                "promedio_diario": round(ventas / max(dias, 1), 2),
                "color": period_colors.get(row.periodo, '#6b7280'),
                "dias": dias
            })

        # Calcular porcentajes de período
        for p in period_data:
            p['pct_del_total'] = round((p['total_ventas_usd'] / total_ventas_all) * 100, 1) if total_ventas_all > 0 else 0

        # Fila de totales
        if period_data:
            total_dias = max(p['dias'] for p in period_data)
            period_data.append({
                "periodo": "** TOTAL **",
                "horario": "",
                "total_ordenes": total_ordenes_all,
                "total_ventas_usd": round(total_ventas_all, 2),
                "promedio_diario": round(total_ventas_all / max(total_dias, 1), 2),
                "pct_del_total": 100.0,
                "color": "#1e293b",
                "isTotal": True
            })

        response = {
            "success": True,
            "data": {
                "chart": {
                    "hours": hours_chart,
                    "sales": sales_chart,
                    "orders": orders_chart
                },
                "periods_table": period_data,
                "period": {"start": start_date, "end": end_date},
                "restaurant_filter": effective_restaurant,
                "timezone": "America/Caracas (UTC-4)"
            },
        }

        if cache:
            try:
                await cache.set(cache_key, response, ttl=300)
            except Exception:
                pass

        return response


def get_period_hours(periodo: str) -> str:
    """Retorna el rango de horas para cada período"""
    horarios = {
        'Almuerzo': '11:00 - 15:00',
        'Media Tarde': '15:00 - 18:00',
        'Cena': '18:00 - 22:00',
        'Late Night': '22:00 - 01:00'
    }
    return horarios.get(periodo, '')
# ============================================================================
# NUEVO ENDPOINT: VENTA POR CAJA (Sales by POS/Register)
# ============================================================================

@router.get("/dashboard/salesbyregister")
async def dashboard_sales_by_register(
    date: Optional[str] = Query(None),
    preset: str = Query("today"),
    restaurant: str = Query("all"),
    restaurant_filter: RestaurantFilter = None
):
    """
    Dashboard de Venta por Caja/POS.

    La fecha que llega en `date` ES el día activo que se quiere mostrar.
    El frontend es responsable de calcular la fecha correcta según el preset:
      - today     → envía la fecha de hoy
      - yesterday → envía la fecha de ayer
      - custom    → envía la fecha seleccionada

    El backend usa esa fecha como día activo y calcula los períodos de
    comparación (día anterior, semana, mes) relativos a ella.
    """
    # Aplicar filtro de seguridad
    effective_restaurant = restaurant
    if restaurant_filter:
        if not restaurant_filter["can_view_all"]:
            effective_restaurant = restaurant_filter["restaurant_filter"]
            logger.debug("SalesByRegister restricted to: %s", effective_restaurant)
        else:
            logger.debug("Admin SalesByRegister, restaurant: %s", restaurant)

    # Obtener fecha en zona Caracas
    now_caracas = get_caracas_now()

    if date:
        try:
            parsed = datetime.strptime(date, "%Y-%m-%d")
            # La fecha recibida ES el día activo — no aplicar ningún offset por preset
            dia_activo = parsed.replace(tzinfo=CARACAS_TZ)
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")
    else:
        # Sin fecha → usar hoy en Caracas
        dia_activo = now_caracas

    hoy_id = date_to_date_id(dia_activo)

    logger.debug("SalesByRegister - preset=%s, dia_activo=%s, hoy_id=%s", preset, dia_activo.strftime('%Y-%m-%d'), hoy_id)

    # unified_team_sk para filtrar
    unified_team_sk = None if effective_restaurant == "all" else effective_restaurant

    # Cache — key incluye la fecha activa real (ya calculada por el frontend)
    cache_key = hashlib.md5(f"salesbyregister:{hoy_id}:{effective_restaurant}:{restaurant_filter['user']['username'] if restaurant_filter else 'unknown'}".encode()).hexdigest()
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit:
            return hit
    except Exception:
        cache = None

    async with AsyncSessionLocal() as session:
        # Calcular períodos de comparación relativos al día activo
        ayer = dia_activo - timedelta(days=1)
        ayer_id = date_to_date_id(ayer)
        sem_inicio, sem_fin = get_week_range(hoy_id)
        mes_inicio, mes_fin = get_month_range(hoy_id)

        # Query helper: métricas por caja para un período
        async def get_caja_metrics(start_id: int, end_id: int, period_label: str):
            params = {"start": start_id, "end": end_id}
            filter_team = ""
            if unified_team_sk:
                filter_team = "AND sm.unified_team_sk = :team_sk"
                params["team_sk"] = unified_team_sk
            
            # El JOIN a dim_pos_session se resuelve en un subquery ANTES del GROUP BY.
            #
            # Problema: pos_config_category_name puede ser NULL en una sesión de un día
            # concreto aunque la misma caja tenga categoría en otros días (dim_pos_session
            # tiene una fila por sesión por día). Unir solo por session_sk_n del día exacto
            # produce la tarjeta "Sin Categoría" incorrectamente.
            #
            # Solución: si la categoría del día exacto es NULL, se busca el valor más
            # reciente no-NULL para esa caja en toda la dimensión (mismo unified_team_sk
            # + mismo nombre de caja). Solo cae en "Sin Categoría" si realmente no existe
            # ningún valor histórico para esa caja.
            sql = text(f"""
                SELECT
                    caja_name,
                    pos_config_category_name,
                    COALESCE(SUM(gmv), 0) as gmv,
                    COALESCE(SUM(trx), 0) as trx,
                    CASE WHEN SUM(trx) > 0 THEN ROUND(SUM(gmv)/SUM(trx), 2) ELSE 0 END as aov
                FROM (
                    SELECT
                        sm.gmv,
                        sm.trx,
                        COALESCE(NULLIF(s.caja, ''), s.session_name, 'Sin Nombre') as caja_name,
                        COALESCE(
                            s.pos_config_category_name,
                            (
                                SELECT s2.pos_config_category_name
                                FROM dim_pos_session s2
                                WHERE s2.unified_team_sk = sm.unified_team_sk
                                  AND COALESCE(NULLIF(s2.caja, ''), s2.session_name) =
                                      COALESCE(NULLIF(s.caja,  ''), s.session_name)
                                  AND s2.pos_config_category_name IS NOT NULL
                                ORDER BY s2.date_id DESC
                                LIMIT 1
                            ),
                            'Sin Categoría'
                        ) as pos_config_category_name
                    FROM daily_metrics_by_session sm
                    LEFT JOIN dim_pos_session s
                        ON s.session_sk_n    = sm.session_sk_n
                        AND s.unified_team_sk = sm.unified_team_sk
                    WHERE sm.date_id BETWEEN :start AND :end {filter_team}
                ) base
                GROUP BY caja_name, pos_config_category_name
                HAVING SUM(gmv) > 0 OR SUM(trx) > 0
                ORDER BY SUM(gmv) DESC
            """)
            rows = (await session.execute(sql, params)).fetchall()
            
            return {
                "period": period_label,
                "cajas": [
                    {
                        "caja": r.caja_name,
                        "category": r.pos_config_category_name or "Sin Categoría",
                        "gmv": float(r.gmv or 0),
                        "trx": int(r.trx or 0),
                        "aov": float(r.aov or 0)
                    }
                    for r in rows
                ],
                "totals": {
                    "gmv": sum(float(r.gmv or 0) for r in rows),
                    "trx": sum(int(r.trx or 0) for r in rows),
                    "aov": sum(float(r.aov or 0) for r in rows) / max(len(rows), 1)
                }
            }

        # Obtener datos de todos los períodos
        hoy_data = await get_caja_metrics(hoy_id, hoy_id, "Hoy")
        ayer_data = await get_caja_metrics(ayer_id, ayer_id, "Ayer")
        sem_data = await get_caja_metrics(sem_inicio, sem_fin, "Esta Semana")
        mes_data = await get_caja_metrics(mes_inicio, mes_fin, "Este Mes")

        # Preparar datos para el chart de barras agrupadas
        # Estructura: labels = nombres de cajas, datasets = períodos con GMV/TRX/AOV
        
        # Obtener todas las cajas únicas del período actual (Hoy)
        all_cajas = [c["caja"] for c in hoy_data["cajas"]] if hoy_data["cajas"] else ["Sin datos"]
        
        # Si no hay cajas hoy, usar las de ayer
        if not all_cajas or all_cajas == ["Sin datos"]:
            all_cajas = [c["caja"] for c in ayer_data["cajas"]] if ayer_data["cajas"] else ["Sin datos"]
        
        # Función para obtener valor de una caja en un período específico
        def get_caja_value(caja_name, period_data, metric):
            for c in period_data["cajas"]:
                if c["caja"] == caja_name:
                    return c[metric]
            return 0

        # Preparar datasets para el chart principal (barras agrupadas por período)
        chart_data = {
            "labels": all_cajas,
            "datasets": {
                "gmv": {
                    "hoy": [get_caja_value(c, hoy_data, "gmv") for c in all_cajas],
                    "ayer": [get_caja_value(c, ayer_data, "gmv") for c in all_cajas],
                    "semana": [get_caja_value(c, sem_data, "gmv") for c in all_cajas],
                    "mes": [get_caja_value(c, mes_data, "gmv") for c in all_cajas]
                },
                "trx": {
                    "hoy": [get_caja_value(c, hoy_data, "trx") for c in all_cajas],
                    "ayer": [get_caja_value(c, ayer_data, "trx") for c in all_cajas],
                    "semana": [get_caja_value(c, sem_data, "trx") for c in all_cajas],
                    "mes": [get_caja_value(c, mes_data, "trx") for c in all_cajas]
                },
                "aov": {
                    "hoy": [get_caja_value(c, hoy_data, "aov") for c in all_cajas],
                    "ayer": [get_caja_value(c, ayer_data, "aov") for c in all_cajas],
                    "semana": [get_caja_value(c, sem_data, "aov") for c in all_cajas],
                    "mes": [get_caja_value(c, mes_data, "aov") for c in all_cajas]
                }
            }
        }

        # El día activo siempre es el que llegó en `date` (calculado por el frontend).
        # El período anterior siempre es el día inmediatamente anterior.
        active_data = hoy_data
        prev_data = ayer_data

        # Agregar por categoría usando el período activo
        category_totals = {}
        for c in active_data["cajas"]:
            cat = c["category"] or "Sin Categoría"
            if cat not in category_totals:
                category_totals[cat] = {"gmv": 0, "trx": 0}
            category_totals[cat]["gmv"] += c["gmv"]
            category_totals[cat]["trx"] += c["trx"]

        # Totales del período activo — fuente de verdad que cuadra con Daily Sales
        total_gmv = active_data["totals"]["gmv"]
        total_trx = active_data["totals"]["trx"]

        # Totales del período anterior por categoría (para comparación en tarjetas)
        prev_category_totals = {}
        for c in prev_data["cajas"]:
            cat = c["category"] or "Sin Categoría"
            if cat not in prev_category_totals:
                prev_category_totals[cat] = {"gmv": 0, "trx": 0}
            prev_category_totals[cat]["gmv"] += c["gmv"]
            prev_category_totals[cat]["trx"] += c["trx"]

        prev_total_gmv = prev_data["totals"]["gmv"]
        prev_total_trx = prev_data["totals"]["trx"]

        category_donuts = []
        colors = [
            "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
            "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"
        ]

        for idx, (cat, values) in enumerate(category_totals.items()):
            # Porcentajes sobre el total real del período activo → siempre suman 100%
            pct_gmv = round((values["gmv"] / max(total_gmv, 1)) * 100, 1)
            pct_trx = round((values["trx"] / max(total_trx, 1)) * 100, 1)
            prev_vals = prev_category_totals.get(cat, {"gmv": 0, "trx": 0})
            gmv_diff = values["gmv"] - prev_vals["gmv"]
            trx_diff = values["trx"] - prev_vals["trx"]
            gmv_diff_pct = round((gmv_diff / max(prev_vals["gmv"], 1)) * 100, 1)
            trx_diff_pct = round((trx_diff / max(prev_vals["trx"], 1)) * 100, 1)
            aov = round(values["gmv"] / max(values["trx"], 1), 2)

            category_donuts.append({
                "category": cat,
                "gmv": round(values["gmv"], 2),
                "trx": values["trx"],
                "aov": aov,
                "pct_gmv": pct_gmv,
                "pct_trx": pct_trx,
                "gmv_diff": round(gmv_diff, 2),
                "trx_diff": trx_diff,
                "gmv_diff_pct": gmv_diff_pct,
                "trx_diff_pct": trx_diff_pct,
                "gmv_trend": "up" if gmv_diff >= 0 else "down",
                "trx_trend": "up" if trx_diff >= 0 else "down",
                "color": colors[idx % len(colors)],
                "is_total": False
            })

        # Ordenar por GMV descendente
        category_donuts.sort(key=lambda x: x["gmv"], reverse=True)

        # Tarjeta TOTAL al final — la suma de todas las tarjetas debe coincidir
        # exactamente con el GMV/TRX que muestra Daily Sales para el mismo período
        total_gmv_diff = round(total_gmv - prev_total_gmv, 2)
        total_trx_diff = total_trx - prev_total_trx
        category_donuts.append({
            "category": "TOTAL",
            "gmv": round(total_gmv, 2),
            "trx": total_trx,
            "aov": round(total_gmv / max(total_trx, 1), 2),
            "pct_gmv": 100.0,
            "pct_trx": 100.0,
            "gmv_diff": total_gmv_diff,
            "trx_diff": total_trx_diff,
            "gmv_diff_pct": round((total_gmv_diff / max(prev_total_gmv, 1)) * 100, 1),
            "trx_diff_pct": round((total_trx_diff / max(prev_total_trx, 1)) * 100, 1),
            "gmv_trend": "up" if total_gmv_diff >= 0 else "down",
            "trx_trend": "up" if total_trx_diff >= 0 else "down",
            "color": "#374151",
            "is_total": True
        })

        # Preparar datos para tabla detallada — usa el mismo período activo que las tarjetas
        table_data = []
        for c in active_data["cajas"]:
            prev_caja = next((p for p in prev_data["cajas"] if p["caja"] == c["caja"]), None)
            gmv_diff = c["gmv"] - (prev_caja["gmv"] if prev_caja else 0)
            trx_diff = c["trx"] - (prev_caja["trx"] if prev_caja else 0)

            table_data.append({
                "caja": c["caja"],
                "category": c["category"],
                "gmv": c["gmv"],
                "trx": c["trx"],
                "aov": c["aov"],
                "gmv_diff": gmv_diff,
                "trx_diff": trx_diff,
                "gmv_trend": "up" if gmv_diff >= 0 else "down",
                "trx_trend": "up" if trx_diff >= 0 else "down"
            })

        result = {
            "success": True,
            "meta": {
                "reference_date": dia_activo.strftime("%Y-%m-%d"),
                "caracas_time": now_caracas.strftime("%Y-%m-%d %H:%M %z"),
                "preset": preset,
                "restaurant_filter": effective_restaurant,
                "timezone": "America/Caracas (UTC-4)",
                "total_cajas": len(all_cajas),
                "total_categories": len(category_donuts)
            },
            "data": {
                "chart_main": chart_data,  # Datos para barras agrupadas
                "category_donuts": category_donuts,  # Datos para donuts
                "table": table_data,  # Datos para tabla detallada
                "summary": {
                    "hoy": hoy_data["totals"],
                    "ayer": ayer_data["totals"],
                    "semana": sem_data["totals"],
                    "mes": mes_data["totals"]
                }
            }
        }

        if cache:
            try:
                await cache.set(cache_key, result, ttl=300)
            except Exception:
                pass

        return result