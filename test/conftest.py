import pytest
import requests
import time
import os

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def ensure_app(base_url):
    """Wait for the app to be healthy before running tests."""
    for _ in range(30):
        try:
            r = requests.get(f"{base_url}/api/health", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    pytest.fail("App did not become healthy in time")


@pytest.fixture
def api(base_url, ensure_app):
    """HTTP client for API calls."""

    class APIClient:
        def __init__(self, base):
            self.base = base

        def get(self, path):
            return requests.get(f"{self.base}{path}")

        def post(self, path, json=None):
            return requests.post(f"{self.base}{path}", json=json)

        def delete(self, path):
            return requests.delete(f"{self.base}{path}")

    return APIClient(base_url)
