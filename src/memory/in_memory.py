from collections import defaultdict
from typing import Any, Dict, List

from src.memory.base_memory import BaseMemory
from src.utils.logger import logger

# Simple in-memory storage using a dictionary
_memory_store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

class InMemoryMemoryService(BaseMemory):
    """In-memory implementation of the conversation memory service."""

    def get_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieves the conversation history."""
        logger.info(f"MEMORY: Getting history for {conversation_id}")
        # Return a copy to prevent external modification of the stored list
        return list(_memory_store.get(conversation_id, []))

    def save_history(self, conversation_id: str, history: List[Dict[str, Any]]) -> None:
        """Saves the entire conversation history."""
        logger.info(
            f"MEMORY: Saving history for {conversation_id} ({len(history)} messages)"
        )
        # Save a copy to prevent issues if the original list is modified later
        _memory_store[conversation_id] = list(history)

    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        """Adds a single message to the conversation history."""
        logger.info(
            f"MEMORY: Adding message to {conversation_id}: {message.get('role')}"
        )
        _memory_store[conversation_id].append(message)

    def clear_history(self, conversation_id: str) -> None:
        """Clears the conversation history."""
        logger.info(f"MEMORY: Clearing history for {conversation_id}")
        if conversation_id in _memory_store:
            del _memory_store[conversation_id]

