"""Tests for contracts/errors.py."""

import pytest

from app.contracts.errors import (
    ContractError,
    ValidationError,
    SchemaValidationError,
    SemanticValidationError,
    JSONValidationError,
    ContractViolationError,
    LLMParsingError,
    MaxRetriesExceededError,
)


class TestContractError:
    """Tests for ContractError."""

    def test_basic(self):
        """Basic error creation."""
        err = ContractError("test error")
        assert str(err) == "test error"
        assert err.message == "test error"
        assert err.details == {}


class TestSchemaValidationError:
    """Tests for SchemaValidationError."""

    def test_with_field_info(self):
        """Create with field info."""
        err = SchemaValidationError(
            "Invalid value",
            field="name",
            expected_type="str",
            actual_value="123",
        )
        assert err.field == "name"
        assert err.expected_type == "str"
        assert err.actual_value == "123"


class TestSemanticValidationError:
    """Tests for SemanticValidationError."""

    def test_with_rule_info(self):
        """Create with rule info."""
        err = SemanticValidationError(
            "Rule violated",
            rule="max_items",
            context={"count": 10, "max": 5},
        )
        assert err.rule == "max_items"
        assert err.context == {"count": 10, "max": 5}


class TestMaxRetriesExceededError:
    """Tests for MaxRetriesExceededError."""

    def test_with_attempt_info(self):
        """Create with attempt info."""
        err = MaxRetriesExceededError(
            "Max retries exceeded",
            contract_name="test",
            max_retries=3,
            attempts=3,
            last_error="JSON parse error",
        )
        assert err.contract_name == "test"
        assert err.max_retries == 3
        assert err.attempts == 3
        assert err.last_error == "JSON parse error"


class TestInheritance:
    """Test that all errors inherit from ContractError."""

    @pytest.mark.parametrize("error_class", [
        ValidationError,
        SchemaValidationError,
        SemanticValidationError,
        JSONValidationError,
        ContractViolationError,
        LLMParsingError,
        MaxRetriesExceededError,
    ])
    def test_inherits_from_contract_error(self, error_class):
        """All custom errors inherit from ContractError."""
        assert issubclass(error_class, ContractError)
