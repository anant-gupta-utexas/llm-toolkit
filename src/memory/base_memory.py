import abc
from typing import Any, Dict, List, Optional


class BaseMemory(abc.ABC):
    """Abstract base class for conversation memory."""

    @abc.abstractmethod
    def get_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieves the conversation history for a given ID."""
        pass

    @abc.abstractmethod
    def save_history(self, conversation_id: str, history: List[Dict[str, Any]]) -> None:
        """Saves the entire conversation history for a given ID."""
        pass

    @abc.abstractmethod
    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        """Adds a single message to the conversation history."""
        pass

    @abc.abstractmethod
    def clear_history(self, conversation_id: str) -> None:
        """Clears the conversation history for a given ID."""
        pass

