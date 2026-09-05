from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from ..core.database import Base


class UserPreferences(Base):
    __tablename__ = "sm_user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("sm_users.id", ondelete="CASCADE"), nullable=False, unique=True)
    intent_mode = Column(String(32), nullable=True)
    age_range_min = Column(Integer, nullable=True)
    age_range_max = Column(Integer, nullable=True)
    interests = Column(JSON, nullable=True)          # list[str]
    dealbreakers = Column(JSON, nullable=True)       # list[str]
    location_range_km = Column(Float, nullable=True)
    personality_traits = Column(JSON, nullable=True) # list[str]
    embedding_vector = Column(JSON, nullable=True)   # list[float]
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
