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


class Price(Base):
    __tablename__ = 'prices'
    id = Column(Integer, primary_key=True)
    service_name = Column(String, nullable=False, index=True)
    price = Column(String)
    description = Column(Text)
    category = Column(String, index=True)


class Schedule(Base):
    __tablename__ = 'schedule'
    id = Column(Integer, primary_key=True)
    day_of_week = Column(Integer, nullable=False, index=True)  # 0-6 (пн-вс)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    is_working = Column(Boolean, default=True, index=True)


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
