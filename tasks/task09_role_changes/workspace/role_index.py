"""Role-oriented read views backed by a membership registry."""

from membership_registry import MembershipRegistry


class RoleIndex:
    """Coordinate role changes and role-oriented queries."""

    def __init__(self, registry: MembershipRegistry):
        self._registry = registry
        self._members_by_role = self._build_index()

    def change_role(self, member: str, role: str) -> tuple[str, str]:
        """Accept a role change through the underlying registry."""

        return self._registry.assign_role(member, role)

    def current_role(self, member: str) -> str:
        """Return a member's current role from the registry."""

        return self._registry.role_for(member)

    def members_with_role(self, role: str) -> tuple[str, ...]:
        """Return members currently associated with a role."""

        if role not in MembershipRegistry.ALLOWED_ROLES:
            raise ValueError("unsupported role")
        return self._members_by_role[role]

    def role_counts(self) -> dict[str, int]:
        """Return the current number of members in each role."""

        return {
            role: len(members)
            for role, members in sorted(self._members_by_role.items())
        }

    def _build_index(self) -> dict[str, tuple[str, ...]]:
        grouped = {role: [] for role in MembershipRegistry.ALLOWED_ROLES}
        for member, role in self._registry.records():
            grouped[role].append(member)
        return {
            role: tuple(sorted(members)) for role, members in grouped.items()
        }
