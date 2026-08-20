"""Authoritative team-membership records."""


class MembershipRegistry:
    """Own member records and validate role changes."""

    ALLOWED_ROLES = frozenset({"editor", "reviewer", "viewer"})

    def __init__(self, records: list[tuple[str, str]]):
        if not records:
            raise ValueError("at least one member is required")
        self._records = [
            {"member": member, "role": role} for member, role in records
        ]
        for record in self._records:
            self._validate_member(record["member"])
            self._validate_role(record["role"])

    def assign_role(self, member: str, role: str) -> tuple[str, str]:
        """Change a member's role and return the accepted assignment."""

        self._validate_member(member)
        self._validate_role(role)
        record = self._find(member)
        record["role"] = role
        return member, role

    def role_for(self, member: str) -> str:
        """Return the current authoritative role for a member."""

        self._validate_member(member)
        return self._find(member)["role"]

    def records(self) -> tuple[tuple[str, str], ...]:
        """Return an immutable representation of current memberships."""

        return tuple((record["member"], record["role"]) for record in self._records)

    def _find(self, member: str) -> dict[str, str]:
        for record in self._records:
            if record["member"] == member:
                return record
        raise KeyError(member)

    @staticmethod
    def _validate_member(member: str) -> None:
        if not isinstance(member, str) or not member.strip():
            raise ValueError("member must be a non-empty string")

    @classmethod
    def _validate_role(cls, role: str) -> None:
        if role not in cls.ALLOWED_ROLES:
            raise ValueError("unsupported role")
