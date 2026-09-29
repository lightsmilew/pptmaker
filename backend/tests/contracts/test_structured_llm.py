"""Tests for contracts/structured_llm.py."""

import pytest
from unittest.mock import MagicMock

from app.contracts.structured_llm import (
    StructuredLLMCaller,
    LLMCallResult,
    RetryContext,
)


class MockLLM:
    """Simple mock LLM for testing."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.calls = []

    def generate(self, prompt="", system="", max_tokens=4096, **kwargs):
        self.calls.append({"prompt": prompt, "system": system, "max_tokens": max_tokens, **kwargs})
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            if isinstance(response, dict):
                import json
                return json.dumps(response)
            elif isinstance(response, Exception):
                raise response
            return str(response)
        return '{"status": "ok"}'


class TestRetryContext:
    """Tests for RetryContext."""

    def test_should_retry(self):
        """Test retry decision logic."""
        ctx = RetryContext(max_retries=3, current_attempt=1)
        assert ctx.should_retry() is True

        ctx = RetryContext(max_retries=3, current_attempt=3)
        assert ctx.should_retry() is False

    def test_increment(self):
        """Increment creates new context."""
        ctx = RetryContext(max_retries=3, current_attempt=1)
        new_ctx = ctx.increment()
        assert new_ctx.current_attempt == 2
        assert new_ctx.max_retries == 3


class TestStructuredLLMCaller:
    """Tests for StructuredLLMCaller."""

    def test_call_success(self):
        """Successful call on first try."""
        llm = MockLLM(responses=[{"key": "value"}])
        caller = StructuredLLMCaller(llm)

        result = caller.call(prompt="test", system="sys")

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.attempt == 1

    def test_call_with_pydantic_model(self):
        """Call with Pydantic model validation."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            age: int

        llm = MockLLM(responses=[{"name": "Alice", "age": 30}])
        caller = StructuredLLMCaller(llm)

        result = caller.call(
            prompt="test",
            expected_type=TestModel,
            contract_name="test"
        )

        assert result.success is True
        assert result.data.name == "Alice"
        assert result.data.age == 30

    def test_call_retry_on_json_error(self):
        """Retry on JSON parse error, eventually succeeds."""
        # First two responses have unparseable JSON (broken object),
        # third has valid JSON
        llm = MockLLM(responses=[
            '{"x":}',   # Invalid JSON
            '{"y":}',   # Invalid JSON
            '{"valid": true}'  # Valid
        ])
        caller = StructuredLLMCaller(llm, default_max_retries=3)

        result = caller.call(prompt="test", contract_name="test")

        assert result.success is True
        assert result.data == {"valid": True}
        assert result.attempt == 3
        assert llm.call_count == 3

    def test_call_max_retries_exceeded_with_invalid_response(self):
        """Malformed JSON triggers retries that all fail."""
        # Extractor now raises on input that looks like JSON but cannot be
        # parsed. Each retry receives the same broken payload so we exhaust
        # the retry budget.
        llm = MockLLM(responses=["{bad"] * 5)
        caller = StructuredLLMCaller(llm, default_max_retries=3)

        result = caller.call(prompt="test", contract_name="test")

        assert result.success is False
        assert result.attempt == 3
        # The error may be wrapped as "JSON解析失败: ..." (legacy path) or the
        # bare JSONDecodeError message (when the extractor itself raises).
        assert result.error, "expected non-empty error message"

    def test_call_validation_failure(self):
        """Validation failure triggers retry."""
        from pydantic import BaseModel

        class StrictModel(BaseModel):
            value: int

        # First response missing required field
        llm = MockLLM(responses=[
            {"value": "not_int"},
            {"value": 42}
        ])
        caller = StructuredLLMCaller(llm, default_max_retries=3)

        result = caller.call(
            prompt="test",
            expected_type=StrictModel,
            contract_name="test"
        )

        assert result.success is True
        assert result.data.value == 42

    def test_call_returns_raw_data_when_no_expected_type(self):
        """Returns raw dict when no expected type specified."""
        llm = MockLLM(responses=[{"raw": True}])
        caller = StructuredLLMCaller(llm)

        result = caller.call(prompt="test")

        assert result.success is True
        assert result.data == {"raw": True}

    def test_call_with_additional_validation(self):
        """Additional validation function is called."""
        llm = MockLLM(responses=[{"value": 10}])
        caller = StructuredLLMCaller(llm)

        # Validator requires value > 100
        def validator(data):
            errors = []
            if data.get("value", 0) <= 100:
                errors.append("Value must be > 100")
            return errors

        result = caller.call(
            prompt="test",
            additional_validation=validator,
            max_retries=2,
        )

        # Should fail (no second response to retry with)
        assert result.success is False


class TestLLMCallResult:
    """Tests for LLMCallResult dataclass."""

    def test_default_values(self):
        """Default values are set correctly."""
        result = LLMCallResult(success=True, data={"a": 1})
        assert result.success is True
        assert result.data == {"a": 1}
        assert result.attempt == 1
        assert result.validation_errors == []
        assert result.error is None
