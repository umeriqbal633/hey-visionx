"""Open WhatsApp Desktop with a message typed to a contact. The user presses Enter to send."""
from __future__ import annotations

from assistant.core.contacts import resolve_contact, suggested_contact
from assistant.core.groups import find_groups
from assistant.skills import _whatsapp
from assistant.skills.base import Ask, Result, Skill


class SendWhatsApp(Skill):
    name = "send_whatsapp"
    description = (
        "Send a WhatsApp message to one of the user's contacts (it is read back for a yes first). "
        "Use for 'X ko message bhejo ke ...', 'tell X that ...', 'X ko WhatsApp karo ...'."
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

    def check(self, contact: str = "", **_) -> str | Ask | None:
        _, question = resolve_contact(self.config.contacts, contact)
        groups = find_groups(self.config.groups, contact)
        if question and len(groups) == 1:   # not a person, but exactly one of the user's groups
            return f"{groups[0].name} is a WhatsApp group; should I send it to the group?"
        suggestion = suggested_contact(self.config.contacts, contact) if question else None
        return Ask(question, {"contact": suggestion}) if suggestion else question

    def describe(self, contact: str = "", message: str = "", **_) -> str:
        found, _ = resolve_contact(self.config.contacts, contact)
        who = f"{found.name} ({found.display})" if found else contact
        return f"send '{message.strip()}' to {who} on WhatsApp"

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
        settings = self.config.settings.get("whatsapp", {})
        if not settings.get("auto_send", False):
            return Result(True, f"WhatsApp is open with your message to {found.name}, so press Enter to send it.")
        status = _whatsapp.send_verified(message.strip(), timeout=float(settings.get("window_timeout", 10)))
        if status == _whatsapp.SENT:
            return Result(True, f"Sent your message to {found.name}.")
        if status == _whatsapp.DRAFT_CONFLICT:
            return Result(False, f"{found.name}'s chat already had unsent text, so I didn't send anything; "
                                 "please check WhatsApp.")
        reason = {
            _whatsapp.NOT_FRONT: "WhatsApp didn't come to the front",
            _whatsapp.NO_TEXT: "I couldn't see the message in WhatsApp's message box",
            _whatsapp.NOT_CLEARED: "WhatsApp didn't take the Enter key",
        }.get(status, "something went wrong")
        return Result(False, f"{reason}, so your message to {found.name} is typed but not sent.")
