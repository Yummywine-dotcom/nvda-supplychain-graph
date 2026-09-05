import argparse
import json
import sys
from datetime import date

from .config import snapshot_path
from .models import FactStatus, RelationType, SnapshotModel
from .query import (
    build_graph,
    date_range_is_invalid,
    evidence_hits,
    filter_relations,
    is_supported_symbol,
    paginate,
)


def load_snapshot() -> SnapshotModel:
    path = snapshot_path()
    if not path.exists():
        print(json.dumps({
            "error_code": "DATA_MISSING",
            "message": f"Snapshot not found at {path}.",
        }))
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return SnapshotModel(**json.load(f))


def bounded_int(name: str, low: int, high: int):
    def parser(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
        if number < low or number > high:
            raise argparse.ArgumentTypeError(f"{name} must be between {low} and {high}")
        return number
    return parser


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("dates must be YYYY-MM-DD") from exc


def parse_fact_status(value: str) -> FactStatus:
    try:
        return FactStatus(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "fact-status must be Confirmed Fact, Reasonable Inference, or Unknown"
        ) from exc


def parse_rel_type(value: str) -> RelationType:
    try:
        return RelationType(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "type must be supplier, customer, partner, investor_or_investee, or peer"
        ) from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="NVIDIA supply-chain snapshot CLI")
    parser.add_argument("--symbol", required=True, help="Research target ticker, e.g. NVDA")
    parser.add_argument(
        "--type",
        dest="rel_type",
        type=parse_rel_type,
        help="Relationship type (investee is accepted as investor_or_investee)",
    )
    parser.add_argument("--min-score", type=bounded_int("min-score", 0, 100), default=0)
    parser.add_argument("--min-relevance", type=bounded_int("min-relevance", 0, 100), default=0)
    parser.add_argument("--fact-status", type=parse_fact_status, default=None)
    parser.add_argument("--published-on-or-after", type=iso_date, default=None)
    parser.add_argument("--published-on-or-before", type=iso_date, default=None)
    parser.add_argument("--page", type=bounded_int("page", 1, 100000), default=1)
    parser.add_argument("--limit", type=bounded_int("limit", 1, 50), default=50)
    parser.add_argument(
        "--mode",
        choices=["relations", "graph", "evidence"],
        default="relations",
    )
    parser.add_argument("--target-ticker", help="Evidence filter, e.g. NYSE: TSM")
    args = parser.parse_args(argv)

    if not is_supported_symbol(args.symbol):
        print(json.dumps({
            "error_code": "ENTITY_NOT_SUPPORTED",
            "message": f"Symbol {args.symbol} is unsupported.",
            "suggested_actions": ["Try using NVDA."],
        }, indent=2))
        return 1

    if date_range_is_invalid(args.published_on_or_after, args.published_on_or_before):
        print(json.dumps({
            "error_code": "DATE_RANGE_INVALID",
            "message": "published_on_or_after must be on or before published_on_or_before.",
        }, indent=2))
        return 1

    snapshot = load_snapshot()
    results = filter_relations(
        snapshot.relations,
        rel_type=args.rel_type,
        fact_status=args.fact_status,
        min_score=args.min_score,
        min_relevance=args.min_relevance,
        published_on_or_after=args.published_on_or_after,
        published_on_or_before=args.published_on_or_before,
    )

    if args.mode == "graph":
        payload = build_graph(snapshot, results).model_dump(mode="json")
    elif args.mode == "evidence":
        hits = evidence_hits(results, target_ticker=args.target_ticker)
        if args.target_ticker and not hits:
            print(json.dumps({
                "error_code": "EVIDENCE_NOT_FOUND",
                "message": f"No evidence for target_ticker '{args.target_ticker}'.",
            }, indent=2))
            return 1
        payload = {"total": len(hits), "data": [h.model_dump(mode="json") for h in hits]}
    else:
        page = paginate(results, args.page, args.limit)
        payload = {
            "query_info": {
                "symbol": args.symbol,
                "filters": {
                    "type": args.rel_type.value if args.rel_type else None,
                    "fact_status": args.fact_status.value if args.fact_status else None,
                    "min_score": args.min_score,
                    "min_relevance": args.min_relevance,
                    "published_on_or_after": (
                        args.published_on_or_after.isoformat()
                        if args.published_on_or_after else None
                    ),
                    "published_on_or_before": (
                        args.published_on_or_before.isoformat()
                        if args.published_on_or_before else None
                    ),
                },
                "total": len(results),
                "page": args.page,
                "limit": args.limit,
                "count": len(page),
            },
            "data": [rel.model_dump(mode="json") for rel in page],
        }

    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
