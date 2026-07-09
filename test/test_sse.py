"""Server-Sent Events (SSE) E2E tests."""

import time
import requests


def test_sse_stream_connectable(base_url):
    """GET /api/stream/prices should connect and return text/event-stream."""
    r = requests.get(f"{base_url}/api/stream/prices", stream=True)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("Content-Type", "")
    r.close()


def test_sse_delivers_price_data(base_url):
    """SSE stream should deliver price data for known tickers within 3 seconds."""
    r = requests.get(f"{base_url}/api/stream/prices", stream=True)
    assert r.status_code == 200

    ticker_seen = False
    deadline = time.time() + 5

    try:
        for line in r.iter_lines(decode_unicode=True):
            if time.time() > deadline:
                break
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                if not data_str or data_str == "[object Object]" or data_str == "{}":
                    continue
                try:
                    import json
                    event = json.loads(data_str)
                    # Accept single-ticker or batch format
                    if isinstance(event, dict):
                        if "ticker" in event and "price" in event:
                            ticker_seen = True
                            break
                    elif isinstance(event, list):
                        if any("ticker" in e and "price" in e for e in event):
                            ticker_seen = True
                            break
                except Exception:
                    continue
    finally:
        r.close()

    assert ticker_seen, "No ticker+price event received from SSE stream within 5 seconds"


def test_sse_event_format(base_url):
    """SSE events should have expected fields: ticker, price, previous_price."""
    r = requests.get(f"{base_url}/api/stream/prices", stream=True)
    assert r.status_code == 200

    event_found = False
    deadline = time.time() + 5

    try:
        for line in r.iter_lines(decode_unicode=True):
            if time.time() > deadline:
                break
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                if not data_str:
                    continue
                try:
                    import json
                    event = json.loads(data_str)
                    # Handle both single-event and batch formats
                    events = event if isinstance(event, list) else [event]
                    for e in events:
                        if "ticker" in e and "price" in e:
                            assert "previous_price" in e, f"Missing 'previous_price' in event: {e}"
                            assert "price" in e, f"Missing 'price' in event: {e}"
                            assert "ticker" in e, f"Missing 'ticker' in event: {e}"
                            assert isinstance(e["price"], (int, float))
                            assert isinstance(e["previous_price"], (int, float))
                            event_found = True
                            break
                    if event_found:
                        break
                except Exception:
                    continue
    finally:
        r.close()

    assert event_found, "No valid ticker event with required fields found in SSE stream"
