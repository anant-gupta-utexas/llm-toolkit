import contextlib
import contextvars
from typing import Generator, Optional

# Define the ContextVar at the module level
_conversation_id_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "conversation_id", default=None
)


def get_conversation_id() -> Optional[str]:
    """
    Retrieves the conversation ID from the current context.

    Returns:
        The current conversation ID (str) if set, otherwise None.
    """
    return _conversation_id_cv.get()


@contextlib.contextmanager
def set_conversation_id(conversation_id: str) -> Generator[None, None, None]:
    """
    A context manager to set the conversation ID for the enclosed code block.

    Args:
        conversation_id: The conversation ID string to set.

    Yields:
        None

    Example:
        with set_conversation_id("conv-123"):
            # Code here will see "conv-123" when calling get_conversation_id()
            process_request()
    """
    if conversation_id is None:
        raise ValueError("conversation_id cannot be None")

    token = _conversation_id_cv.set(conversation_id)
    try:
        yield
    finally:
        _conversation_id_cv.reset(token)


def set_conversation_id_for_current_context(conversation_id: str) -> contextvars.Token:
    """
    Sets the conversation ID for the current context and returns a token
    that can be used to restore the previous value.

    This is useful for non-context-manager use cases, such as when you need
    to set the ID at the beginning of a function and reset it at the end.

    Args:
        conversation_id: The conversation ID string to set.

    Returns:
        Token object that can be used with _conversation_id_cv.reset()

    Example:
        token = set_conversation_id_for_current_context("conv-123")
        try:
            # Code using the conversation ID
        finally:
            _conversation_id_cv.reset(token)
    """
    if conversation_id is None:
        raise ValueError("conversation_id cannot be None")

    return _conversation_id_cv.set(conversation_id)


# Example Usage (for documentation purposes)
if __name__ == "__main__":
    import asyncio

    async def task(name: str, conv_id: str):
        with set_conversation_id(conv_id):
            print(f"Task {name}: Started. Conv ID: {get_conversation_id()}")
            await asyncio.sleep(0.1)
            await sub_task(name)
            print(f"Task {name}: Finished. Conv ID: {get_conversation_id()}")

    async def sub_task(parent_name: str):
        print(
            f"  Sub-task from {parent_name}: Running. Conv ID: {get_conversation_id()}"
        )
        await asyncio.sleep(0.1)

    async def main():
        print(f"Main context before tasks: Conv ID: {get_conversation_id()}")
        await asyncio.gather(task("A", "conv-abc"), task("B", "conv-xyz"))
        print(f"Main context after tasks: Conv ID: {get_conversation_id()}")

    # asyncio.run(main())  # Uncomment to run the example
