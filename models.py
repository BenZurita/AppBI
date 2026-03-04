from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from Database import Base  


class FactOrderLine(Base):
    __tablename__ = "fact_order_line"

    order_line_sk_n = Column(String(50), primary_key=True)
    order_line_id = Column(Integer)
    order_id = Column(Integer)
    user_id = Column(Integer)
    customer_id = Column(Integer)
    product_id = Column(Integer)
    session_id = Column(Integer)
    date_id = Column(Integer, index=True)
    order_datetime = Column(DateTime)
    created_datetime_final = Column(DateTime)
    product_sk_n = Column(String(50), ForeignKey("dim_product.product_sk_n"))
    session_sk = Column(String(50), ForeignKey("dim_session.session_sk_n"))
    team_sk = Column(String(50), ForeignKey("dim_team.team_sk_n"))
    order_sk_n = Column(String(50))
    quantity = Column(Numeric(10, 2))
    price_unit_usd = Column(Numeric(12, 4))
    price_subtotal_usd = Column(Numeric(12, 2))
    price_subtotal_incl_usd = Column(Numeric(12, 2))
    odoo_version = Column(String(20))
    es_finde_semana = Column(Integer)


class DimProduct(Base):
    __tablename__ = "dim_product"

    product_sk_n = Column(String(50), primary_key=True)
    product_id = Column(Integer)
    codigo_odoo18 = Column(Integer)
    product_name = Column(Text)
    group_name = Column(Text)
    category_name = Column(Text)
    parent_category_name = Column(Text)
    product_type = Column(String(50))
    sale_ok = Column(Boolean)
    available_in_pos = Column(Boolean)
    is_cambio_pza = Column(Boolean, default=False)
    is_queso_extra = Column(Boolean, default=False)
    is_barquilla = Column(Boolean, default=False)
    create_date = Column(DateTime)
    write_date = Column(DateTime)


class DimTeam(Base):
    __tablename__ = "dim_team"

    team_sk_n = Column(String(50), primary_key=True)
    team_id = Column(Integer)
    team_name = Column(String(255))
    restaurant_code = Column(Integer)
    region = Column(String(255))
    city_name = Column(String(255))
    state_name = Column(String(255))
    country_name = Column(String(255))
    company_name = Column(String(255))
    odoo_version = Column(String(20))


class DimSession(Base):
    __tablename__ = "dim_session"

    session_sk_n = Column(String(50), primary_key=True)
    session_id = Column(Integer)
    session_name = Column(String(100))
    config_name = Column(String(100))
    session_start_datetime = Column(DateTime)
    session_end_datetime = Column(DateTime)
    user_name = Column(String(100))
    cod_restaurante = Column(String(50))
    caja = Column(String(50))
    odoo_version = Column(String(20))
    date_id = Column(Integer)


class PosOrderComplete(Base):
    __tablename__ = "pos_order_complete"

    order_sk_n = Column(String(50), primary_key=True)
    order_id = Column(Integer)
    date_id = Column(Integer, index=True)
    team_sk_n = Column(String(50))
    customer_sk_n = Column(String(50))
    amount_total = Column(Numeric(12, 2))
    price_subtotal_usd = Column(Numeric(12, 2))
    price_subtotal_usd_sin_igtf = Column(Numeric(12, 2))
    date_order = Column(DateTime)
    date_order_conv = Column(DateTime)


class BarquillaCombo(Base):
    __tablename__ = "barquilla_combo"

    date_id = Column(Integer, primary_key=True)
    team_sk = Column(String(50), primary_key=True)
    pct_barquillas_combo = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CambioPieza(Base):
    __tablename__ = "cambio_pz"

    date_id = Column(Integer, primary_key=True)
    team_sk = Column(String(50), primary_key=True)
    pct_cambio_pz = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class QuesoMetric(Base):
    __tablename__ = "queso_metric"

    date_id = Column(Integer, primary_key=True)
    team_sk = Column(String(50), primary_key=True)
    pct_queso = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GdeMetric(Base):
    __tablename__ = "gde_metric"

    date_id = Column(Integer, primary_key=True)
    team_sk = Column(String(50), primary_key=True)
    pct_gde = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)