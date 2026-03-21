import asyncio
import os
import sys
from contextlib import contextmanager
from typing import Any, Callable

from dotenv import load_dotenv
from rapidata import RapidataClient

load_dotenv()

_client: RapidataClient | None = None


def get_client() -> RapidataClient:
    global _client
    if _client is None:
        try:
            _client = RapidataClient(
                client_id=os.environ["RAPIDATA_CLIENT_ID"],
                client_secret=os.environ["RAPIDATA_CLIENT_SECRET"],
            )
        except Exception:
            _client = None  # don't cache a broken client
            raise
    return _client


@contextmanager
def _stdout_to_stderr():
    """Redirect stdout to stderr during SDK calls.

    MCP uses stdio as its transport layer. Any SDK prints to stdout corrupt
    the JSON protocol. The Rapidata SDK prints status messages (e.g. order URLs)
    to stdout via managed_print() — redirect them to stderr instead.
    """
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


async def run_sync(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    def _wrapped():
        with _stdout_to_stderr():
            return fn(*args, **kwargs)

    return await asyncio.to_thread(_wrapped)
