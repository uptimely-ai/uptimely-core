"""Serialize MCP tool results as JSON."""

import datetime
import json


class JsonSerializer:
    """Encode tool payloads, including date and time values."""

    @staticmethod
    def dumps(payload: object) -> str:
        """Return an indented JSON representation of a tool payload.

        Args:
            payload: JSON-compatible tool output.

        Returns:
            The serialized JSON string.

        Raises:
            TypeError: If a payload contains a value without JSON support.
        """

        def encode_date(value: object) -> str:
            if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                return value.isoformat()
            raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

        return json.dumps(payload, indent=2, default=encode_date)
