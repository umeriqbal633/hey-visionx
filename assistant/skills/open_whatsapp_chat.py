"""Open the WhatsApp chat with a contact, without typing anything."""
from __future__ import annotations

from assistant.core.contacts import resolve_contact, suggested_contact
from assistant.skills import _whatsapp
from assistant.skills.base import Ask, Result, Skill


class OpenWhatsAppChat(Skill):
    name = "open_whatsapp_chat"
    description = (
        "Open the WhatsApp chat with one of the user's contacts, with no message. "
        "Use for 'Ali ki chat kholo', 'open my WhatsApp chat with Sara'. "
        "To just open the WhatsApp app, use open_app instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "string",
                "description": "The person's name exactly as the user said it, e.g. 'Ali'.",
            }
        },
        "required": ["contact"],
    }
    risk = "safe"

    def check(self, contact: str = "", **_) -> str | Ask | None:
        _, question = resolve_contact(self.config.contacts, contact)
        suggestion = suggested_contact(self.config.contacts, contact) if question else None
        return Ask(question, {"contact": suggestion}) if suggestion else question

    def describe(self, contact: str = "", **_) -> str:
        found, _ = resolve_contact(self.config.contacts, contact)
        return f"open the WhatsApp chat with {found.name if found else contact}"

    def run(self, contact: str = "", **_) -> Result:
        found, question = resolve_contact(self.config.contacts, contact)
        if found is None:
            return Result(False, question or "I couldn't find that contact.")
        try:
            _whatsapp.launch(_whatsapp.chat_url(found.phone))
        except OSError:
            return Result(False, "I couldn't open WhatsApp; is WhatsApp Desktop installed?")
        return Result(True, f"Opening your WhatsApp chat with {found.name}.")
