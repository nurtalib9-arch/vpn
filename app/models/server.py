from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.sql import func
from app.core.database import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    marzban_node_id = Column(String(255), nullable=True)
    max_users = Column(Integer, default=100)
    current_users = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    location = Column(String(255), nullable=True)
    cpu_usage = Column(Numeric(5, 2), default=0)
    ram_usage = Column(Numeric(5, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
