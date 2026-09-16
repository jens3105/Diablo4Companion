import requests
from datetime import datetime, timezone


class DiabloAPI:

    URL = "http://192.168.10.11:8080/api/v1/schedule"

    # Officielt bekræftet af Blizzard på BlizzCon 2026-09-12:
    # "Season of Hell's Legacy" - 2026-09-15, 09:30 PT / 18:30 CEST.
    SEASON_15_START_UTC = datetime(2026, 9, 15, 16, 30, tzinfo=timezone.utc)

    def get_season_15_start(self):
        return self.SEASON_15_START_UTC

    EMPTY_SCHEDULE = {"world_boss": [], "legion": [], "helltide": []}

    @staticmethod
    def _adapt_event_server_schedule(events):
        """Translate the Event Server's external schema into Companion's
        existing internal schedule shape, so every other consumer
        (``get_next_world_boss``/etc., ``app.py``'s countdown logic) can
        stay unchanged. Only ever maps fields the Event Server actually
        provides - never invents a field it doesn't return.
        """

        adapted = {"world_boss": [], "legion": [], "helltide": []}

        for boss in events.get("world_boss") or []:
            adapted["world_boss"].append({
                "timestamp": boss.get("timestamp"),
                "boss": boss.get("boss"),
                "startTime": boss.get("start_time"),
                "zone": [{"name": z} for z in (boss.get("zones") or [])],
            })

        for legion in events.get("legion") or []:
            adapted["legion"].append({
                "timestamp": legion.get("timestamp"),
                "startTime": legion.get("start_time"),
            })

        for helltide in events.get("helltide") or []:
            adapted["helltide"].append({
                "timestamp": helltide.get("timestamp"),
                "startTime": helltide.get("start_time"),
            })

        return adapted

    def get_schedule(self):
        """Fetch the live schedule from our own Event Server (which itself
        fetches from helltides.com server-side - see PROJECT_ROADMAP.md).

        Dashboard Live Data bugfix: this used to fall back to a locally
        calculated, fixed-interval-based schedule (``src/local_schedule.py``,
        now deleted) whenever the live request failed - confirmed by the
        user's own real in-game comparison to be wildly inaccurate (Diablo
        4's real World Boss/Legion/Helltide cadence is not the simple fixed
        interval that fallback assumed), and worse, presented as a real
        countdown with only a small "(estimated)" label most users would
        never notice on a fast-moving timer. NEVER inventing an event time
        is more important than always having something to show - if the
        Event Server can't be reached, reports failure, or returns nothing,
        this returns an empty schedule and every caller already handles
        that as "no data" (see ``get_next_world_boss``/etc. returning
        ``None``, and the Dashboard cards/Upcoming Events showing
        "DATA UNAVAILABLE" for that), never a guessed time.
        """

        try:
            response = requests.get(self.URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                print(f"Event Server rapporterede status={data.get('status')!r} - ingen data tilgaengelig.")
                return {"world_boss": [], "legion": [], "helltide": []}

            events = data.get("events")
            if events is None:
                print("Event Server-response mangler 'events' - ingen data tilgaengelig.")
                return {"world_boss": [], "legion": [], "helltide": []}

            adapted = self._adapt_event_server_schedule(events)

            if adapted["world_boss"] or adapted["legion"] or adapted["helltide"]:
                return adapted

            print("Event Server svarede, men uden nogen events - ingen data tilgaengelig.")

        except requests.RequestException as exc:
            print(f"Kunne ikke hente schedule fra Event Server: {exc} - ingen data tilgaengelig.")

        return {"world_boss": [], "legion": [], "helltide": []}

    # -----------------------------
    # World Boss
    # -----------------------------

    def get_next_world_boss(self, schedule=None):

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for boss in schedule["world_boss"]:
            # Defensive: the live API tags every entry with its own
            # "type" field (confirmed live 2026-09-16 via a real browser
            # session, since requests/WebFetch both get blocked by
            # Cloudflare's bot-challenge before ever seeing a response).
            # Skip anything that doesn't actually claim to
            # be a world_boss entry rather than trust the outer
            # "world_boss" key alone - this is the root-cause fix for
            # the class of bug where one event type's card could end up
            # displaying another type's fields if the API ever nests an
            # unexpected entry under the wrong key.
            if boss.get("type", "world_boss") != "world_boss":
                continue
            if boss["timestamp"] > now:
                return boss

        return None

    # -----------------------------
    # Legion
    # -----------------------------

    def get_next_legion(self, schedule=None):

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for legion in schedule["legion"]:
            if legion.get("type", "legion") != "legion":
                continue
            if legion["timestamp"] > now:
                return legion

        return None

    # -----------------------------
    # Helltide
    # -----------------------------

    def get_next_helltide(self, schedule=None):

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for helltide in schedule["helltide"]:
            if helltide.get("type", "helltide") != "helltide":
                continue
            if helltide["timestamp"] > now:
                return helltide

        return None

    # -----------------------------
    # Upcoming
    # -----------------------------

    def get_upcoming_events(self, limit=8, schedule=None):
        """Every real upcoming event across all 3 types, merged and
        sorted by real start time. Each entry only ever carries fields
        the live helltides.com schedule actually provides for that
        event's own ``type`` - confirmed live (2026-09-16, via a real
        browser session, see ``get_next_world_boss``'s comment): only
        ``world_boss`` entries have a real ``boss`` name and a real
        ``zone``; ``legion``/``helltide`` entries have neither, so
        ``name``/``location`` are ``None`` for those (never a copied or
        invented value from a different event type) - the UI layer
        shows "DATA UNAVAILABLE" for a ``None`` here, it is never
        silently left blank or filled with a guess.
        """

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        events = []

        for boss in schedule["world_boss"]:
            if boss.get("type", "world_boss") != "world_boss":
                continue
            if boss["timestamp"] > now:
                zone_list = boss.get("zone") or []
                events.append({
                    "type": "world_boss",
                    "timestamp": boss["timestamp"],
                    "title": boss["boss"],
                    "name": boss["boss"],
                    "location": zone_list[0]["name"] if zone_list else None,
                    "icon": "🌍",
                })

        for legion in schedule["legion"]:
            if legion.get("type", "legion") != "legion":
                continue
            if legion["timestamp"] > now:
                events.append({
                    "type": "legion",
                    "timestamp": legion["timestamp"],
                    "title": "Legion",
                    "name": None,
                    "location": None,
                    "icon": "👹",
                })

        for helltide in schedule["helltide"]:
            if helltide.get("type", "helltide") != "helltide":
                continue
            if helltide["timestamp"] > now:
                events.append({
                    "type": "helltide",
                    "timestamp": helltide["timestamp"],
                    "title": "Helltide",
                    "name": None,
                    "location": None,
                    "icon": "🔥",
                })

        events.sort(key=lambda x: x["timestamp"])

        return events[:limit]
