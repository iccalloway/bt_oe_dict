from typing import Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)

_client = Anthropic()


def parse_structured(
    system: str,
    user: str,
    schema: Type[T],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> T:
    """Force Claude to emit JSON conforming to `schema` via a single tool call."""
    tool = {
        "name": "record_entry",
        "description": "Record the parsed dictionary entry.",
        "input_schema": schema.model_json_schema(),
    }
    resp = _client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_entry"},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(f"Response truncated at max_tokens={max_tokens}")
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return schema.model_validate(tool_use.input)
