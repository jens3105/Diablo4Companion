"""Pure data + geometry helpers for the Hellwyrm Location Guide.

No Qt imports here on purpose - this stays independently testable and
keeps the Dashboard's Hellwyrm panel's data fully separate from the
widget code that draws it (same separation principle as builds/*.json
vs. the interfaces that read them).

Every entry in HELLWYRM_AREAS comes from cross-referencing at least two
independently published, publicly available player guides that do not
cite each other, and that agree on both the named waypoint and the
general compass direction. Nothing here is a coordinate copied from
any map/tracker site - "directions" is just the compass-word sequence
those guides describe in prose. resolve_path() below turns that prose
into a purely SCHEMATIC visual position for our own original diagram.
It is NOT a claim about a real in-game position, distance, or scale -
see HellwyrmCard's permanent on-screen disclaimer. Regions without two
agreeing independent sources are intentionally left out of
HELLWYRM_AREAS - the UI shows DATA UNAVAILABLE for those rather than a
guessed entry.
"""

import math

REGION_ORDER = [
    "Fractured Peaks",
    "Scosglen",
    "Dry Steppes",
    "Hawezar",
    "Kehjistan",
]

HELLWYRM_AREAS = {
    "Fractured Peaks": {
        "landmark": "Menestad",
        "directions": ["south", "northeast"],
        "description": (
            "Multiple independently published player guides describe a "
            "Hellwyrm farming route starting at the Menestad waypoint, "
            "heading south and then turning northeast. This diagram shows "
            "that documented direction only - not an exact spawn point."
        ),
        "sources": 3,
        "confidence": "High",
    },
    "Dry Steppes": {
        "landmark": "Girandai",
        "directions": ["center", "east"],
        "description": (
            "Multiple independently published player guides describe a "
            "Hellwyrm farming route starting at the Girandai waypoint, "
            "moving toward the zone's center and then heading east. This "
            "diagram shows that documented direction only - not an exact "
            "spawn point."
        ),
        "sources": 2,
        "confidence": "High",
    },
    # Scosglen, Hawezar, Kehjistan: no two independently-written sources
    # agreed on the same waypoint + direction yet (see research notes) -
    # left out deliberately rather than guessed.
}

# Unit vectors for an 8-point compass plus "center" (no movement). A
# fixed, arbitrary visual convention (y grows downward, matching Qt's
# scene coordinates) - not a claim about real in-game geometry.
_DIAG = math.sqrt(2) / 2
DIRECTION_VECTORS = {
    "north": (0.0, -1.0),
    "northeast": (_DIAG, -_DIAG),
    "east": (1.0, 0.0),
    "southeast": (_DIAG, _DIAG),
    "south": (0.0, 1.0),
    "southwest": (-_DIAG, _DIAG),
    "west": (-1.0, 0.0),
    "northwest": (-_DIAG, -_DIAG),
    "center": (0.0, 0.0),
}

# Scene size every region's diagram uses (see HellwyrmCard).
SCENE_WIDTH = 1000.0
SCENE_HEIGHT = 700.0

# The waypoint reference point sits at the center of the scene for
# every region, since no source documents where a waypoint actually
# sits within its region - any other fixed choice would imply a
# position we don't have. See PROJECT research notes.
ORIGIN = (SCENE_WIDTH / 2, SCENE_HEIGHT / 2)

# Purely a layout constant for our own original diagram (how far apart
# to draw one documented directional "hop") - not a real distance and
# not a map scale. See HellwyrmCard's permanent disclaimer.
STEP_LENGTH = 220.0


def resolve_path(directions, origin=ORIGIN, step=STEP_LENGTH):
    """Turn a documented compass-word sequence into a list of purely
    schematic (x, y) points for our own diagram, starting at ``origin``.
    Never represents a real position - see module docstring."""

    points = [origin]
    x, y = origin
    for word in directions:
        dx, dy = DIRECTION_VECTORS[word]
        x, y = x + dx * step, y + dy * step
        points.append((x, y))
    return points
