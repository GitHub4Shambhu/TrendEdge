"""
TrendEdge Backend - Watchlist Alert Routes

Server-side watchlist plus the signal-change alert feed.  The scheduled
check itself is started from the app lifespan (see ``run_alert_scheduler``).
"""

import asyncio
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.dashboard import _analyze_all_engines
from app.core.config import get_settings
from app.schemas.momentum import (
    AlertEventResult,
    AlertEventsResponse,
    AlertToggleRequest,
    SavedWatchlistEntry,
    SavedWatchlistResponse,
    SavedWatchlistUpdate,
)
from app.services.signal_alerts import Snapshot, get_signal_alert_service, is_market_open

router = APIRouter(prefix="/alerts", tags=["Alerts"])


async def analyze_snapshot(symbol: str) -> Optional[Snapshot]:
    """Adapt the multi-engine lookup to what the alert check compares."""
    r = await _analyze_all_engines(symbol)
    if r is None:
        return None
    return Snapshot(
        symbol=r.symbol,
        consensus=r.consensus,
        price=r.price,
        buy_votes=r.buy_votes,
        sell_votes=r.sell_votes,
        stale=r.data_source == "stale",
    )


async def run_alert_scheduler() -> None:
    """Check the watchlist every N minutes while the US market is open."""
    settings = get_settings()
    service = get_signal_alert_service()
    while True:
        if is_market_open():
            try:
                events = await service.check(analyze_snapshot)
                if events:
                    print(f"🔔 {len(events)} watchlist signal change(s)")
            except Exception as exc:
                print(f"⚠️ scheduled alert check failed: {exc}")
        await asyncio.sleep(settings.alert_check_minutes * 60)


@router.get("/watchlist", response_model=SavedWatchlistResponse)
async def get_saved_watchlist():
    """The persisted watchlist, in display order."""
    return SavedWatchlistResponse(
        symbols=[SavedWatchlistEntry(**w) for w in get_signal_alert_service().store.get_watchlist()]
    )


@router.put("/watchlist", response_model=SavedWatchlistResponse)
async def save_watchlist(body: SavedWatchlistUpdate):
    """Replace the persisted watchlist (alert toggles of kept symbols survive)."""
    try:
        saved = get_signal_alert_service().store.set_watchlist(body.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SavedWatchlistResponse(symbols=[SavedWatchlistEntry(**w) for w in saved])


@router.patch("/watchlist/{symbol}", response_model=SavedWatchlistResponse)
async def toggle_alerts(symbol: str, body: AlertToggleRequest):
    """Turn signal-change alerts on or off for one watchlist symbol."""
    store = get_signal_alert_service().store
    if not store.set_alerts_enabled(symbol, body.alerts_enabled):
        raise HTTPException(status_code=404, detail=f"{symbol.upper()} is not on the watchlist")
    return SavedWatchlistResponse(symbols=[SavedWatchlistEntry(**w) for w in store.get_watchlist()])


def _events_response(limit: int) -> AlertEventsResponse:
    service = get_signal_alert_service()
    return AlertEventsResponse(
        events=[AlertEventResult(**asdict(e)) for e in service.store.recent_events(limit)],
        last_check=service.last_run,
        market_open=is_market_open(),
        webhook_configured=bool(service.webhook_url),
    )


@router.get("/events", response_model=AlertEventsResponse)
async def alert_events(limit: int = Query(20, ge=1, le=100)):
    """Most recent consensus changes, newest first."""
    return _events_response(limit)


@router.post("/check", response_model=AlertEventsResponse)
async def check_now(limit: int = Query(20, ge=1, le=100)):
    """Run the watchlist check immediately (ignores market hours)."""
    await get_signal_alert_service().check(analyze_snapshot)
    return _events_response(limit)
