import json
from pathlib import Path
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base, Conversation, UserPreferences

DB_PATH = Path(__file__).parent.parent.parent / "data" / "bot.db"
DB_PATH.parent.mkdir(exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("✅ Base de données initialisée (SQLAlchemy)")


def get_session() -> Session:
    return SessionLocal()


def save_message(chat_id: str, role: str, content: str) -> None:
    with SessionLocal() as session:
        message = Conversation(chat_id=chat_id, role=role, content=content)
        session.add(message)
        session.commit()


def get_conversation_history(chat_id: str, limit: int = 10) -> list[dict[str, str]]:
    with SessionLocal() as session:
        messages = (
            session.query(Conversation)
            .filter(Conversation.chat_id == chat_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
            .all()
        )
    return [
        {"role": str(msg.role), "content": str(msg.content)}
        for msg in reversed(messages)
    ]


def get_or_create_preferences(chat_id: str) -> UserPreferences:
    with SessionLocal() as session:
        prefs = session.get(UserPreferences, chat_id)
        if not prefs:
            prefs = UserPreferences(chat_id=chat_id)
            session.add(prefs)
            session.commit()
            session.refresh(prefs)
        return prefs


def update_preferences(chat_id: str, **kwargs: str | float) -> None:
    with SessionLocal() as session:
        prefs = session.get(UserPreferences, chat_id)
        if not prefs:
            prefs = UserPreferences(chat_id=chat_id)
            session.add(prefs)
        for key, value in kwargs.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)
        session.commit()


def get_watchlist(chat_id: str) -> list[str]:
    with SessionLocal() as session:
        prefs = session.get(UserPreferences, chat_id)
        if not prefs:
            return []
        return json.loads(str(prefs.watchlist))


def update_watchlist(chat_id: str, tickers: list[str]) -> None:
    update_preferences(chat_id, watchlist=json.dumps(tickers))