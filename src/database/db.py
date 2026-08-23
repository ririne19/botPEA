import json
from pathlib import Path

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import Session, sessionmaker

from src.config import DATABASE_URL
from src.database.models import Base, Conversation, UserPreferences

# Nombre maximum de messages conservés par utilisateur
MAX_MESSAGES_PER_USER = 100

# Création de l'engine selon la base utilisée
if DATABASE_URL and "postgresql" in DATABASE_URL:
    # Postgres en prod — pas besoin de check_same_thread
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # vérifie que la connexion est active avant chaque requête
        pool_recycle=300,     # renouvelle les connexions toutes les 5 minutes
        echo=False,
    )
else:
    # SQLite en dev local
    db_path = Path(__file__).parent.parent.parent / "data" / "bot.db"
    db_path.parent.mkdir(exist_ok=True)
    engine = create_engine(
        DATABASE_URL or f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Crée toutes les tables si elles n'existent pas."""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de données initialisée")


def get_session() -> Session:
    """Retourne une session SQLAlchemy."""
    return SessionLocal()


def save_message(chat_id: str, role: str, content: str) -> None:
    """
    Sauvegarde un message et purge les anciens si nécessaire.
    Garde uniquement les MAX_MESSAGES_PER_USER derniers messages par utilisateur.
    """
    with SessionLocal() as session:
        # Sauvegarde le nouveau message
        message = Conversation(chat_id=chat_id, role=role, content=content)
        session.add(message)
        session.commit()

        # Compte le nombre de messages pour cet utilisateur
        count = (
            session.query(Conversation)
            .filter(Conversation.chat_id == chat_id)
            .count()
        )

        # Purge si on dépasse la limite
        if count > MAX_MESSAGES_PER_USER:
            # Trouve l'ID du Nème message en partant de la fin
            ids_to_keep = [
                row.id
                for row in (
                    session.query(Conversation.id)
                    .filter(Conversation.chat_id == chat_id)
                    .order_by(desc(Conversation.created_at))
                    .limit(MAX_MESSAGES_PER_USER)
                    .all()
                )
            ]
            if ids_to_keep:
                session.query(Conversation).filter(
                    Conversation.chat_id == chat_id,
                    ~Conversation.id.in_(ids_to_keep),
                ).delete(synchronize_session="fetch")
                session.commit()


def get_conversation_history(chat_id: str, limit: int = 10) -> list[dict[str, str]]:
    """Récupère les N derniers messages pour alimenter le contexte Groq."""
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
    """Récupère ou crée les préférences utilisateur."""
    with SessionLocal() as session:
        prefs = session.get(UserPreferences, chat_id)
        if not prefs:
            prefs = UserPreferences(chat_id=chat_id)
            session.add(prefs)
            session.commit()
            session.refresh(prefs)
        return prefs


def update_preferences(chat_id: str, **kwargs: str | float) -> None:
    """Met à jour les préférences utilisateur."""
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
    """Retourne la watchlist de l'utilisateur."""
    with SessionLocal() as session:
        prefs = session.get(UserPreferences, chat_id)
        if not prefs:
            return []
        return json.loads(str(prefs.watchlist))


def update_watchlist(chat_id: str, tickers: list[str]) -> None:
    """Met à jour la watchlist."""
    update_preferences(chat_id, watchlist=json.dumps(tickers))