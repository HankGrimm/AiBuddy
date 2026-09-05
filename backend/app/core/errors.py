from fastapi import HTTPException, status


class MonadMateError(HTTPException):
    pass


class UserNotFoundError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=404, detail="User not found")


class PersonaNotFoundError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=404, detail="Persona not found")


class PersonaExpiredError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=403, detail="Persona has expired")


class RoomNotFoundError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=404, detail="Room not found")


class RoomAccessDeniedError(MonadMateError):
    def __init__(self, reason: str = "Access denied"):
        super().__init__(status_code=403, detail=reason)


class StakeRequiredError(MonadMateError):
    def __init__(self, amount: float, action: str):
        super().__init__(
            status_code=402,
            detail=f"Stake of {amount} MON required to {action}",
        )


class StakeNotFoundError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=404, detail="Stake not found")


class InsufficientStakeError(MonadMateError):
    def __init__(self, required: float, provided: float):
        super().__init__(
            status_code=402,
            detail=f"Insufficient stake: {provided} MON provided, {required} MON required",
        )


class MatchNotFoundError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=404, detail="Match not found")


class MessagingBlockedError(MonadMateError):
    def __init__(self, reason: str):
        super().__init__(status_code=403, detail=f"Messaging blocked: {reason}")


class ConsentRequiredError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=403, detail="Consent has not been granted")


class BlockedUserError(MonadMateError):
    def __init__(self):
        super().__init__(status_code=403, detail="This user has been blocked")


class AttestationError(MonadMateError):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


class EscrowError(MonadMateError):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


class SafetyError(MonadMateError):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=detail)
