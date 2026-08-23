import time
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Conversation


@pytest.fixture
def test_session() -> Generator[Session, None, None]:
    """Crée une base SQLite temporaire en mémoire pour chaque test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_init_db(test_session: Session) -> None:
    """Vérifie que la base de données s'initialise sans erreur."""
    assert test_session is not None


def test_save_and_retrieve_message(test_session: Session) -> None:
    """Vérifie qu'on peut sauvegarder et récupérer un message."""
    chat_id = "test_chat_123"

    test_session.add(Conversation(chat_id=chat_id, role="user", content="Bonjour"))
    test_session.add(Conversation(chat_id=chat_id, role="assistant", content="Bonjour, comment puis-je t'aider ?"))
    test_session.commit()

    messages: list[Conversation] = (
        test_session.query(Conversation)
        .filter(Conversation.chat_id == chat_id)
        .order_by(Conversation.created_at)
        .all()
    )

    assert len(messages) == 2
    assert str(messages[0].role) == "user"
    assert str(messages[0].content) == "Bonjour"
    assert str(messages[1].role) == "assistant"


def test_conversation_history_limit(test_session: Session) -> None:
    """Vérifie que la limite de l'historique est respectée."""
    chat_id = "test_limit_456"

    for i in range(15):
        test_session.add(Conversation(chat_id=chat_id, role="user", content=f"Message {i}"))
    test_session.commit()

    messages: list[Conversation] = (
        test_session.query(Conversation)
        .filter(Conversation.chat_id == chat_id)
        .order_by(desc(Conversation.created_at))
        .limit(5)
        .all()
    )

    assert len(messages) == 5


def test_conversation_history_order(test_session: Session) -> None:
    """Vérifie que les messages sont dans l'ordre chronologique."""
    chat_id = "test_order_789"

    test_session.add(Conversation(chat_id=chat_id, role="user", content="Premier message"))
    test_session.commit()
    time.sleep(0.01)
    test_session.add(Conversation(chat_id=chat_id, role="assistant", content="Deuxième message"))
    test_session.commit()

    messages: list[Conversation] = (
        test_session.query(Conversation)
        .filter(Conversation.chat_id == chat_id)
        .order_by(Conversation.created_at)
        .all()
    )

    contents: list[str] = [str(m.content) for m in messages]
    assert contents.index("Premier message") < contents.index("Deuxième message")