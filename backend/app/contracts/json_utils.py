"""JSON utilities for extracting and parsing LLM responses."""

import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

T = TypeVar("T")


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""

    def __init__(self, message: str, raw_response: str = "", cause: Exception = None):
        super().__init__(message)
        self.raw_response = raw_response
        self.cause = cause


def extract_json_from_text(text: str) -> str:
    """
    Extract JSON from LLM response text, handling various formatting issues.

    Handles:
    - Markdown code fences (```json ... ```)
    - Trailing text after JSON
    - Leading text before JSON
    - Preamble text from models (e.g., "Here is the JSON: ...")
    - Multiple JSON objects (extracts first complete one)
    - Reverse-proxy-injected JSON schemas that don't match the requested one
      (we look for the first complete JSON object in the text)

    Args:
        text: Raw LLM response text

    Returns:
        Extracted JSON string (guaranteed parseable by ``json.loads``) or "{}".
    """
    if not text:
        return "{}"

    raw = text.strip()

    # Remove common preamble patterns
    preamble_patterns = [
        r"^(Here(?:'s| is) the (?:JSON|json|data|output):?\s*)",
        r"^(以下(?:是|为).*?:?\s*)",
        r"^(JSON(?: response)?:?\s*)",
        r"^(```json\s*)",
    ]
    for pattern in preamble_patterns:
        raw = re.sub(pattern, "", raw, flags=re.IGNORECASE)

    # Handle markdown code fences
    if "```" in raw:
        chunks = [part.strip() for part in raw.split("```") if part.strip()]
        for i, chunk in enumerate(chunks):
            if chunk.startswith(("json\n", "JSON\n")):
                chunk = chunk[5:]
            if chunk.startswith(("json ", "JSON ")):
                parts = chunk.split("\n", 1)
                if len(parts) > 1:
                    chunk = parts[1]
            if "{" in chunk:
                raw = chunk
                break

    # First, try a quick parse of the whole string. If it works, we are done.
    try:
        return json.dumps(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        pass

    # Otherwise, walk the text and collect every balanced JSON object or array,
    # then return the first one that parses. This protects against responses
    # where the model emits a proxy-style "waiting_for_input" schema first and
    # then appends the real JSON afterwards.
    candidates: list[str] = []
    for start_char, end_char in (("{", "}"), ("[", "]")):
        idx = 0
        while idx < len(raw):
            start = raw.find(start_char, idx)
            if start == -1:
                break
            depth = 0
            in_string = False
            escape = False
            for end in range(start, len(raw)):
                ch = raw[end]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        candidates.append(raw[start : end + 1])
                        idx = end + 1
                        break
            else:
                break

    # Prefer the largest parseable JSON. Reverse-proxy responses tend to
    # inject a small ``waiting_for_input`` schema; the real LLM answer is
    # usually the larger object appended after it. If we can only parse one,
    # use it; otherwise sort by length so the real content wins. As a final
    # tie-breaker, we drop any candidate whose ``status`` is "waiting_for_input"
    # because those come from LLM-proxy auto-responders, not the actual model.
    parsed: list[str] = []
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("status") == "waiting_for_input":
            continue
        parsed.append(candidate)
    if not parsed:
        # Fall back to the largest of all parseable candidates.
        parsed = [
            c for c in candidates
            if _json_loads_or_none(c) is not None
        ]
    if parsed:
        return max(parsed, key=len)

    # If the input clearly looks like JSON (starts with { or [) but we couldn't
    # parse it, raise so that retry logic in callers can kick in. Returning
    # ``{}`` silently would mask real failures (e.g. the model emits truncated
    # JSON and the caller would treat it as a successful empty result).
    if raw.startswith(("{", "[")):
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            raise

    return "{}"


def _json_loads_or_none(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
def parse_llm_json(
    response: str,
    expected_type: Type[T] = None,
    contract_name: str = "unknown",
    default: T = None,
    allow_none: bool = False,
) -> T:
    """
    Parse and validate JSON from LLM response.

    Args:
        response: Raw LLM response text
        expected_type: Pydantic model class to validate against
        contract_name: Name of the contract for error messages
        default: Default value if parsing fails and allow_none is True
        allow_none: If True, return default on parse failure

    Returns:
        Parsed and validated object

    Raises:
        JSONParseError: If JSON parsing or validation fails
    """
    if not response:
        if allow_none:
            return default
        raise JSONParseError(
            f"Empty response for {contract_name}",
            raw_response=response
        )

    # Extract JSON from text
    json_text = extract_json_from_text(response)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        if allow_none:
            return default
        raise JSONParseError(
            f"Invalid JSON for {contract_name}: {e}",
            raw_response=response,
            cause=e
        )

    # If expected_type is a Pydantic model, validate it
    if expected_type is not None:
        if hasattr(expected_type, "model_validate"):
            try:
                return expected_type.model_validate(data)
            except Exception as e:
                if allow_none:
                    return default
                raise JSONParseError(
                    f"Validation failed for {contract_name}: {e}",
                    raw_response=response,
                    cause=e
                )
        elif hasattr(expected_type, "validate"):
            # Regular Pydantic v1
            try:
                return expected_type.validate(data)
            except Exception as e:
                if allow_none:
                    return default
                raise JSONParseError(
                    f"Validation failed for {contract_name}: {e}",
                    raw_response=response,
                    cause=e
                )

    return data


def parse_json_safely(
    json_text: str,
    default: Any = None
) -> Any:
    """
    Safely parse JSON with a fallback default.

    Args:
        json_text: JSON string to parse
        default: Default value on failure

    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return default


def validate_json_schema(
    data: Dict[str, Any],
    required_fields: List[str],
    field_types: Dict[str, type] = None,
    contract_name: str = "unknown"
) -> List[str]:
    """
    Basic JSON schema validation.

    Args:
        data: Data to validate
        required_fields: List of required field names
        field_types: Optional dict of field name to expected type
        contract_name: Name for error messages

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not isinstance(data, dict):
        return [f"{contract_name}: Expected JSON object"]

    for field in required_fields:
        if field not in data:
            errors.append(f"{contract_name}: Missing required field '{field}'")
        elif field_types and field in field_types:
            expected_type = field_types[field]
            actual = data[field]
            if actual is not None and not isinstance(actual, expected_type):
                errors.append(
                    f"{contract_name}: Field '{field}' should be {expected_type.__name__}, "
                    f"got {type(actual).__name__}"
                )

    return errors


def extract_multiple_json_objects(text: str) -> List[Dict[str, Any]]:
    """
    Extract all complete JSON objects from text.

    Useful when LLM returns multiple JSON blocks.

    Args:
        text: Text containing JSON objects

    Returns:
        List of parsed JSON objects
    """
    results = []
    json_text = extract_json_from_text(text)

    try:
        # Try parsing as array of objects
        data = json.loads(json_text)
        if isinstance(data, list):
            results = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            results = [data]
    except json.JSONDecodeError:
        pass

    return results
