from __future__ import annotations

import logging

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_reply(self, user_text: str) -> str:
        user_text = (user_text or "").strip()
        if not user_text:
            return "Ich habe keinen Text erhalten."

        if self.settings.llm_provider != "openai" or not self.settings.openai_api_key:
            return f"Verstanden. Du hast gesagt: {user_text}"

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            completion = client.chat.completions.create(
                model=self.settings.openai_llm_model,
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist ein hilfreicher, klarer Assistent. Antworte kurz.",
                    },
                    {"role": "user", "content": user_text},
                ],
            )
            content = completion.choices[0].message.content
            return (content or "").strip() or "Ich konnte keine Antwort erzeugen."
        except Exception as exc:
            logger.exception("LLM request failed: %s", exc)
            return f"Verstanden. Du hast gesagt: {user_text}"

