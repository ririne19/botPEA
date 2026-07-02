from src.database.db import get_conversation_history, init_db, save_message


def test_init_db():
    """Vérifie que la base de données s'initialise sans erreur."""
    init_db()  # ne doit pas lever d'exception


def test_save_and_retrieve_message():
    """Vérifie qu'on peut sauvegarder et récupérer un message."""
    init_db()
    chat_id = "test_chat_123"

    save_message(chat_id, "user", "Bonjour")
    save_message(chat_id, "assistant", "Bonjour, comment puis-je t'aider ?")

    history = get_conversation_history(chat_id, limit=10)

    assert len(history) >= 2
    assert history[-2]["role"] == "user"
    assert history[-2]["content"] == "Bonjour"
    assert history[-1]["role"] == "assistant"


def test_conversation_history_limit():
    """Vérifie que la limite de l'historique est respectée."""
    init_db()
    chat_id = "test_limit_456"

    for i in range(15):
        save_message(chat_id, "user", f"Message {i}")

    history = get_conversation_history(chat_id, limit=5)
    assert len(history) == 5


def test_conversation_history_order():
    """Vérifie que les messages sont dans l'ordre chronologique."""
    init_db()
    chat_id = "test_order_789"

    save_message(chat_id, "user", "Premier message")
    save_message(chat_id, "assistant", "Deuxième message")

    history = get_conversation_history(chat_id, limit=10)
    # Le premier message doit apparaître avant le deuxième
    messages = [m["content"] for m in history if m["content"] in ["Premier message", "Deuxième message"]]
    assert messages.index("Premier message") < messages.index("Deuxième message")