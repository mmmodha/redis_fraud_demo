"""Tests for backend.app.agent_memory.

Uses ``fakeredis[json]`` so the suite does not require a live Redis Cloud
database. The "container restart" durability test simulates a restart by
discarding the client and re-opening a fresh one against the same fake server
(equivalent to a fresh TCP connection to the same Redis instance).
"""

from __future__ import annotations

from datetime import date, timedelta

import fakeredis
import pytest

from backend.app import agent_memory as am
from data import heroes
from data.seed_memory import _canonicalise


@pytest.fixture
def server() -> fakeredis.FakeServer:
    """A single fake-server instance shared across client reconnects."""
    return fakeredis.FakeServer()


@pytest.fixture
def client(server: fakeredis.FakeServer) -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(server=server, decode_responses=True)


def test_get_memory_returns_empty_skeleton_for_unknown_customer(client):
    doc = am.get_memory(client, "cust_unknown")
    assert doc["customer_id"] == "cust_unknown"
    assert doc["travel_windows"] == []
    assert doc["prior_disputes"] == []
    assert doc["flagged_devices"] == []
    assert doc["conversation_notes"] == []


def test_append_conversation_note_initialises_and_appends(client):
    am.append_conversation_note(client, "cust_jane", "Mentioned trip", source="chat")
    am.append_conversation_note(client, "cust_jane", "Confirmed Singapore", source="agent")
    doc = am.get_memory(client, "cust_jane")
    assert [n["text"] for n in doc["conversation_notes"]] == [
        "Mentioned trip",
        "Confirmed Singapore",
    ]
    assert {n["source"] for n in doc["conversation_notes"]} == {"chat", "agent"}


def test_add_travel_window_dispute_device(client):
    am.add_travel_window(
        client, "cust_jane", "2099-01-01", "2099-01-10", ["Tokyo"], source="chat"
    )
    am.add_dispute(
        client, "cust_jane", "tx_x", "duplicate_charge", "refunded", "2026-05-01"
    )
    am.add_flagged_device(client, "cust_jane", "dev_x", "new_geo")
    doc = am.get_memory(client, "cust_jane")
    assert doc["travel_windows"][0]["destinations"] == ["Tokyo"]
    assert doc["prior_disputes"][0]["resolution"] == "refunded"
    assert doc["flagged_devices"][0]["device_id"] == "dev_x"
    assert doc["flagged_devices"][0]["flagged_at"]  # server-set timestamp


def test_invalid_dates_are_rejected(client):
    with pytest.raises(ValueError):
        am.add_travel_window(client, "cust_jane", "not-a-date", "2099-01-10", ["X"])
    with pytest.raises(ValueError):
        am.add_dispute(client, "cust_jane", "tx_x", "r", "res", "31/12/2026")


def test_expired_travel_windows_filtered_on_read(client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    last_week = (date.today() - timedelta(days=7)).isoformat()
    future = (date.today() + timedelta(days=30)).isoformat()
    am.add_travel_window(client, "cust_jane", last_week, yesterday, ["Past"])
    am.add_travel_window(client, "cust_jane", date.today().isoformat(), future, ["Future"])
    doc = am.get_memory(client, "cust_jane")
    destinations = [w["destinations"] for w in doc["travel_windows"]]
    assert destinations == [["Future"]]


def test_purge_expired_travel_windows_rewrites_in_place(client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    last_week = (date.today() - timedelta(days=7)).isoformat()
    future = (date.today() + timedelta(days=30)).isoformat()
    am.add_travel_window(client, "cust_a", last_week, yesterday, ["Past"])
    am.add_travel_window(client, "cust_a", date.today().isoformat(), future, ["Future"])
    am.add_travel_window(client, "cust_b", last_week, yesterday, ["GonePast"])
    removed = am.purge_expired_travel_windows(client)
    assert removed == 2
    # Use get_memory (which normalises path-unwrap differences) for assertions.
    doc_a = am.get_memory(client, "cust_a")
    assert [w["destinations"] for w in doc_a["travel_windows"]] == [["Future"]]
    doc_b = am.get_memory(client, "cust_b")
    assert doc_b["travel_windows"] == []


def test_memory_survives_container_restart(server):
    """Write through one client, drop it, reopen — data still there."""
    writer = fakeredis.FakeRedis(server=server, decode_responses=True)
    am.append_conversation_note(writer, "cust_jane", "before restart", source="agent")
    am.add_flagged_device(writer, "cust_jane", "dev_lost", "test_marker")
    del writer  # simulate container teardown

    reader = fakeredis.FakeRedis(server=server, decode_responses=True)
    doc = am.get_memory(reader, "cust_jane")
    assert any(n["text"] == "before restart" for n in doc["conversation_notes"])
    assert any(d["device_id"] == "dev_lost" for d in doc["flagged_devices"])


def test_jane_seed_canonicalises_to_visible_travel_window(client):
    """Mirrors what ``data/seed_memory.py`` does to Jane's JSONB seed row."""
    canonical = _canonicalise(heroes.JANE.customer_id, heroes.JANE_MEMORY_SEED)
    assert client.json().set(f"mem:{heroes.JANE.customer_id}", "$", canonical, nx=True)
    doc = am.get_memory(client, heroes.JANE.customer_id)

    assert len(doc["travel_windows"]) == 1
    window = doc["travel_windows"][0]
    assert window["start_date"] == "2026-11-10"
    assert window["end_date"] == "2026-11-17"
    assert "Singapore" in window["destinations"]
    assert window["source"] == "seed"
    assert any(
        "travelling 10-17 Nov" in n["text"].lower() or
        "10-17 nov" in n["text"].lower()
        for n in doc["conversation_notes"]
    )


def test_seed_is_idempotent_via_nx(client):
    """Re-running the seed must not clobber later writes."""
    canonical = _canonicalise(heroes.JANE.customer_id, heroes.JANE_MEMORY_SEED)
    client.json().set(f"mem:{heroes.JANE.customer_id}", "$", canonical, nx=True)
    am.append_conversation_note(
        client, heroes.JANE.customer_id, "analyst checked in", source="analyst"
    )
    # Second seed attempt — should be a no-op because of NX.
    assert not client.json().set(
        f"mem:{heroes.JANE.customer_id}", "$", canonical, nx=True
    )
    doc = am.get_memory(client, heroes.JANE.customer_id)
    texts = [n["text"] for n in doc["conversation_notes"]]
    assert "analyst checked in" in texts
