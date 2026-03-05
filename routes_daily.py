from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import text

from cache import get_cache
from Database import AsyncSessionLocal
from auth import RestaurantFilter, get_current_user, CurrentUser

router = APIRouter(prefix="/api", tags=["dashboard"])


# ============================================================
# HELPERS
# ============================================================

def date_to_date_id(d: datetime) -> int:
    """Convierte datetime a date_id (YYYYMMDD)"""
    return int(d.strftime("%Y%m%d"))

def date_id_to_date(date_id: int) -> datetime:
    """Convierte date_id a datetime"""
    return datetime.strptime(str(date_id), "%Y%m%d")

def get_week_range(date_id: int) -> tuple[int, int]:
    """Retorna inicio (lunes) y fin (domingo) de la semana"""
    d = date_id_to_date(date_id)
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return date_to_date_id(monday), date_to_date_id(sunday)

def get_month_range(date_id: int) -> tuple[int, int]:
    """Retorna inicio y fin del mes"""
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
            print(f"[DEBUG] restaurants_list for user: {current_user.get('username')}, team_sk: {user_team_sk}")
            
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
    Dashboard diario optimizado - solo lectura de tablas pre-calculadas
    """
    # Aplicar filtro de seguridad
    effective_restaurant = restaurant
    if restaurant_filter:
        if not restaurant_filter["can_view_all"]:
            effective_restaurant = restaurant_filter["restaurant_filter"]
            print(f"[DEBUG] Dashboard restricted to: {effective_restaurant}")
        else:
            print(f"[DEBUG] Admin view, restaurant param: {restaurant}")
    
    # Validar fecha
    try:
        hoy = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    except ValueError:
        raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")
    
    hoy_id = date_to_date_id(hoy)
    
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
        # Calcular fechas de comparación
        ayer = hoy - timedelta(days=1)
        hoy_sp = hoy - timedelta(days=7)
        ayer_sp = ayer - timedelta(days=7)
        
        ayer_id = date_to_date_id(ayer)
        hoy_sp_id = date_to_date_id(hoy_sp)
        ayer_sp_id = date_to_date_id(ayer_sp)
        
        sem_inicio, sem_fin = get_week_range(hoy_id)
        sem_pas_inicio, sem_pas_fin = get_week_range(hoy_sp_id)
        
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
                "preset": preset,
                "restaurant_filter": effective_restaurant,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                "charts": []
            },
        }

        if cache:
            try:
                await cache.set(cache_key, result, ttl=300)
            except Exception:
                pass

        return result


# ============================================================
# ENDPOINT: Product Mix (reemplaza a Detalle de Restaurantes)
# ============================================================

@router.get("/dashboard/productmix")
async def dashboard_product_mix(
    start_date: str = Query(...),
    end_date: str = Query(...),
    restaurant: str = Query("all"),
    restaurant_filter: RestaurantFilter = None
):
    """
    Product Mix: Ventas por producto en un rango de fechas
    Muestra: product_name, cantidad, total_usd, % peso del producto
    """
    # Aplicar filtro de seguridad
    effective_restaurant = restaurant
    if restaurant_filter:
        if not restaurant_filter["can_view_all"]:
            effective_restaurant = restaurant_filter["restaurant_filter"]
            print(f"[DEBUG] Product Mix restricted to: {effective_restaurant}")
        else:
            print(f"[DEBUG] Admin Product Mix, restaurant: {restaurant}")
    
    try:
        date_start = int(datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d"))
        date_end = int(datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d"))
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
                "total_products": len(table_data) - 1
            },
        }

        if cache:
            try:
                await cache.set(cache_key, response, ttl=300)
            except Exception:
                pass

        return response