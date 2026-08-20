import pytest

from membership_registry import MembershipRegistry
from role_index import RoleIndex


def make_index() -> RoleIndex:
    registry = MembershipRegistry(
        [("Ari", "editor"), ("Bo", "viewer"), ("Cy", "viewer")]
    )
    return RoleIndex(registry)


def test_initial_role_views_and_counts():
    index = make_index()

    assert index.members_with_role("editor") == ("Ari",)
    assert index.members_with_role("viewer") == ("Bo", "Cy")
    assert index.role_counts() == {"editor": 1, "reviewer": 0, "viewer": 2}


def test_change_return_value_and_direct_lookup_are_preserved():
    index = make_index()

    assert index.change_role("Bo", "reviewer") == ("Bo", "reviewer")
    assert index.current_role("Bo") == "reviewer"


def test_unknown_members_and_roles_are_rejected():
    index = make_index()

    with pytest.raises(KeyError):
        index.change_role("Dee", "viewer")
    with pytest.raises(ValueError):
        index.change_role("Ari", "owner")
    with pytest.raises(ValueError):
        index.members_with_role("owner")


def test_changing_one_member_preserves_other_members():
    index = make_index()

    index.change_role("Bo", "reviewer")

    assert index.current_role("Ari") == "editor"
    assert index.current_role("Cy") == "viewer"


def test_role_membership_views_reflect_an_accepted_change():
    index = make_index()

    index.change_role("Bo", "reviewer")

    assert index.members_with_role("reviewer") == ("Bo",)
    assert index.members_with_role("viewer") == ("Cy",)


def test_role_counts_reflect_an_accepted_change():
    index = make_index()

    index.change_role("Ari", "viewer")

    assert index.role_counts() == {"editor": 0, "reviewer": 0, "viewer": 3}
