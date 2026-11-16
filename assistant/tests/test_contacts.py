from assistant.core.config import CONFIG_DIR
from assistant.core.contacts import find_contacts, load_contacts, resolve_contact


def test_exact_name_match(config):
    contact, question = resolve_contact(config.contacts, "Ali Khan")
    assert question is None and contact.name == "Ali Khan"
    assert contact.phone == "+923001234567"


def test_alias_match_case_insensitive(config):
    contact, question = resolve_contact(config.contacts, "  Sara BAJI ")
    assert question is None and contact.name == "Sara Ahmed" and contact.phone == "+923211112222"


def test_unknown_contact_asks(config):
    contact, question = resolve_contact(config.contacts, "Bilal")
    assert contact is None and "Bilal" in question and "contacts.yaml" in question


def test_duplicate_alias_asks_which(config):
    assert len(find_contacts(config.contacts, "ali")) == 2
    contact, question = resolve_contact(config.contacts, "Ali")
    assert contact is None
    assert question == "Which Ali do you mean: Ali Khan or Ali Raza?"


def test_invalid_number_is_reported_not_used(config):
    contact, question = resolve_contact(config.contacts, "bad")
    assert contact is None and "looks wrong" in question


def test_missing_contacts_file_asks_to_create(tmp_path):
    assert load_contacts(tmp_path / "contacts.yaml") is None
    contact, question = resolve_contact(None, "Ali")
    assert contact is None and "contacts.example.yaml" in question


def test_yaml_numbers_are_not_mangled(tmp_path):
    # Unquoted 03001234567 would be an octal int in plain YAML; it must stay intact.
    path = tmp_path / "contacts.yaml"
    path.write_text(
        "contacts:\n"
        "  - name: Ali\n    phone: 03001234567\n"
        "  - name: Sara\n    phone: +923211112222\n"
        "  - name: Umer\n    aliases: umer bhai\n    phone: 0300 7654321\n",
        encoding="utf-8",
    )
    contacts = load_contacts(path)
    assert [c.phone for c in contacts] == ["+923001234567", "+923211112222", "+923007654321"]
    assert contacts[2].aliases == ("umer bhai",)


def test_example_file_is_valid():
    contacts = load_contacts(CONFIG_DIR / "contacts.example.yaml")
    assert len(contacts) == 2 and all(c.phone for c in contacts)
