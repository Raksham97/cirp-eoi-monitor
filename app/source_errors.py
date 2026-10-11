"""Classify only temporary upstream transport failures; never exempt schema/data errors."""
from __future__ import annotations
import requests

TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def is_transient_source_error(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                        requests.exceptions.RetryError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        return response is not None and response.status_code in TRANSIENT_HTTP_STATUSES
    return False


class SourceTemporarilyUnavailable(RuntimeError):
    """A transient official-site outage exhausted bounded attempts."""
