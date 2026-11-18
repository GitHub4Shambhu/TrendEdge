"""Tests for the server-side watchlist and signal-change alerts."""

from datetime import datetime
from typing import Dict, Optional

import pytest
from zoneinfo import ZoneInfo

from app.services import signal_alerts
from app.services.signal_alerts import (
    SignalAlertService,
    SignalAlertStore,
    Snapshot,
    is_market_open,
)

ET = ZoneInfo("America/New_York")


def _snap(symbol: str, consensus: str, price: float = 100.0, stale: bool = False) -> Snapshot:
    return Snapshot(symbol, consensus, price, buy_votes=2, sell_votes=0, stale=stale)


class FakeAnalyzer:
    """Returns whatever snapshot the test set for each symbol."""

    def __init__(self):
        self.snaps: Dict[str, Optional[Snapshot]] = {}
        self.calls = []

    async def __call__(self, symbol: str) -> Optional[Snapshot]:
        self.calls.append(symbol)
        result = self.snaps.get(symbol)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def service():
    return SignalAlertService(SignalAlertStore(":memory:"))


# ── Watchlist persistence ────────────────────────────────────

def test_set_watchlist_normalizes_and_keeps_order(service):
    saved = service.store.set_watchlist([" nvda", "AAPL", "nvda", ""])
    assert [w["symbol"] for w in saved] == ["NVDA", "AAPL"]
    assert all(w["alerts_enabled"] for w in saved)


def test_set_watchlist_rejects_too_many(service):
    with pytest.raises(ValueError):
        service.store.set_watchlist([f"T{i}" for i in range(26)])


def test_alert_toggle_survives_reorder(service):
    service.store.set_watchlist(["NVDA", "AAPL"])
    assert service.store.set_alerts_enabled("aapl", False)
    saved = service.store.set_watchlist(["AAPL", "MSFT", "NVDA"])
    assert saved == [
        {"symbol": "AAPL", "alerts_enabled": False},
        {"symbol": "MSFT", "alerts_enabled": True},
        {"symbol": "NVDA", "alerts_enabled": True},
    ]


def test_toggle_unknown_symbol_returns_false(service):
    assert service.store.set_alerts_enabled("TSLA", True) is False


# ── Signal-change detection ──────────────────────────────────

async def test_first_check_records_baseline_without_event(service):
    service.store.set_watchlist(["NVDA"])
    analyze = FakeAnalyzer()
    analyze.snaps["NVDA"] = _snap("NVDA", "BULLISH")
    assert await service.check(analyze) == []
    assert service.store.last_consensus("NVDA") == "BULLISH"
    assert service.last_run is not None


async def test_consensus_change_creates_event(service):
    service.store.set_watchlist(["NVDA"])
    analyze = FakeAnalyzer()
    analyze.snaps["NVDA"] = _snap("NVDA", "BULLISH")
    await service.check(analyze)

    analyze.snaps["NVDA"] = _snap("NVDA", "BEARISH", price=91.5)
    events = await service.check(analyze)

    assert len(events) == 1
    e = events[0]
    assert (e.symbol, e.previous, e.current, e.price) == ("NVDA", "BULLISH", "BEARISH", 91.5)
    assert "BULLISH → BEARISH" in e.message
    assert [x.id for x in service.store.recent_events()] == [e.id]


async def test_unchanged_consensus_creates_no_event(service):
    service.store.set_watchlist(["NVDA"])
    analyze = FakeAnalyzer()
    analyze.snaps["NVDA"] = _snap("NVDA", "MIXED")
    await service.check(analyze)
    assert await service.check(analyze) == []


async def test_stale_and_missing_results_are_ignored(service):
    service.store.set_watchlist(["NVDA", "XXXX"])
    analyze = FakeAnalyzer()
    analyze.snaps["NVDA"] = _snap("NVDA", "BULLISH")
    await service.check(analyze)

    analyze.snaps["NVDA"] = _snap("NVDA", "BEARISH", stale=True)
    assert await service.check(analyze) == []
    assert service.store.last_consensus("NVDA") == "BULLISH"
    assert service.store.last_consensus("XXXX") is None


async def test_disabled_symbols_are_not_checked(service):
    service.store.set_watchlist(["NVDA", "AAPL"])
    service.store.set_alerts_enabled("AAPL", False)
    analyze = FakeAnalyzer()
    await service.check(analyze)
    assert analyze.calls == ["NVDA"]


async def test_one_failing_symbol_does_not_stop_the_run(service):
    service.store.set_watchlist(["BAD", "NVDA"])
    analyze = FakeAnalyzer()
    analyze.snaps["BAD"] = RuntimeError("boom")
    analyze.snaps["NVDA"] = _snap("NVDA", "BULLISH")
    await service.check(analyze)
    assert service.store.last_consensus("NVDA") == "BULLISH"


async def test_removing_symbol_resets_its_baseline(service):
    service.store.set_watchlist(["NVDA"])
    analyze = FakeAnalyzer()
    analyze.snaps["NVDA"] = _snap("NVDA", "BULLISH")
    await service.check(analyze)

    service.store.set_watchlist([])
    service.store.set_watchlist(["NVDA"])
    analyze.snaps["NVDA"] = _snap("NVDA", "BEARISH")
    assert await service.check(analyze) == []


# ── Webhook delivery ─────────────────────────────────────────

async def test_webhook_posts_and_marks_notified(service, monkeypatch):
    posted = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            posted.append((url, json))
            return FakeResponse()

    monkeypatch.setattr(signal_alerts.httpx, "AsyncClient", FakeClient)
    service.webhook_url = "https://hooks.example/abc"
    service.store.set_watchlist(["NVDA"])
    analyze = FakeAnalyzer()
    analyze.snaps["NVDA"] = _snap("NVDA", "BULLISH")
    await service.check(analyze)
    analyze.snaps["NVDA"] = _snap("NVDA", "BEARISH")
    await service.check(analyze)

    assert len(posted) == 1
    url, body = posted[0]
    assert url == "https://hooks.example/abc"
    assert "NVDA consensus BULLISH → BEARISH" in body["text"]
    assert body["content"] == body["text"]
    assert service.store.recent_events()[0].notified is True


# ── Market hours ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "when, expected",
    [
        (datetime(2026, 11, 18, 10, 0, tzinfo=ET), True),    # Wednesday mid-morning
        (datetime(2026, 11, 18, 9, 29, tzinfo=ET), False),   # before the open
        (datetime(2026, 11, 18, 16, 1, tzinfo=ET), False),   # after the close
        (datetime(2026, 11, 21, 12, 0, tzinfo=ET), False),   # Saturday
    ],
)
def test_is_market_open(when, expected):
    assert is_market_open(when) is expected
