from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from src.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)


async def get_groq_response(
    history: list[dict[str, str]],
    system_prompt: str,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        *[{"role": msg["role"], "content": msg["content"]} for msg in history],  # type: ignore[misc]
    ]

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content or "❌ Réponse vide du modèle."

    except Exception as e:
        return f"❌ Erreur lors de la communication avec l'IA : {str(e)}"