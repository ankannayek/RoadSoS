from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import mci
from app.services.supergraph import _cluster_semantics_are_consistent


class _NoRedisCache:
    async def get(self, key):
        return None


@pytest.mark.asyncio
async def test_register_sos_in_geohash_counts_unique_members(monkeypatch):
    monkeypatch.setattr(mci, "cache", _NoRedisCache())
    mci._LOCAL_CELLS.clear()
    cell = mci.mci_geohash_cell(13.0067, 80.2206)

    assert await mci.register_sos_in_geohash(13.0067, 80.2206, "incident-1", cell=cell) == 1
    assert await mci.register_sos_in_geohash(13.0067, 80.2206, "incident-1", cell=cell) == 1
    assert await mci.register_sos_in_geohash(13.0068, 80.2207, "incident-2", cell=cell) == 2


@pytest.mark.asyncio
async def test_mci_threshold_defaults_on_bad_runtime_value(monkeypatch):
    class BadThresholdCache:
        async def get(self, key):
            return "not-an-int"

    monkeypatch.setattr(mci, "cache", BadThresholdCache())
    assert await mci.get_mci_threshold() == mci.DEFAULT_MCI_THRESHOLD


def test_mci_resource_estimate_is_actionable_for_minimum_cluster():
    estimate = mci.mci_resource_estimate(3, avg_priority=2.0)

    assert estimate["estimated_victims"] == 3
    assert estimate["ambulances_recommended"] >= 2
    assert estimate["triage_protocol"] == "START"


def test_supergraph_semantic_check_rejects_unrelated_cluster():
    rows = [
        SimpleNamespace(description="bus crash with passengers injured"),
        SimpleNamespace(description="heart attack in apartment"),
        SimpleNamespace(description="robbery with weapon visible"),
    ]

    assert _cluster_semantics_are_consistent(rows) is False


def test_supergraph_semantic_check_accepts_traffic_cluster():
    rows = [
        SimpleNamespace(description="bus crash with passengers injured"),
        SimpleNamespace(description="vehicle collision near the junction"),
        SimpleNamespace(description="car accident, multiple people hurt"),
    ]

    assert _cluster_semantics_are_consistent(rows) is True
