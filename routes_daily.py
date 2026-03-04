"""
routes_daily.py — Endpoints de dashboard (FastAPI async)
"""

from __future__ import annotations

import asyncio
import hashlib
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from cache import get_cache
from Database import engine

router = APIRouter(prefix="/api", tags=["dashboard"])


# =============================================================================
# CONTEXT MANAGER
# =============================================================================

@asynccontextmanager
async def _new_conn():
    async with engine.connect() as conn:
        yield conn


# =============================================================================
# QUERIES SQL - Construcción dinámica según team_sk
# =============================================================================

def _build_gmv_query(has_team_sk: bool, is_range: bool) -> str:
    """Construye query GMV según si hay filtro de team_sk."""
    date_filter = "fol.date_id BETWEEN :inicio AND :fin" if is_range else "fol.date_id = :date_id"
    team_filter = "AND fol.team_sk = :team_sk" if has_team_sk else ""
    
    return f"""
        SELECT SUM(CASE
            WHEN fol.date_id < 20250601 THEN
                CASE WHEN dp.group_name ILIKE '%%Delivery%%' OR dp.group_name ILIKE '%%IGTF%%'
                     THEN 0.0 ELSE fol.price_subtotal_usd END
            ELSE fol.price_subtotal_usd
        END) AS gmv
        FROM fact_order_line fol
        LEFT JOIN dim_product dp ON fol.product_sk_n = dp.product_sk_n
        WHERE {date_filter}
        {team_filter}
    """


def _build_trx_query(has_team_sk: bool, is_range: bool) -> str:
    """Construye query TRX según si hay filtro de team_sk."""
    date_filter = "date_id BETWEEN :inicio AND :fin" if is_range else "date_id = :date_id"
    team_filter = "AND team_sk_n = :team_sk" if has_team_sk else ""
    
    return f"""
        SELECT COUNT(DISTINCT order_sk_n) AS trx
        FROM pos_order_complete
        WHERE {date_filter}
        {team_filter}
    """


def _build_secondary_query(table: str, column: str, has_team_sk: bool, is_range: bool) -> str:
    """Construye query para métricas secundarias."""
    date_filter = "date_id BETWEEN :inicio AND :fin" if is_range else "date_id = :inicio"
    team_filter = f"AND team_sk = :team_sk" if has_team_sk else ""
    
    return f"""
        SELECT AVG({column}) AS avg_val FROM {table}
        WHERE {date_filter}
        {team_filter}
    """


def _build_monthly_trend_query(has_team_sk: bool) -> str:
    """Construye query de tendencia mensual."""
    team_filter = "AND fol.team_sk = :team_sk" if has_team_sk else ""
    
    return f"""
        SELECT
            SUBSTRING(date_id::text, 1, 6) AS year_month,
            SUM(CASE
                WHEN fol.date_id < 20250601 THEN
                    CASE WHEN dp.group_name ILIKE '%%Delivery%%' OR dp.group_name ILIKE '%%IGTF%%'
                         THEN 0.0 ELSE fol.price_subtotal_usd END
                ELSE fol.price_subtotal_usd
            END) AS gmv
        FROM fact_order_line fol
        LEFT JOIN dim_product dp ON fol.product_sk_n = dp.product_sk_n
        WHERE fol.date_id BETWEEN :start_date AND :end_date
        {team_filter}
        GROUP BY SUBSTRING(date_id::text, 1, 6)
        ORDER BY year_month ASC
    """


# =============================================================================
# HELPERS
# =============================================================================

async def _gmv_trx_day(date_id: int, team_sk: str | None) -> dict:
    has_team = team_sk is not None
    
    async with _new_conn() as conn:
        gmv_sql = text(_build_gmv_query(has_team, False))
        trx_sql = text(_build_trx_query(has_team, False))
        
        params = {"date_id": date_id}
        if has_team:
            params["team_sk"] = team_sk
        
        g = (await conn.execute(gmv_sql, params)).fetchone()
        t = (await conn.execute(trx_sql, params)).fetchone()
        
        gmv = float(g.gmv or 0)
        trx = int(t.trx or 0)
        return {"gmv": gmv, "trx": trx, "aov": round(gmv / max(trx, 1), 2)}


