import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class KBeautyProduct(Base):
    __tablename__ = "kbeauty_products"

    id = Column(Integer, primary_key=True)
    brand = Column(String, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String)
    key_actives = Column(String)
    typical_price_usd = Column(Float)

    dupes = relationship("DrugstoreDupe", back_populates="kbeauty_product", cascade="all, delete-orphan")


class DrugstoreDupe(Base):
    __tablename__ = "drugstore_dupes"

    id = Column(Integer, primary_key=True)
    kbeauty_product_id = Column(Integer, ForeignKey("kbeauty_products.id"), nullable=False)
    brand = Column(String, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String)
    key_actives = Column(String)
    match_notes = Column(Text)
    retailer = Column(String)  # cvs, amazon, target, walgreens
    product_url = Column(String)
    last_known_price_usd = Column(Float)

    kbeauty_product = relationship("KBeautyProduct", back_populates="dupes")
    price_history = relationship("PriceHistory", back_populates="dupe", cascade="all, delete-orphan")
    videos = relationship("GeneratedVideo", back_populates="dupe", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    dupe_id = Column(Integer, ForeignKey("drugstore_dupes.id"), nullable=False)
    price_usd = Column(Float, nullable=False)
    in_stock = Column(Integer, default=1)
    checked_at = Column(DateTime, default=datetime.datetime.utcnow)

    dupe = relationship("DrugstoreDupe", back_populates="price_history")


class AlertLog(Base):
    __tablename__ = "alert_log"

    id = Column(Integer, primary_key=True)
    dupe_id = Column(Integer, ForeignKey("drugstore_dupes.id"), nullable=False)
    old_price = Column(Float)
    new_price = Column(Float)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)


class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    id = Column(Integer, primary_key=True)
    dupe_id = Column(Integer, ForeignKey("drugstore_dupes.id"), nullable=False)
    file_path = Column(String, nullable=False)
    caption = Column(Text)
    hashtags = Column(String)
    trigger_reason = Column(String)  # "scheduled_rotation" or "price_drop"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    dupe = relationship("DrugstoreDupe", back_populates="videos")
