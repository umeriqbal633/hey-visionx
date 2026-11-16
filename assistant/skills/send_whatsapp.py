"""Open WhatsApp Desktop with a message typed to a contact. The user presses Enter to send."""
from __future__ import annotations

from assistant.core.contacts import resolve_contact
from assistant.skills import _whatsapp
from assistant.skills.base import Result, Skill


class SendWhatsApp(Skill):
    name = "send_whatsapp"
    description = (
        "Prepare a WhatsApp message to one of the user's contacts (WhatsApp opens with it typed; "
        "the user presses Enter). Use for 'X ko message bhejo ke ...', 'tell X that ...', "
        "'X ko WhatsApp karo ...'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "string",
                "description": "The person's name exactly as the user said it, e.g. 'Ali'.",
            },
            "message": {
                "type": "string",
                "description": (
                    "The message in the user's exact words, same language and script. "
                    "Do not translate (Roman Urdu stays Roman Urdu), correct or rephrase it. "
                    "Leave out the command words, e.g. for 'Ali ko message bhejo ke main late hoon' "
                    "the message is 'main late hoon'."
                ),
            },
        },
        "required": ["contact", "message"],
    }
    risk = "confirm"

    def check(self, contact: str = "", **_) -> str | None:
        _, question = resolve_contact(self.config.contacts, contact)
        return question

    def confirm_prompt(self, contact: str = "", message: str = "", **_) -> str:
        found, question = resolve_contact(self.config.contacts, contact)
        if found is None:
            return question or ""
        return f"Send '{message.strip()}' to {found.name} ({found.display})?"

    def run(self, contact: str = "", message: str = "", **_) -> Result:
        found, question = resolve_contact(self.config.contacts, contact)
        if found is None:
            return Result(False, question or "I couldn't find that contact.")
        try:
            _whatsapp.launch(_whatsapp.chat_url(found.phone, message.strip()))
        except OSError:
            return Result(False, "I couldn't open WhatsApp; is WhatsApp Desktop installed?")
        return Result(True, f"WhatsApp is open with your message to {found.name}, so press Enter to send it.")
