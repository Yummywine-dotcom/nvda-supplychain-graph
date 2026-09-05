"""Validate the committed snapshot without starting the API."""

import json
import sys
from collections import Counter

from .config import snapshot_path
from .models import SnapshotModel
from .scoring import total_score


def main() -> int:
    path = snapshot_path()
    if not path.exists():
        print(json.dumps({"error_code": "DATA_MISSING", "message": str(path)}))
        return 1
    snapshot = SnapshotModel(**json.loads(path.read_text(encoding="utf-8")))
    types = Counter(rel.relation_type.value for rel in snapshot.relations)
    statuses = Counter(rel.fact_status.value for rel in snapshot.relations)
    for rel in snapshot.relations:
        assert total_score(rel.score_components.model_dump()) == rel.confidence_score
    print(json.dumps({
        "ok": True,
        "path": str(path),
        "cut_off_date": snapshot.metadata.cut_off_date.isoformat(),
        "relation_count": len(snapshot.relations),
        "relation_types": dict(types),
        "fact_status": dict(statuses),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
