class SecurityViolation(Exception):
    """Raised when a player bot attempts to bypass security restrictions or sabotage the engine."""

    def __init__(self, message: str, offender: str | None = None):
        super().__init__(message)
        self.offender = offender
