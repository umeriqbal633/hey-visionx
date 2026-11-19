"""Send a WhatsApp message to a group from groups.yaml (groups have no phone number, so the
chat is opened through WhatsApp's search and checked by its exact name before anything is typed)."""
from __future__ import annotations

from assistant.core.groups import resolve_group, suggested_group
from assistant.skills import _whatsapp
from assistant.skills.base import Ask, Result, Skill


class SendWhatsAppGroup(Skill):
    name = "send_whatsapp_group"
    description = (
        "Send a WhatsApp message to one of the user's WhatsApp GROUPS (it is read back for a yes "
        "first). Use when the user says group / grup / گروپ or names a group, e.g. "
        "'C10 group mein bhejo ke ...', 'family group ko message karo ...'. For one person use send_whatsapp."
    )
    parameters = {
        "type": "object",
        "properties": {
            "group": {
                "type": "string",
                "description": "The group's name as the user said it, without the word 'group', e.g. 'C10'.",
            },
            "message": {
                "type": "string",
                "description": (
                    "The message in the user's exact words, same language and script. "
                    "Do not translate (Roman Urdu stays Roman Urdu), correct or rephrase it. "
                    "Leave out the command words."
                ),
            },
        },
        "required": ["group", "message"],
    }
    risk = "confirm"

    def check(self, group: str = "", message: str = "", **_) -> str | Ask | None:
        if not message.strip():
            return "What should I send to the group?"
        _, question = resolve_group(self.config.groups, group)
        suggestion = suggested_group(self.config.groups, group) if question else None
        return Ask(question, {"group": suggestion}) if suggestion else question

    def describe(self, group: str = "", message: str = "", **_) -> str:
        found, _ = resolve_group(self.config.groups, group)
        return f"send '{message.strip()}' to the WhatsApp group {found.name if found else group}"

    def confirm_prompt(self, group: str = "", message: str = "", **_) -> str:
        found, question = resolve_group(self.config.groups, group)
        if found is None:
            return question or ""
        return f"Send '{message.strip()}' to the WhatsApp group {found.name}?"

    def run(self, group: str = "", message: str = "", **_) -> Result:
        found, question = resolve_group(self.config.groups, group)
        if found is None:
            return Result(False, question or "I couldn't find that group.")
        settings = self.config.settings.get("whatsapp", {})
        auto = bool(settings.get("auto_send", False))
        try:
            status = _whatsapp.send_to_group(found.name, message.strip(), send=auto,
                                             timeout=float(settings.get("window_timeout", 10)))
        except OSError:
            return Result(False, "I couldn't open WhatsApp; is WhatsApp Desktop installed?")
        name = found.name
        if status == _whatsapp.SENT:
            return Result(True, f"Sent your message to the group {name}.")
        if status == _whatsapp.TYPED:
            return Result(True, f"Your message is typed in the group {name}, so press Enter to send it.")
        reasons = {
            _whatsapp.NOT_FOUND: (f"I couldn't find the group {name} in WhatsApp; "
                                  "check that its name in groups.yaml matches exactly"),
            _whatsapp.WRONG_CHAT: f"I couldn't open the group {name}, so I didn't type anything",
            _whatsapp.NOT_FRONT: "WhatsApp didn't come to the front, so I didn't type anything",
            _whatsapp.DRAFT_CONFLICT: f"the group {name} already had unsent text, so I didn't send anything",
            _whatsapp.NO_TEXT: f"I couldn't see the message in the box, so nothing was sent to {name}",
            _whatsapp.NOT_CLEARED: f"WhatsApp didn't take the send, so your message to {name} is typed but not sent",
        }
        reason = reasons.get(status, "something went wrong, so nothing was sent")
        return Result(False, reason[0].upper() + reason[1:] + ".")
