"""Stub of the original cross-process action bus.

The chat-only fork has no Live2D pet to drive, so action publication is a
no-op. The function is kept for API compatibility with chat_window.py — when
the LLM emits an animation tag we just discard it.
"""


def publish_action(character: str, action: str) -> None:
    pass


def consume_actions(character: str, seen: set[str]) -> list[str]:
    return []
