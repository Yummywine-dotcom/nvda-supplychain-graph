from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

from .scoring import WEIGHTS, total_score


class RelationType(str, Enum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    PARTNER = "partner"
    INVESTOR_OR_INVESTEE = "investor_or_investee"
    PEER = "peer"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str) and value.lower() in {"investee", "investor"}:
            return cls.INVESTOR_OR_INVESTEE
        return None


class FactStatus(str, Enum):
    CONFIRMED_FACT = "Confirmed Fact"
    REASONABLE_INFERENCE = "Reasonable Inference"
    UNKNOWN = "Unknown"

    @classmethod
    def _missing_(cls, value):
        if not isinstance(value, str):
            return None
        aliases = {
            "fact": cls.CONFIRMED_FACT,
            "confirmed": cls.CONFIRMED_FACT,
            "confirmed_fact": cls.CONFIRMED_FACT,
            "inference": cls.REASONABLE_INFERENCE,
            "reasonable_inference": cls.REASONABLE_INFERENCE,
            "unknown": cls.UNKNOWN,
        }
        return aliases.get(value.lower().replace(" ", "_"))


class ScoreComponents(BaseModel):
    source_authority: int = Field(ge=0, le=WEIGHTS["source_authority"])
    independence_directness: int = Field(ge=0, le=WEIGHTS["independence_directness"])
    timeliness: int = Field(ge=0, le=WEIGHTS["timeliness"])
    quantifiable_info: int = Field(ge=0, le=WEIGHTS["quantifiable_info"])


class EvidenceModel(BaseModel):
    source_url: HttpUrl
    publisher: str
    publish_date: str
    access_time: datetime
    evidence_locator: str


class RelationModel(BaseModel):
    relation_id: str = Field(min_length=1, description="Stable row id, unique in the snapshot")
    target_entity: str
    target_ticker: str
    relation_type: RelationType
    direction: str
    fact_status: FactStatus
    quantifiable_info: str
    confidence_score: int = Field(ge=0, le=100)
    score_components: ScoreComponents
    score_explanation: str
    relevance_score: int = Field(ge=0, le=100)
    evidence: EvidenceModel
    as_of_date: Optional[date] = None
    entity_disambiguation: Optional[str] = None
    uncertainty_notes: Optional[str] = None
    source_conflict_notes: Optional[str] = None

    @model_validator(mode="after")
    def confidence_matches_components(self):
        computed = total_score(self.score_components.model_dump())
        if computed != self.confidence_score:
            raise ValueError(
                f"confidence_score {self.confidence_score} != component sum {computed}"
            )
        return self


class MetadataModel(BaseModel):
    base_entity: str
    ticker: str
    cut_off_date: date
    version: str
    description: Optional[str] = None
    scope: Optional[str] = None
    boundaries: Optional[str] = None
    disclaimer: Optional[str] = None
    unknowns: Optional[List[str]] = None
    scoring_method: Optional[str] = None


class SnapshotModel(BaseModel):
    metadata: MetadataModel
    relations: List[RelationModel]

    @model_validator(mode="after")
    def unique_relation_ids(self):
        ids = [rel.relation_id for rel in self.relations]
        dupes = {item for item in ids if ids.count(item) > 1}
        if dupes:
            raise ValueError(f"Duplicate relation_id values: {sorted(dupes)}")
        return self


class PaginatedResponse(BaseModel):
    total: int
    page: int
    limit: int
    data: List[RelationModel]


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    suggested_actions: Optional[List[str]] = None
    details: Optional[list] = None


class GraphNode(BaseModel):
    id: str
    label: str
    ticker: str
    role: str


class GraphEdge(BaseModel):
    relation_id: str
    source: str
    target: str
    relation_type: RelationType
    direction: str
    confidence_score: int
    fact_status: FactStatus
    relevance_score: int


class GraphResponse(BaseModel):
    base_entity: str
    ticker: str
    cut_off_date: date
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class EvidenceHit(BaseModel):
    relation_id: str
    target_entity: str
    target_ticker: str
    relation_type: RelationType
    fact_status: FactStatus
    evidence: EvidenceModel


class EvidenceResponse(BaseModel):
    total: int
    data: List[EvidenceHit]


