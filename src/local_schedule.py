"""Locally-calculated fallback schedule for World Boss / Helltide / Legion.

helltides.com's ``/api/schedule`` endpoint sits behind a Cloudflare
managed bot-challenge that plain HTTP clients (``requests``, and even
``cloudscraper``) cannot get past - this affects any machine hitting it,
not just this dev box or a particular network/VPN. Rather than showing
"waiting for data..." forever whenever that happens, we fall back to a
locally-calculated schedule based on Diablo IV's fixed, publicly known
event cadences:

- Legion: a fixed 25-minute cycle.
- Helltide: a fixed hourly cycle, active ~55 minutes per hour.
- World Boss: fixed ~2-hour UTC spawn windows every 6 hours
  (04:30-06:30, 10:30-12:30, 16:30-18:30, 22:30-00:30 UTC), cycling
  through Ashava / Wandering Death / Avarice in a repeating run-length
  pattern of 3,2,3,2,3,2 windows per boss.

Every entry produced here is tagged ``"estimated": True`` so the UI can
make it clear this is a calculated estimate, not a value confirmed by
the live API. The World Boss anchor/pattern is sourced from the
publicly documented spawn logic of the open-source Diablo.NET project
(WorldBossSpawnService / WorldBossSequencer); the Helltide/Legion
cadences are widely-cited community knowledge, not tied to a confirmed
official anchor timestamp, so their exact minute-of-hour alignment is a
best-effort estimate rather than a guarantee.
"""

import math
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

# ---------------------------------------------------------------------
# World Boss
# ---------------------------------------------------------------------

# Reference anchor ("BigBang") from the Diablo.NET world boss spawn
# service, rounded down to the start of its 2-hour window.
_WORLD_BOSS_REFERENCE = datetime(2023, 6, 2, 4, 30, 0, tzinfo=UTC)
_WORLD_BOSS_INTERVAL = timedelta(hours=6)
_WORLD_BOSS_WINDOW_DURATION = timedelta(hours=2)

_WORLD_BOSS_ORDER = ["Ashava", "Wandering Death", "Avarice"]
_WORLD_BOSS_COUNTS = [3, 2, 3, 2, 3, 2]

_WORLD_BOSS_SEQUENCE = []
for _i, _count in enumerate(_WORLD_BOSS_COUNTS):
    _WORLD_BOSS_SEQUENCE.extend([_WORLD_BOSS_ORDER[_i % len(_WORLD_BOSS_ORDER)]] * _count)

_WORLD_BOSS_ZONES = {
    "Ashava": "Fractured Peaks",
    "Wandering Death": "Dry Steppes",
    "Avarice": "Kehjistan",
}


def _world_boss_window(n: int):
    """Return (boss, start, end) for window index ``n`` (can be any int)."""

    start = _WORLD_BOSS_REFERENCE + n * _WORLD_BOSS_INTERVAL
    end = start + _WORLD_BOSS_WINDOW_DURATION
    boss = _WORLD_BOSS_SEQUENCE[n % len(_WORLD_BOSS_SEQUENCE)]

    return boss, start, end


def _world_boss_entry(n: int):

    boss, start, _end = _world_boss_window(n)

    return {
        "boss": boss,
        "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp": start.timestamp(),
        "zone": [{"name": _WORLD_BOSS_ZONES.get(boss, "Sanctuary")}],
        "estimated": True,
    }


def world_boss_entries(now: datetime, count: int = 4):

    elapsed = (now - _WORLD_BOSS_REFERENCE) / _WORLD_BOSS_INTERVAL
    start_n = math.floor(elapsed) + 1

    return [_world_boss_entry(start_n + i) for i in range(count)]


# ---------------------------------------------------------------------
# Legion
# ---------------------------------------------------------------------

_LEGION_REFERENCE = datetime(2023, 6, 6, 0, 0, 0, tzinfo=UTC)
_LEGION_PERIOD = timedelta(minutes=25)


def _legion_entry(n: int):

    start = _LEGION_REFERENCE + n * _LEGION_PERIOD

    return {
        "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp": start.timestamp(),
        "estimated": True,
    }


def legion_entries(now: datetime, count: int = 10):

    elapsed = (now - _LEGION_REFERENCE) / _LEGION_PERIOD
    start_n = math.floor(elapsed) + 1

    return [_legion_entry(start_n + i) for i in range(count)]


# ---------------------------------------------------------------------
# Helltide
# ---------------------------------------------------------------------

_HELLTIDE_ACTIVE_MINUTES = 55


def _helltide_entry(hour_start: datetime):

    return {
        "startTime": hour_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp": hour_start.timestamp(),
        "activeMinutes": _HELLTIDE_ACTIVE_MINUTES,
        "estimated": True,
    }


def helltide_entries(now: datetime, count: int = 6):

    first = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    return [_helltide_entry(first + timedelta(hours=i)) for i in range(count)]


# ---------------------------------------------------------------------
# Combined schedule (same shape as helltides.com's live API response)
# ---------------------------------------------------------------------

def build_schedule(now: datetime = None):

    now = now or datetime.now(UTC)

    return {
        "world_boss": world_boss_entries(now),
        "legion": legion_entries(now),
        "helltide": helltide_entries(now),
    }
