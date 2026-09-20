"""Boss database for the Unique Drop Locations page.

No Qt imports here on purpose - kept independently testable, same
separation principle as builds/*.json vs. the interfaces that read them.

Each boss's ``id`` is the stable key that the server's drop-source
``target_bosses`` lists reference - never duplicate a boss's loot list
here AND on the unique side; src/unique_drop_service.py computes
records name, so there is exactly one
place that relationship is recorded (the Unique's own target_bosses).

Verified against Icy-Veins' Season 15 Lair Boss guide and aoeah.com's
independent Season 15 boss table (2-source cross-check on tier/location/
key for every "Lair Boss" entry). General drop rule confirmed by
Icy-Veins (quoted): "The first Unique item that drops from a Lair Boss
is guaranteed to come from that boss' specific loot pool" - additional
drops in the same run have roughly a 50% chance of being boss-specific
vs. the general Unique pool instead.

Astaroth and Bartuc are NOT on the tiered "Lair Boss" ladder - they are
standalone rewards from the Escalating Nightmares and Infernal Hordes
activities respectively, confirmed by the same sources.
"""

BOSSES: list[dict] = [
    {
        "id": "urivar",
        "name": "Urivar",
        "tier": "Initiate (Tier 1) Lair Boss",
        "location": "Nahantu, Fields of Judgement, west of Kichuk",
        "key": "1x Lair Key",
        "key_source": "War Plans, Helltide, World Bosses, Legion Events, Tree of Whispers Cache",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "High",
    },
    {
        "id": "grigoire",
        "name": "Grigoire, The Galvanic Saint",
        "tier": "Initiate (Tier 1) Lair Boss",
        "location": "Dry Steppes, Hall of the Penitent, south of Ked Bardu",
        "key": "1x Lair Key",
        "key_source": "War Plans, Helltide, World Bosses, Legion Events, Tree of Whispers Cache",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "High",
    },
    {
        "id": "the_beast_in_the_ice",
        "name": "The Beast in the Ice",
        "tier": "Initiate (Tier 1) Lair Boss",
        "location": "Fractured Peaks, Glacial Fissure, SW of Kyovashad",
        "key": "1x Lair Key",
        "key_source": "War Plans, Helltide, World Bosses, Legion Events, Tree of Whispers Cache",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "High",
    },
    {
        "id": "echo_of_varshan",
        "name": "Echo of Varshan",
        "tier": "Initiate (Tier 1) Lair Boss",
        "location": "Hawezar, Malignant Burrow, near Tree of Whispers Waypoint",
        "key": "1x Lair Key",
        "key_source": "War Plans, Helltide, World Bosses, Legion Events, Tree of Whispers Cache",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "High",
    },
    {
        "id": "lord_zir",
        "name": "Lord Zir",
        "tier": "Initiate (Tier 1) Lair Boss",
        "location": "Fractured Peaks, Ancient's Seat, Darkened Way, east of Kyovashad",
        "key": "1x Lair Key",
        "key_source": "War Plans, Helltide, World Bosses, Legion Events, Tree of Whispers Cache",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "High",
    },
    {
        "id": "duriel_king_of_maggots",
        "name": "Duriel, King of Maggots",
        "tier": "Greater (Tier 2) Lair Boss",
        "location": "Kehjistan, Gaping Crevasse, east of Gea Kul",
        "key": "1x Greater Lair Key",
        "key_source": "Drops from Initiate Lair Bosses, or crafted 1:1 from Stygian Stones",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "High",
    },
    {
        "id": "harbinger_of_hatred",
        "name": "Harbinger of Hatred",
        "tier": "Greater (Tier 2) Lair Boss",
        "location": "Nahantu, Harbinger's Den, south of Kurast Docks",
        "key": "1x Greater Lair Key",
        "key_source": "Drops from Initiate Lair Bosses, or crafted 1:1 from Stygian Stones",
        "source": "Icy-Veins, aoeah.com, Game8",
        "confidence": "High",
    },
    {
        "id": "echo_of_andariel",
        "name": "Echo of Andariel",
        "tier": "Greater (Tier 2) Lair Boss",
        "location": "Kehjistan, Hanged Man's Hall, east of Tarsarak",
        "key": "1x Greater Lair Key",
        "key_source": "Drops from Initiate Lair Bosses, or crafted 1:1 from Stygian Stones",
        "source": "aoeah.com",
        "confidence": "Medium",
    },
    {
        "id": "the_butcher",
        "name": "The Butcher",
        "tier": "Greater (Tier 2) Lair Boss",
        "location": "Nahantu, near Kurast Docks Waypoint",
        "key": "1x Greater Lair Key",
        "key_source": "Drops from Initiate Lair Bosses, or crafted 1:1 from Stygian Stones",
        "source": "Icy-Veins, aoeah.com, DiabloFilter",
        "confidence": "High",
    },
    {
        "id": "belial",
        "name": "Belial",
        "tier": "Exalted (Tier 3) Lair Boss",
        "location": "Kehjistan, Palace of the Deceiver, west of Tarsarak Waypoint",
        "key": "2x Betrayer's Husk",
        "key_source": "High Torment-difficulty endgame activities",
        "source": "Icy-Veins, aoeah.com",
        "confidence": "Medium",
    },
    {
        "id": "echo_of_mephisto",
        "name": "Echo of Mephisto",
        "tier": "Pinnacle Lair Boss",
        "location": "Skovos Isles, The Birthplace",
        "key": "1x Crux of the False Prophet",
        "key_source": "High Torment-difficulty endgame activities",
        "mythic_note": (
            "Guarantees one Mythic Unique per kill from the general Mythic pool - not a "
            "specific item, and not the only way to obtain a Mythic (see Season 15's Iconic "
            "Mythic crafting, e.g. Harlequin Crest's own notes)."
        ),
        "source": "aoeah.com",
        "confidence": "Medium",
    },
    {
        "id": "astaroth",
        "name": "Astaroth",
        "tier": "Not on the Lair Boss ladder - Escalating Nightmares reward",
        "location": "Scosglen, Cerrigar, final boss of an Escalating Nightmares run",
        "key": "1x Escalation Sigil",
        "key_source": "Escalating Nightmares activity",
        "source": "aoeah.com",
        "confidence": "Medium",
    },
    {
        "id": "bartuc_lord_of_chaos",
        "name": "Bartuc, Lord of Chaos",
        "tier": "Not on the Lair Boss ladder - Infernal Hordes reward",
        "location": "Kehjistan, near Yshari Sanctum Waypoint, end of an Infernal Hordes run",
        "key": "1x Infernal Hordes Compass + 666 Burning Aether",
        "key_source": "Infernal Hordes activity",
        "source": "aoeah.com",
        "confidence": "Medium",
    },
]
