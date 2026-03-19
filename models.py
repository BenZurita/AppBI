# models.py - SQLAlchemy models para la BD de la APP (capa de presentación)

from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class UnifiedRestaurantMap(Base):
    """Mapeo unificado de restaurantes (reemplaza DimTeam)"""
    __tablename__ = "unified_restaurant_map"

    unified_team_sk = Column(String(50), primary_key=True)
    restaurant_code = Column(Integer)
    restaurant_name = Column(Text)
    region = Column(Text)
    city_name = Column(Text)
    state_name = Column(Text)
    country_name = Column(Text)
    company_name = Column(Text)
    dwh_team_sk_16 = Column(String(50))
    dwh_team_sk_18 = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DailyMetrics(Base):
    """Métricas diarias pre-calculadas (reemplaza cálculos de fact_order_line)"""
    __tablename__ = "daily_metrics"

    date_id = Column(Integer, primary_key=True)
    unified_team_sk = Column(String(50), primary_key=True)
    
    gmv = Column(Numeric(14, 2), default=0)
    trx = Column(Integer, default=0)
    aov = Column(Numeric(12, 2), default=0)
    
    # Desglose por versión (opcional, para auditoría)
    gmv_odoo16 = Column(Numeric(14, 2), default=0)
    gmv_odoo18 = Column(Numeric(14, 2), default=0)
    trx_odoo16 = Column(Integer, default=0)
    trx_odoo18 = Column(Integer, default=0)
    
    source_rows = Column(Integer)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class BarquillaCombo(Base):
    __tablename__ = "barquilla_combo"

    date_id = Column(Integer, primary_key=True)
    unified_team_sk = Column(String(50), primary_key=True)
    pct_barquillas_combo = Column(Numeric(10, 4), default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CambioPieza(Base):
    __tablename__ = "cambio_pz"

    date_id = Column(Integer, primary_key=True)
    unified_team_sk = Column(String(50), primary_key=True)
    pct_cambio_pz = Column(Numeric(10, 4), default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class QuesoMetric(Base):
    __tablename__ = "queso_metric"

    date_id = Column(Integer, primary_key=True)
    unified_team_sk = Column(String(50), primary_key=True)
    pct_queso = Column(Numeric(10, 4), default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GdeMetric(Base):
    __tablename__ = "gde_metric"

    date_id = Column(Integer, primary_key=True)
    unified_team_sk = Column(String(50), primary_key=True)
    pct_gde = Column(Numeric(10, 4), default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PaymentMetrics(Base):
    """Métricas diarias por tipo y método de pago (Delivery, Cashea, etc.)"""
    __tablename__ = "daily_payment_metrics"

    date_id = Column(Integer, primary_key=True)
    unified_team_sk = Column(String(50), primary_key=True)
    tipo_pago = Column(String, primary_key=True)
    payment_method_name = Column(String, primary_key=True)

    amount_usd = Column(Numeric(14, 2), default=0)
    ordenes = Column(Numeric(14, 2), default=0)
    amount_odoo16 = Column(Numeric(14, 2), default=0)
    amount_odoo18 = Column(Numeric(14, 2), default=0)
    ordenes_odoo16 = Column(Numeric(14, 2), default=0)
    ordenes_odoo18 = Column(Numeric(14, 2), default=0)
    calculation_version = Column(Integer, default=1)
    source_rows = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)