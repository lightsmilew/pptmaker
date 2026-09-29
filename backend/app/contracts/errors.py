"""Custom exceptions for the contracts module."""


class ContractError(Exception):
    """Base exception for contract-related errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(ContractError):
    """Raised when validation fails."""

    pass


class SchemaValidationError(ValidationError):
    """Raised when JSON schema validation fails."""

    def __init__(
        self,
        message: str,
        field: str = None,
        expected_type: str = None,
        actual_value: str = None,
        details: dict = None
    ):
        super().__init__(message, details)
        self.field = field
        self.expected_type = expected_type
        self.actual_value = actual_value


class SemanticValidationError(ValidationError):
    """Raised when semantic validation fails (e.g., business logic)."""

    def __init__(
        self,
        message: str,
        rule: str = None,
        context: dict = None,
        details: dict = None
    ):
        super().__init__(message, details)
        self.rule = rule
        self.context = context or {}


class JSONValidationError(ValidationError):
    """Raised when JSON parsing or structure validation fails."""

    def __init__(
        self,
        message: str,
        json_error: str = None,
        position: int = None,
        details: dict = None
    ):
        super().__init__(message, details)
        self.json_error = json_error
        self.position = position


class ContractViolationError(ContractError):
    """Raised when a contract's rules are violated."""

    def __init__(
        self,
        message: str,
        contract_name: str = None,
        violations: list = None,
        details: dict = None
    ):
        super().__init__(message, details)
        self.contract_name = contract_name
        self.violations = violations or []


class LLMParsingError(ContractError):
    """Raised when LLM output cannot be parsed."""

    def __init__(
        self,
        message: str,
        raw_output: str = None,
        attempt: int = 1,
        details: dict = None
    ):
        super().__init__(message, details)
        self.raw_output = raw_output
        self.attempt = attempt


class MaxRetriesExceededError(ContractError):
    """Raised when maximum retry attempts are exceeded."""

    def __init__(
        self,
        message: str,
        contract_name: str = None,
        max_retries: int = 3,
        attempts: int = 0,
        last_error: str = None,
        details: dict = None
    ):
        super().__init__(message, details)
        self.contract_name = contract_name
        self.max_retries = max_retries
        self.attempts = attempts
        self.last_error = last_error
