"""
TrendEdge Backend - Watchlist Persistence & Signal-Change Alerts

Keeps the watchlist on the server (SQLite, stdlib only) so a background job
can re-score it on a schedule.  Each check compares every symbol's
multi-engine consensus with the last one stored; a change becomes an alert
event and is optionally posted to a Slack/Discord-compatible webhook.

Rules:
* The first observation of a symbol only records a baseline — no event.
* Results built from mocked (stale) data are ignored entirely, so a yfinance
  outage can never fake a signal flip.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx

WATCHLIST_MAX = 25
_ET = ZoneInfo("America/New_York")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    symbol         TEXT PRIMARY KEY,
    position       INTEGER NOT NULL,
    alerts_enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS signal_state (
    symbol     TEXT PRIMARY KEY,
    consensus  TEXT NOT NULL,
    price      REAL NOT NULL,
    checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL,
    previous   TEXT NOT NULL,
    current    TEXT NOT NULL,
    price      REAL NOT NULL,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    notified   INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass
class Snapshot:
    """What the alert check needs from one multi-engine analysis."""
    symbol: str
    consensus: str
    price: float
    buy_votes: int
    sell_votes: int
    stale: bool


@dataclass
class AlertEvent:
    id: int
    symbol: str
    previous: str
    current: str
    price: float
    message: str
    created_at: datetime
    notified: bool


Analyzer = Callable[[str], Awaitable[Optional[Snapshot]]]


def is_market_open(now: Optional[datetime] = None) -> bool:
    """Regular US session, Mon–Fri 09:30–16:00 ET (exchange holidays not excluded)."""
    now = (now or datetime.now(_ET)).astimezone(_ET)
    return now.weekday() < 5 and time(9, 30) <= now.time() <= time(16, 0)


class SignalAlertStore:
    """SQLite-backed watchlist, last-seen signals and alert history."""

    def __init__(self, db_path: str):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    # ── Watchlist ────────────────────────────────────────────

    def get_watchlist(self) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT symbol, alerts_enabled FROM watchlist ORDER BY position"
            ).fetchall()
        return [{"symbol": r["symbol"], "alerts_enabled": bool(r["alerts_enabled"])} for r in rows]

    def set_watchlist(self, symbols: List[str]) -> List[Dict]:
        """Replace the list, keeping each surviving symbol's alert toggle."""
        clean = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        if len(clean) > WATCHLIST_MAX:
            raise ValueError(f"Maximum {WATCHLIST_MAX} symbols allowed")
        with self._lock, self._conn:
            enabled = {
                r["symbol"]: r["alerts_enabled"]
                for r in self._conn.execute("SELECT symbol, alerts_enabled FROM watchlist")
            }
            self._conn.execute("DELETE FROM watchlist")
            self._conn.executemany(
                "INSERT INTO watchlist (symbol, position, alerts_enabled) VALUES (?, ?, ?)",
                [(s, i, enabled.get(s, 1)) for i, s in enumerate(clean)],
            )
            # Forget baselines of removed symbols so re-adding one starts fresh
            self._conn.execute(
                "DELETE FROM signal_state WHERE symbol NOT IN (SELECT symbol FROM watchlist)"
            )
        return self.get_watchlist()

    def set_alerts_enabled(self, symbol: str, enabled: bool) -> bool:
        """Toggle alerts for one symbol; False if it is not on the watchlist."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE watchlist SET alerts_enabled = ? WHERE symbol = ?",
                (int(enabled), symbol.strip().upper()),
            )
        return cur.rowcount > 0

    # ── Signal state & events ────────────────────────────────

    def last_consensus(self, symbol: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT consensus FROM signal_state WHERE symbol = ?", (symbol,)
            ).fetchone()
        return row["consensus"] if row else None

    def record(self, snap: Snapshot, now: datetime) -> Optional[AlertEvent]:
        """Store the latest consensus; return an event if it changed."""
        previous = self.last_consensus(snap.symbol)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO signal_state (symbol, consensus, price, checked_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET consensus = excluded.consensus, "
                "price = excluded.price, checked_at = excluded.checked_at",
                (snap.symbol, snap.consensus, snap.price, now.isoformat()),
            )
            if previous is None or previous == snap.consensus:
                return None
            message = (
                f"{snap.symbol} consensus {previous} → {snap.consensus} at ${snap.price:,.2f} "
                f"({snap.buy_votes} BUY / {snap.sell_votes} SELL)"
            )
            cur = self._conn.execute(
                "INSERT INTO alert_events (symbol, previous, current, price, message, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (snap.symbol, previous, snap.consensus, snap.price, message, now.isoformat()),
            )
        return AlertEvent(cur.lastrowid, snap.symbol, previous, snap.consensus,
                          snap.price, message, now, False)

    def mark_notified(self, event_ids: List[int]) -> None:
        if not event_ids:
            return
        with self._lock, self._conn:
            self._conn.executemany(
                "UPDATE alert_events SET notified = 1 WHERE id = ?", [(i,) for i in event_ids]
            )

    def recent_events(self, limit: int = 20) -> List[AlertEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM alert_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            AlertEvent(r["id"], r["symbol"], r["previous"], r["current"], r["price"],
                       r["message"], datetime.fromisoformat(r["created_at"]), bool(r["notified"]))
            for r in rows
        ]


class SignalAlertService:
    """Runs the watchlist check and delivers new events."""

    def __init__(self, store: SignalAlertStore, webhook_url: str = ""):
        self.store = store
        self.webhook_url = webhook_url
        self.last_run: Optional[datetime] = None
        self._running = threading.Lock()

    async def check(self, analyze: Analyzer) -> List[AlertEvent]:
        """Score every alert-enabled symbol and return the new events."""
        if not self._running.acquire(blocking=False):
            return []  # a check is already in flight
        try:
            symbols = [w["symbol"] for w in self.store.get_watchlist() if w["alerts_enabled"]]
            events: List[AlertEvent] = []
            for symbol in symbols:
                try:
                    snap = await analyze(symbol)
                except Exception as exc:  # one bad ticker must not stop the run
                    print(f"⚠️ alert check failed for {symbol}: {exc}")
                    continue
                if snap is None or snap.stale:
                    continue
                event = self.store.record(snap, datetime.now(timezone.utc))
                if event:
                    events.append(event)
            self.last_run = datetime.now(timezone.utc)
            if events:
                await self._notify(events)
            return events
        finally:
            self._running.release()

    async def _notify(self, events: List[AlertEvent]) -> None:
        if not self.webhook_url:
            return
        text = "📈 TrendEdge signal changes\n" + "\n".join(f"• {e.message}" for e in events)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # "text" is read by Slack, "content" by Discord
                resp = await client.post(self.webhook_url, json={"text": text, "content": text})
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"⚠️ alert webhook failed: {exc}")
            return
        self.store.mark_notified([e.id for e in events])


_service: Optional[SignalAlertService] = None


def get_signal_alert_service() -> SignalAlertService:
    global _service
    if _service is None:
        from app.core.config import get_settings

        settings = get_settings()
        _service = SignalAlertService(SignalAlertStore(settings.alerts_db_path),
                                      settings.alert_webhook_url)
    return _service