async def _gmv_trx_range(inicio: int, fin: int, team_sk: str | None) -> dict:
    has_team = team_sk is not None
    
    async with _new_conn() as conn:
        gmv_sql = text(_build_gmv_query(has_team, True))
        trx_sql = text(_build_trx_query(has_team, True))
        
        params = {"inicio": inicio, "fin": fin}
        if has_team:
            params["team_sk"] = team_sk
        
        g = (await conn.execute(gmv_sql, params)).fetchone()
        t = (await conn.execute(trx_sql, params)).fetchone()
        
        gmv = float(g.gmv or 0)
        trx = int(t.trx or 0)
        return {"gmv": gmv, "trx": trx, "aov": round(gmv / max(trx, 1), 2)}


async def _secondary_metric(table: str, column: str, inicio: int, fin: int | None, team_sk: str | None) -> float:
    has_team = team_sk is not None
    is_range = fin is not None
    
    async with _new_conn() as conn:
        try:
            sql = text(_build_secondary_query(table, column, has_team, is_range))
            
            params = {"inicio": inicio}
            if is_range:
                params["fin"] = fin
            if has_team:
                params["team_sk"] = team_sk
            
            row = (await conn.execute(sql, params)).fetchone()
            return float(row.avg_val or 0)
        except Exception as exc:
            print(f"[WARN] {table}.{column}: {exc}")
            return 0.0


async def _secondary_all_periods(table: str, column: str, fechas: dict, team_sk: str | None) -> dict:
    keys = [
        ("hoy",       fechas["hoy"],            None),
        ("hoy_sp",    fechas["hoy_sp"],          None),
        ("ayer",      fechas["ayer"],             None),
        ("ayer_sp",   fechas["ayer_sp"],          None),
        ("sem",       fechas["sem_inicio"],       fechas["sem_fin"]),
        ("sem_pas",   fechas["sem_pas_inicio"],   fechas["sem_pas_fin"]),
        ("mes",       fechas["mes_inicio"],       fechas["mes_fin"]),
        ("mes_pas",   fechas["mes_pas_inicio"],   fechas["mes_pas_fin"]),
    ]
    values = await asyncio.gather(*[
        _secondary_metric(table, column, inicio, fin, team_sk)
        for _, inicio, fin in keys
    ])
    return {k: v for (k, _, __), v in zip(keys, values)}


async def _monthly_trend(hoy: datetime, team_sk: str | None) -> dict:
    start_current = datetime(hoy.year - 1, 1, 1)
    end_current   = hoy
    start_last    = datetime(hoy.year - 2, 1, 1)
    end_last      = datetime(hoy.year - 1, hoy.month, min(hoy.day, 28))

    has_team = team_sk is not None

    async def _fetch(start: datetime, end: datetime):
        async with _new_conn() as conn:
            sql = text(_build_monthly_trend_query(has_team))
            
            params = {
                "start_date": int(start.strftime("%Y%m%d")),
                "end_date":   int(end.strftime("%Y%m%d")),
            }
            if has_team:
                params["team_sk"] = team_sk
            
            res = await conn.execute(sql, params)
            return {r.year_month: float(r.gmv or 0) for r in res.fetchall()}

    data_cur, data_last = await asyncio.gather(
        _fetch(start_current, end_current),
        _fetch(start_last, end_last),
    )

    months, ty_vals, ly_vals = [], [], []
    current = start_current
    while current <= end_current:
        ym    = current.strftime("%Y%m")
        ly_ym = (current - timedelta(days=365)).strftime("%Y%m")
        months.append(current.strftime("%b %Y"))
        ty_vals.append(data_cur.get(ym, 0))
        ly_vals.append(data_last.get(ly_ym, 0))
        current = (datetime(current.year + 1, 1, 1) if current.month == 12
                   else datetime(current.year, current.month + 1, 1))

    return {
        "labels": months,
        "datasets": [
            {"label": f"{hoy.year-1}-{hoy.year}", "data": ty_vals,
             "borderColor": "#3b82f6", "backgroundColor": "rgba(59,130,246,0.1)",
             "borderWidth": 3, "pointRadius": 4, "tension": 0.3, "fill": True},
            {"label": f"{hoy.year-2}-{hoy.year-1}", "data": ly_vals,
             "borderColor": "#94a3b8", "backgroundColor": "rgba(148,163,184,0.1)",
             "borderWidth": 2, "pointRadius": 3, "tension": 0.3,
             "borderDash": [5, 5], "fill": False},
        ],
    }


