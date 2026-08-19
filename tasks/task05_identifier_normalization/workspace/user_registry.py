class UserRegistry:
    """In-memory registry keyed by externally supplied user identifiers."""

    def __init__(self):
        self._users = {}

    @staticmethod
    def _validate(identifier):
        if not isinstance(identifier, str):
            raise TypeError("identifier must be a string")
        if not identifier.strip():
            raise ValueError("identifier must not be empty")

    def register(self, identifier, display_name):
        self._validate(identifier)
        if identifier in self._users:
            return False
        self._users[identifier] = display_name
        return True

    def display_name_for(self, identifier):
        self._validate(identifier)
        return self._users.get(identifier)

    def __len__(self):
        return len(self._users)
