from sqlalchemy import Column, BigInteger, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from config.database.dbsession import Base

class Telemetry(Base):
    __tablename__ = "telemetry"

    telemetry_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    event_name = Column(String(100), nullable=False, index=True)
    event_payload = Column(JSONB, nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)