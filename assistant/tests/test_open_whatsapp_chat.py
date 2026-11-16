from unittest.mock import patch

from assistant.skills.open_whatsapp_chat import OpenWhatsAppChat

LAUNCH = "assistant.skills._whatsapp.launch"


def test_is_safe(config):
    assert OpenWhatsAppChat(config).risk == "safe"


def test_opens_chat_without_text(config):
    with patch(LAUNCH) as launch:
        result = OpenWhatsAppChat(config).run(contact="sara")
    launch.assert_called_once_with("whatsapp://send?phone=923211112222")
    assert result.ok and "Sara Ahmed" in result.reply


def test_unknown_and_duplicate_do_not_open(config):
    with patch(LAUNCH) as launch:
        unknown = OpenWhatsAppChat(config).run(contact="Bilal")
        dup = OpenWhatsAppChat(config).run(contact="ali")
    launch.assert_not_called()
    assert not unknown.ok and not dup.ok
    assert OpenWhatsAppChat(config).check(contact="ali") == "Which ali do you mean: Ali Khan or Ali Raza?"
