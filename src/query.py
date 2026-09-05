from datetime import date
from typing import List, Optional, Tuple

from .models import (
    EvidenceHit,
    FactStatus,
    GraphEdge,
    GraphNode,
    GraphResponse,
    RelationModel,
    RelationType,
    SnapshotModel,
)

SUPPORTED_SYMBOLS = {"NVDA", "NASDAQ:NVDA"}


def is_supported_symbol(symbol: str) -> bool:
    return symbol.upper().replace(" ", "") in SUPPORTED_SYMBOLS


def parse_publish_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def date_range_is_invalid(after: Optional[date], before: Optional[date]) -> bool:
    return after is not None and before is not None and after > before


def sort_relations(relations: List[RelationModel]) -> List[RelationModel]:
    return sorted(
        relations,
        key=lambda rel: (-rel.relevance_score, -rel.confidence_score, rel.relation_id),
    )


def filter_relations(
    relations: List[RelationModel],
    rel_type: Optional[RelationType] = None,
    fact_status: Optional[FactStatus] = None,
    min_score: int = 0,
    min_relevance: int = 0,
    published_on_or_after: Optional[date] = None,
    published_on_or_before: Optional[date] = None,
) -> List[RelationModel]:
    results = list(relations)
    if rel_type:
        results = [r for r in results if r.relation_type == rel_type]
    if fact_status:
        results = [r for r in results if r.fact_status == fact_status]
    results = [r for r in results if r.confidence_score >= min_score]
    results = [r for r in results if r.relevance_score >= min_relevance]
    if published_on_or_after:
        results = [
            r for r in results
            if parse_publish_date(r.evidence.publish_date) >= published_on_or_after
        ]
    if published_on_or_before:
        results = [
            r for r in results
            if parse_publish_date(r.evidence.publish_date) <= published_on_or_before
        ]
    return sort_relations(results)


def paginate(items: List[RelationModel], page: int, limit: int) -> List[RelationModel]:
    start_idx = (page - 1) * limit
    return items[start_idx:start_idx + limit]


def evidence_hits(
    relations: List[RelationModel],
    target_ticker: Optional[str] = None,
) -> List[EvidenceHit]:
    hits = []
    needle = target_ticker.upper().replace(" ", "") if target_ticker else None
    for rel in relations:
        if needle and rel.target_ticker.upper().replace(" ", "") != needle:
            continue
        hits.append(
            EvidenceHit(
                relation_id=rel.relation_id,
                target_entity=rel.target_entity,
                target_ticker=rel.target_ticker,
                relation_type=rel.relation_type,
                fact_status=rel.fact_status,
                evidence=rel.evidence,
            )
        )
    return hits


def _edge_endpoints(rel: RelationModel, base_id: str, other_id: str) -> Tuple[str, str]:
    if rel.relation_type == RelationType.SUPPLIER:
        return other_id, base_id
    if rel.relation_type in {RelationType.CUSTOMER, RelationType.INVESTOR_OR_INVESTEE}:
        return base_id, other_id
    return base_id, other_id


def _merge_role(existing: str, incoming: str) -> str:
    if existing == "research_target":
        return existing
    parts = [part for part in existing.split(",") if part]
    if incoming not in parts:
        parts.append(incoming)
    return ",".join(parts)


def build_graph(snapshot: SnapshotModel, relations: List[RelationModel]) -> GraphResponse:
    base_id = "NVDA"
    nodes = {
        base_id: GraphNode(
            id=base_id,
            label=snapshot.metadata.base_entity,
            ticker=snapshot.metadata.ticker,
            role="research_target",
        )
    }
    edges: List[GraphEdge] = []
    for rel in relations:
        other_id = rel.target_ticker.split(":")[-1].strip()
        if other_id in nodes:
            previous = nodes[other_id]
            nodes[other_id] = previous.model_copy(
                update={"role": _merge_role(previous.role, rel.relation_type.value)}
            )
        else:
            nodes[other_id] = GraphNode(
                id=other_id,
                label=rel.target_entity,
                ticker=rel.target_ticker,
                role=rel.relation_type.value,
            )
        source, target = _edge_endpoints(rel, base_id, other_id)
        edges.append(
            GraphEdge(
                relation_id=rel.relation_id,
                source=source,
                target=target,
                relation_type=rel.relation_type,
                direction=rel.direction,
                confidence_score=rel.confidence_score,
                fact_status=rel.fact_status,
                relevance_score=rel.relevance_score,
            )
        )
    return GraphResponse(
        base_entity=snapshot.metadata.base_entity,
        ticker=snapshot.metadata.ticker,
        cut_off_date=snapshot.metadata.cut_off_date,
        nodes=list(nodes.values()),
        edges=edges,
    )
