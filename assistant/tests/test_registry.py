from assistant.core.registry import discover


def test_discovers_all_phase1_skills(config):
    registry = discover(config)
    assert {"open_app", "open_website", "get_time"} <= set(registry.names())


def test_tool_schemas_are_sorted_and_stable(config):
    a = discover(config).tool_schemas()
    b = discover(config).tool_schemas()
    assert a == b                                     # identical across runs (cache-friendly)
    names = [t["name"] for t in a]
    assert names == sorted(names)
    for tool in a:
        assert set(tool) == {"name", "description", "parameters"}
        assert tool["parameters"]["type"] == "object"


def test_every_skill_follows_contract(config):
    registry = discover(config)
    for name in registry.names():
        skill = registry.get(name)
        assert skill.risk in ("safe", "confirm")
        assert skill.description
