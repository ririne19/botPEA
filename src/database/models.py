from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Conversation chat_id={self.chat_id} role={self.role}>"


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    chat_id = Column(String, primary_key=True)
    sectors = Column(String, default="tech")
    watchlist = Column(String, default="[]")
    budget_mensuel: float = Column(Float, default=0.0)  # type: ignore[assignment]
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<UserPreferences chat_id={self.chat_id} sectors={self.sectors}>"