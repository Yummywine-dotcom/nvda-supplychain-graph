import json

from src.models import SnapshotModel
from src.scoring import total_score


def test_snapshot_scores_match_components():
    with open("data/snapshot_nvda.json", encoding="utf-8") as handle:
        snapshot = SnapshotModel(**json.load(handle))
    types = {rel.relation_type.value for rel in snapshot.relations}
    statuses = {rel.fact_status.value for rel in snapshot.relations}
    assert types == {
        "supplier",
        "customer",
        "partner",
        "investor_or_investee",
        "peer",
    }
    assert "Confirmed Fact" in statuses
    assert "Reasonable Inference" in statuses
    assert "Unknown" in statuses
    for rel in snapshot.relations:
        assert total_score(rel.score_components.model_dump()) == rel.confidence_score
        assert rel.evidence.access_time.date() <= snapshot.metadata.cut_off_date
        assert rel.relation_id
    named = {rel.target_ticker for rel in snapshot.relations}
    for ticker in {
        "NYSE: TSM",
        "KRX: 005930",
        "NASDAQ: MU",
        "KRX: 000660",
        "TWSE: 2317",
        "TWSE: 3231",
        "NYSE: FN",
        "NASDAQ: CRWV",
        "NASDAQ: SPCX",
    }:
        assert ticker in named
