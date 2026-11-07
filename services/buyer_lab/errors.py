"""Domain Exceptions for Phase 6 AI Buyer Lab."""


class BuyerLabError(Exception):
    """Base exception for all AI Buyer Lab errors."""
    pass


class IneligibleOfferError(BuyerLabError):
    """Raised when an offer fails hard constraints or exclusions."""
    def __init__(self, offer_id: str, reason: str, details: str):
        super().__init__(f"Offer '{offer_id}' is ineligible: {reason} ({details})")
        self.offer_id = offer_id
        self.reason = reason
        self.details = details


class MalformedOfferError(BuyerLabError):
    """Raised when an offer fails structural or schema validation."""
    def __init__(self, offer_id: str, details: str):
        super().__init__(f"Offer '{offer_id}' is malformed: {details}")
        self.offer_id = offer_id
        self.details = details


class SecurityBoundaryViolationError(BuyerLabError):
    """Raised when an offer attempts prompt-injection or contains forbidden merchant internals."""
    pass
