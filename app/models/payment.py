from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default="RUB")
    provider = Column(String(50), nullable=False)
    provider_payment_id = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="payments", lazy="raise")
    subscription = relationship("Subscription", lazy="raise")