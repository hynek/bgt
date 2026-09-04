from unittest.mock import patch

import pytest
import structlog


@pytest.fixture(autouse=True)
def configure_structlog():
    """
    Configures cleanly structlog for each test case.
    """
    structlog.stdlib.recreate_defaults(log_level=None)


@pytest.fixture(name="no_jitter")
def _no_jitter():
    """
    Pin the backoff jitter to 1, so backoff values are exact.
    """
    with patch("bgt._backoff.random.uniform", return_value=1):
        yield
