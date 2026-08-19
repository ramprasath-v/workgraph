import pytest

from user_registry import UserRegistry


def test_exact_identifier_lookup_works():
    registry = UserRegistry()
    assert registry.register("Alice", "Alice Example") is True
    assert registry.display_name_for("Alice") == "Alice Example"


def test_surrounding_whitespace_is_ignored():
    registry = UserRegistry()
    registry.register("  Alice  ", "Alice Example")
    assert registry.display_name_for("Alice") == "Alice Example"


def test_identifier_casing_is_ignored():
    registry = UserRegistry()
    registry.register("Alice", "Alice Example")
    assert registry.display_name_for("ALICE") == "Alice Example"


def test_equivalent_identifiers_do_not_create_duplicate_users():
    registry = UserRegistry()
    assert registry.register(" Alice ", "Alice Example") is True
    assert registry.register("alice", "Replacement Name") is False
    assert len(registry) == 1
    assert registry.display_name_for("ALICE") == "Alice Example"


def test_invalid_identifiers_remain_rejected():
    registry = UserRegistry()
    for identifier in ("", "   "):
        with pytest.raises(ValueError, match="must not be empty"):
            registry.register(identifier, "Nobody")
    with pytest.raises(TypeError, match="must be a string"):
        registry.register(None, "Nobody")


def test_registration_return_values_and_length_are_preserved():
    registry = UserRegistry()
    assert registry.register("bob", "Bob Example") is True
    assert registry.register("bob", "Different Name") is False
    assert len(registry) == 1
    assert registry.display_name_for("bob") == "Bob Example"
