from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Time, Date, Text, Index
from sqlalchemy.orm import relationship
from database.db import Base
import datetime


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, index=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    registered_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    appointments = relationship("Appointment", back_populates="user")

    __table_args__ = (
        Index('ix_users_telegram_id', 'telegram_id'),
        Index('ix_users_registered_at', 'registered_at'),
    )


class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)

    images = relationship("PortfolioImage", back_populates="category")


class PortfolioImage(Base):
    __tablename__ = 'portfolio_images'
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'), index=True)
    file_path = Column(String, nullable=False)
    caption = Column(Text)
    price = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    category = relationship("Category", back_populates="images")

    __table_args__ = (
        Index('ix_portfolio_category_id', 'category_id'),
        Index('ix_portfolio_created_at', 'created_at'),
    )


class Price(Base):
    __tablename__ = 'prices'
    id = Column(Integer, primary_key=True)
    service_name = Column(String, nullable=False, index=True)
    price = Column(String)
    description = Column(Text)
    category = Column(String, index=True)

    __table_args__ = (
        Index('ix_prices_service_name', 'service_name'),
        Index('ix_prices_category', 'category'),
    )


class Schedule(Base):
    __tablename__ = 'schedule'
    id = Column(Integer, primary_key=True)
    day_of_week = Column(Integer, nullable=False, index=True)  # 0-6 (пн-вс)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    is_working = Column(Boolean, default=True, index=True)

    __table_args__ = (
        Index('ix_schedule_day_of_week', 'day_of_week'),
    )


class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    date = Column(Date, nullable=False, index=True)
    time = Column(Time, nullable=False, index=True)
    service = Column(String)
    comment = Column(Text)
    status = Column(String, default='scheduled', index=True)  # scheduled, completed, cancelled
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    reminder_sent = Column(Boolean, default=False, index=True)

    user = relationship("User", back_populates="appointments")

    __table_args__ = (
        Index('ix_appointments_user_id', 'user_id'),
        Index('ix_appointments_date', 'date'),
        Index('ix_appointments_status', 'status'),
        Index('ix_appointments_date_time', 'date', 'time'),
        Index('ix_appointments_user_status', 'user_id', 'status'),
    )