# =============================================================================
# FORMATO
# =============================================================================

def _calc_diff(act, ant):
    diff = act - ant
    pct  = round((diff / ant) * 100, 1) if ant > 0 else 0.0
    return diff, pct

def _fmt_kpi(d, d_sp, nombre, comp, tipo="gmv"):
    val  = d[tipo]
    val2 = d_sp[tipo]
    diff, pct = _calc_diff(val, val2)
    if tipo in ("gmv", "aov"):
        return {
            "nombre": nombre, "comparacion": comp,
            "valor":      f"${val:,.0f}",
            "diff_monto": f"+${diff:,.0f}" if diff >= 0 else f"${diff:,.0f}",
            "diff_pct":   pct,
            "trend":      "up" if val >= val2 else "down",
        }
    return {
        "nombre": nombre, "comparacion": comp,
        "valor":      f"{int(val):,}",
        "diff_monto": f"{int(diff):+,}",
        "diff_pct":   pct,
        "trend":      "up" if val >= val2 else "down",
    }

def _format_trend(data, key_act, key_ant):
    act  = data[key_act] * 100
    ant  = data[key_ant] * 100
    diff = act - ant
    pct  = (diff / ant * 100) if ant != 0 else 0
    return {
        "valor":       f"{act:.2f}%",
        "comparacion": "vs per. anterior",
        "diff_monto":  f"{diff:+.2f}%",
        "diff_pct":    round(abs(pct), 2),
        "trend":       "up" if act >= ant else "down",
    }


# =============================================================================
# ENDPOINT: Restaurantes
# =============================================================================

