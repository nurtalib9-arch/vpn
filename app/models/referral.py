from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bonus_days_given = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    referrer = relationship(
        "User",
        foreign_keys=[referrer_id],
        back_populates="referrals_made",
    )
