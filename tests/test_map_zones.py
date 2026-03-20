# Run: pytest tests/test_map_zones.py
"""Tests for map_01.json zone music_track configuration.

Every zone in map_01.json must declare a non-null ``music_track`` path so
that AudioSystem can start the correct background loop when the player
crosses into that zone.  These tests guard against a regression where all
three zones had ``music_track: null``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_MAP_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "maps" / "map_01.json"
)


@pytest.fixture(scope="module")
def map_data():
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def zones(map_data):
    return map_data["zones"]


# ---------------------------------------------------------------------------
# Zone inventory
# ---------------------------------------------------------------------------

class TestMapZoneNames:
    def test_map_has_exactly_three_zones(self, zones):
        assert len(zones) == 3

    def test_hangar_bay_zone_exists(self, zones):
        names = [z["name"] for z in zones]
        assert "HANGAR BAY" in names

    def test_reactor_core_zone_exists(self, zones):
        names = [z["name"] for z in zones]
        assert "REACTOR CORE" in names

    def test_extraction_pad_zone_exists(self, zones):
        names = [z["name"] for z in zones]
        assert "EXTRACTION PAD" in names

    def test_zone_names_are_unique(self, zones):
        names = [z["name"] for z in zones]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Zone music_track values
# ---------------------------------------------------------------------------

class TestMapZoneMusicTracks:
    def test_all_zones_have_non_null_music_track(self, zones):
        """No zone may have music_track: null — that would silence the game."""
        for zone in zones:
            assert zone.get("music_track") is not None, (
                f"Zone {zone['name']!r} has music_track: null"
            )

    def test_all_music_tracks_are_strings(self, zones):
        for zone in zones:
            assert isinstance(zone["music_track"], str), (
                f"Zone {zone['name']!r} music_track is not a string"
            )

    def test_all_music_tracks_are_ogg_files(self, zones):
        for zone in zones:
            track = zone["music_track"]
            assert track.endswith(".ogg"), (
                f"Zone {zone['name']!r} music_track {track!r} must end in .ogg"
            )

    def test_all_music_tracks_are_non_empty(self, zones):
        for zone in zones:
            assert zone["music_track"].strip(), (
                f"Zone {zone['name']!r} has an empty music_track string"
            )

    def test_music_tracks_are_unique_per_zone(self, zones):
        """Each zone should have a distinct track so transitions are audible."""
        tracks = [z["music_track"] for z in zones]
        assert len(tracks) == len(set(tracks)), (
            "Two or more zones share the same music_track"
        )

    def test_hangar_bay_uses_zone_alpha_track(self, zones):
        hangar = next(z for z in zones if z["name"] == "HANGAR BAY")
        assert "zone_alpha" in hangar["music_track"]

    def test_reactor_core_uses_zone_beta_track(self, zones):
        reactor = next(z for z in zones if z["name"] == "REACTOR CORE")
        assert "zone_beta" in reactor["music_track"]

    def test_extraction_pad_uses_zone_gamma_track(self, zones):
        extraction = next(z for z in zones if z["name"] == "EXTRACTION PAD")
        assert "zone_gamma" in extraction["music_track"]

    def test_all_tracks_reference_music_subdirectory(self, zones):
        """Tracks must live under a music/ directory so asset paths are correct."""
        for zone in zones:
            assert "music" in zone["music_track"], (
                f"Zone {zone['name']!r} track {zone['music_track']!r} "
                "does not reference the music/ directory"
            )