@router.get("/restaurants")
async def restaurants_list():
    cache_key = "restaurants_list"
    cache = None
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit is not None:
            return hit
    except Exception:
        cache = None

    try:
        async with _new_conn() as conn:
            rows = (await conn.execute(text("""
                SELECT DISTINCT team_sk_n, team_name FROM dim_team
                WHERE team_name IS NOT NULL ORDER BY team_name
            """))).fetchall()
            
        response = {
            "success": True,
            "data": [{"id": r.team_sk_n, "name": r.team_name} for r in rows if r.team_name],
        }
        if cache:
            await cache.set(cache_key, response, ttl=86400)
        return response
    except Exception as exc:
        print(f"[ERROR] restaurants_list: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# ENDPOINT: Daily Dashboard
# =============================================================================

@router.get("/dashboard/daily")
@router.get("/dashboard/ventas")
async def dashboard_daily(
    date:       Optional[str] = Query(None),
    preset:     str           = Query("today"),
    restaurant: str           = Query("all"),
):
    # Validación de fecha
    try:
        hoy = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    
    team_sk = None if restaurant == "all" else restaurant

    # Cache
    cache_key = hashlib.md5(f"daily:{date}:{preset}:{restaurant}".encode()).hexdigest()
    cache = None
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit is not None:
            return hit
    except Exception:
        cache = None

    try:
        # Cálculo de fechas
        ayer           = hoy - timedelta(days=1)
        inicio_semana  = hoy - timedelta(days=6)
        inicio_mes     = hoy.replace(day=1)
        hoy_sp         = hoy - timedelta(days=7)
        ayer_sp        = ayer - timedelta(days=7)
        inicio_sem_pas = inicio_semana - timedelta(days=7)

        try:
            if hoy.month == 1:
                inicio_mes_pas = inicio_mes.replace(year=hoy.year-1, month=12)
                fin_mes_pas    = hoy.replace(year=hoy.year-1, month=12, day=min(hoy.day, 31))
            else:
                inicio_mes_pas = inicio_mes.replace(month=inicio_mes.month-1)
                ultimo_dia     = (inicio_mes - timedelta(days=1)).day
                fin_mes_pas    = hoy.replace(month=hoy.month-1, day=min(hoy.day, ultimo_dia))
        except ValueError:
            inicio_mes_pas = hoy - timedelta(days=60)
            fin_mes_pas    = hoy - timedelta(days=30)

        def di(d): return int(d.strftime("%Y%m%d"))

        fechas = {
            "hoy":            di(hoy),
            "hoy_sp":         di(hoy_sp),
            "ayer":           di(ayer),
            "ayer_sp":        di(ayer_sp),
            "sem_inicio":     di(inicio_semana),
            "sem_fin":        di(hoy),
            "sem_pas_inicio": di(inicio_sem_pas),
            "sem_pas_fin":    di(hoy_sp),
            "mes_inicio":     di(inicio_mes),
            "mes_fin":        di(hoy),
            "mes_pas_inicio": di(inicio_mes_pas),
            "mes_pas_fin":    di(fin_mes_pas),
        }

        # Ejecutar todas las queries en paralelo
        (
            hoy_d, hoy_sp_d, ayer_d, ayer_sp_d,
            sem_d, sem_pas_d, mes_d, mes_pas_d,
            barq, cambio, queso, agrand, chart,
        ) = await asyncio.gather(
            _gmv_trx_day  (fechas["hoy"],            team_sk),
            _gmv_trx_day  (fechas["hoy_sp"],         team_sk),
            _gmv_trx_day  (fechas["ayer"],            team_sk),
            _gmv_trx_day  (fechas["ayer_sp"],         team_sk),
            _gmv_trx_range(fechas["sem_inicio"],     fechas["sem_fin"],       team_sk),
            _gmv_trx_range(fechas["sem_pas_inicio"], fechas["sem_pas_fin"],   team_sk),
            _gmv_trx_range(fechas["mes_inicio"],     fechas["mes_fin"],       team_sk),
            _gmv_trx_range(fechas["mes_pas_inicio"], fechas["mes_pas_fin"],   team_sk),
            _secondary_all_periods("barquilla_combo", "pct_barquillas_combo", fechas, team_sk),
            _secondary_all_periods("cambio_pz",       "pct_cambio_pz",        fechas, team_sk),
            _secondary_all_periods("queso_metric",    "pct_queso",            fechas, team_sk),
            _secondary_all_periods("gde_metric",      "pct_gde",              fechas, team_sk),
            _monthly_trend(hoy, team_sk),
        )

        # Formato de respuesta
        hoy_sp_str     = hoy_sp.strftime("%d/%m")
        ayer_sp_str    = ayer_sp.strftime("%d/%m")
        mes_pasado_str = inicio_mes_pas.strftime("%b %Y")

        def periodos_kpi(tipo):
            return [
                _fmt_kpi(hoy_d,  hoy_sp_d,  "Hoy",    f"vs {hoy_sp_str}",    tipo),
                _fmt_kpi(ayer_d, ayer_sp_d, "Ayer",   f"vs {ayer_sp_str}",   tipo),
                _fmt_kpi(sem_d,  sem_pas_d, "Semana", "vs semana pasada",     tipo),
                _fmt_kpi(mes_d,  mes_pas_d, "Mes",    f"vs {mes_pasado_str}", tipo),
            ]

        def periodos_sec(data):
            return [
                {"nombre": "Hoy",    **_format_trend(data, "hoy",  "hoy_sp")},
                {"nombre": "Ayer",   **_format_trend(data, "ayer", "ayer_sp")},
                {"nombre": "Semana", **_format_trend(data, "sem",  "sem_pas")},
                {"nombre": "Mes",    **_format_trend(data, "mes",  "mes_pas")},
            ]

        result = {
            "success": True,
            "meta": {
                "reference_date": hoy.strftime("%Y-%m-%d"),
                "preset": preset,
                "restaurant_filter": restaurant,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "data": {
                "kpis": [
                    {"id": "gmv",  "title": "GMV (Ingresos)",       "icon": "fas fa-dollar-sign", "color": "green",  "periodos": periodos_kpi("gmv")},
                    {"id": "trx",  "title": "TRX (Órdenes)",        "icon": "fas fa-receipt",     "color": "blue",   "periodos": periodos_kpi("trx")},
                    {"id": "aov",  "title": "AOV (Ticket Promedio)", "icon": "fas fa-calculator",  "color": "purple", "periodos": periodos_kpi("aov")},
                ],
                "secondary_metrics": [
                    {"id": "barquilla", "title": "Barquilla Extra",  "icon": "fas fa-cookie",            "color": "orange", "periodos": periodos_sec(barq)},
                    {"id": "cambio",    "title": "Cambio de Pieza",  "icon": "fas fa-exchange-alt",      "color": "cyan",   "periodos": periodos_sec(cambio)},
                    {"id": "queso",     "title": "Queso Extra",      "icon": "fas fa-cheese",            "color": "yellow", "periodos": periodos_sec(queso)},
                    {"id": "agrandado", "title": "Agrandado",        "icon": "fas fa-expand-arrows-alt", "color": "red",    "periodos": periodos_sec(agrand)},
                ],
                "charts": [{"title": "Tendencia Mensual - Facturación", "type": "line", "data": chart}],
            },
        }

        if cache:
            try: 
                await cache.set(cache_key, result, ttl=300)
            except Exception: 
                pass

        return result

    except Exception as exc:
        print(f"[ERROR] dashboard_daily: {exc}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail={
            "error": str(exc), "traceback": traceback.format_exc()
        })


# =============================================================================
# ENDPOINT: Detalle de Restaurantes
# =============================================================================

@router.get("/dashboard/restaurants")
async def dashboard_restaurants(
    start_date:  str       = Query(...),
    end_date:    str       = Query(...),
    restaurants: list[str] = Query(default=["all"]),
):
    # Validación de fechas
    try:
        date_start = int(datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d"))
        date_end   = int(datetime.strptime(end_date,   "%Y-%m-%d").strftime("%Y%m%d"))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )

    _rkey     = ":".join(sorted(restaurants))
    cache_key = hashlib.md5(f"restaurants:{start_date}:{end_date}:{_rkey}".encode()).hexdigest()
    cache = None
    try:
        cache = get_cache()
        hit = await cache.get(cache_key)
        if hit is not None:
            return hit
    except Exception:
        cache = None

    try:
        use_all     = not restaurants or "all" in restaurants
        rest_filter = "" if use_all else "AND dt.team_sk_n = ANY(:restaurants)"
        params: dict = {"start_date": date_start, "end_date": date_end}
        if not use_all:
            params["restaurants"] = restaurants

        sql_main = text(f"""
            SELECT dt.team_name AS restaurant,
                SUM(CASE
                    WHEN fol.date_id < 20250601 THEN
                        CASE WHEN dp.group_name ILIKE '%%Delivery%%' OR dp.group_name ILIKE '%%IGTF%%'
                             THEN 0.0 ELSE fol.price_subtotal_usd END
                    ELSE fol.price_subtotal_usd
                END) AS gmv,
                COUNT(DISTINCT fol.order_sk_n) AS trx
            FROM fact_order_line fol
            LEFT JOIN dim_product dp ON fol.product_sk_n = dp.product_sk_n
            LEFT JOIN dim_team dt    ON fol.team_sk = dt.team_sk_n
            WHERE fol.date_id BETWEEN :start_date AND :end_date
            {rest_filter}
            GROUP BY dt.team_name
            HAVING SUM(CASE
                WHEN fol.date_id < 20250601 THEN
                    CASE WHEN dp.group_name ILIKE '%%Delivery%%' OR dp.group_name ILIKE '%%IGTF%%'
                         THEN 0.0 ELSE fol.price_subtotal_usd END
                ELSE fol.price_subtotal_usd
            END) > 0
            ORDER BY gmv DESC
        """)

        sql_sec = text(f"""
            SELECT dt.team_name AS restaurant,
                AVG(bc.pct_barquillas_combo) AS barquilla,
                AVG(cp.pct_cambio_pz)        AS cambio,
                AVG(qm.pct_queso)            AS queso,
                AVG(gm.pct_gde)              AS agrandado
            FROM dim_team dt
            LEFT JOIN barquilla_combo bc ON dt.team_sk_n = bc.team_sk AND bc.date_id BETWEEN :start_date AND :end_date
            LEFT JOIN cambio_pz       cp ON dt.team_sk_n = cp.team_sk AND cp.date_id BETWEEN :start_date AND :end_date
            LEFT JOIN queso_metric    qm ON dt.team_sk_n = qm.team_sk AND qm.date_id BETWEEN :start_date AND :end_date
            LEFT JOIN gde_metric      gm ON dt.team_sk_n = gm.team_sk AND gm.date_id BETWEEN :start_date AND :end_date
            WHERE EXISTS (
                SELECT 1 FROM fact_order_line fol
                WHERE fol.team_sk = dt.team_sk_n
                AND fol.date_id BETWEEN :start_date AND :end_date
            )
            {rest_filter}
            GROUP BY dt.team_name
        """)

        async with _new_conn() as conn:
            rows_main = (await conn.execute(sql_main, params)).fetchall()
            rows_sec  = (await conn.execute(sql_sec,  params)).fetchall()

        # ✅ CORREGIDO: Convertir Decimal a float en el mapeo
        sec_map = {
            r.restaurant: {
                "barquilla": float(r.barquilla or 0) * 100,
                "cambio":    float(r.cambio    or 0) * 100,
                "queso":     float(r.queso     or 0) * 100,
                "agrandado": float(r.agrandado or 0) * 100,
            }
            for r in rows_sec
        }

        table_data = []
        total_gmv = total_trx = 0.0
        # ✅ CORREGIDO: Inicializar como float, no como 0.0 (ya era float, pero ahora sec_map también tiene floats)
        totals = {"barquilla": 0.0, "cambio": 0.0, "queso": 0.0, "agrandado": 0.0}
        count  = 0

        for row in rows_main:
            gmv = float(row.gmv or 0)
            trx = int(row.trx or 0)
            aov = round(gmv / max(trx, 1), 2)
            sec = sec_map.get(row.restaurant, {k: 0.0 for k in totals})
            total_gmv += gmv
            total_trx += trx
            # ✅ Ahora ambos son float, no hay problema
            for k in totals:
                totals[k] += sec[k]
            count += 1
            table_data.append({
                "restaurant": row.restaurant,
                "gmv":        f"${gmv:,.2f}",
                "trx":        f"{trx:,}",
                "aov":        f"${aov:,.2f}",
                "barquilla":  f"{sec['barquilla']:.2f}%",
                "cambio":     f"{sec['cambio']:.2f}%",
                "queso":      f"{sec['queso']:.2f}%",
                "agrandado":  f"{sec['agrandado']:.2f}%",
            })

        if count > 0:
            avg_aov = round(total_gmv / max(total_trx, 1), 2)
            table_data.append({
                "restaurant": "** TOTAL **",
                "gmv":        f"${total_gmv:,.2f}",
                "trx":        f"{int(total_trx):,}",
                "aov":        f"${avg_aov:,.2f}",
                "barquilla":  f"{totals['barquilla']/count:.2f}%",
                "cambio":     f"{totals['cambio']/count:.2f}%",
                "queso":      f"{totals['queso']/count:.2f}%",
                "agrandado":  f"{totals['agrandado']/count:.2f}%",
                "isTotal":    True,
            })

        result = {
            "success": True,
            "data": {
                "table":  table_data,
                "period": {"start": start_date, "end": end_date},
            },
        }

        if cache:
            try: 
                await cache.set(cache_key, result, ttl=300)
            except Exception: 
                pass

        return result

    except Exception as exc:
        print(f"[ERROR] dashboard_restaurants: {exc}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail={
            "error": str(exc), "traceback": traceback.format_exc()
        })