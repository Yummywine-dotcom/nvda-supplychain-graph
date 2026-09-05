import json
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import snapshot_path
from .models import (
    EvidenceResponse,
    FactStatus,
    GraphResponse,
    PaginatedResponse,
    RelationType,
    SnapshotModel,
)
from .query import (
    build_graph,
    date_range_is_invalid,
    evidence_hits,
    filter_relations,
    is_supported_symbol,
    paginate,
)

snapshot_data: Optional[SnapshotModel] = None


def load_snapshot() -> SnapshotModel:
    path = snapshot_path()
    if not path.exists():
        raise FileNotFoundError(f"Snapshot not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return SnapshotModel(**json.load(f))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global snapshot_data
    snapshot_data = load_snapshot()
    yield


app = FastAPI(
    title="NVIDIA Supply Chain API",
    description="ARTi Challenge - Supply Chain & Partnership Relation Data API",
    version="1.5.0",
    lifespan=lifespan,
)


def require_snapshot() -> SnapshotModel:
    if snapshot_data is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "SNAPSHOT_NOT_LOADED",
                "message": "Snapshot is not loaded.",
                "suggested_actions": ["Restart the API process."],
            },
        )
    return snapshot_data


def require_symbol(symbol: str) -> None:
    if not is_supported_symbol(symbol):
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ENTITY_NOT_SUPPORTED",
                "message": f"Entity '{symbol}' is not found in the current snapshot.",
                "suggested_actions": ["Try using 'NVDA' as the symbol."],
            },
        )


def require_date_range(after: Optional[date], before: Optional[date]) -> None:
    if date_range_is_invalid(after, before):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "DATE_RANGE_INVALID",
                "message": "published_on_or_after must be on or before published_on_or_before.",
                "suggested_actions": ["Swap the dates or omit one bound."],
            },
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {
            "error_code": "HTTP_ERROR",
            "message": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request failed input validation.",
            "suggested_actions": [
                "Use rel_type in supplier, customer, partner, investor_or_investee, peer.",
                "Use fact_status Confirmed Fact, Reasonable Inference, or Unknown.",
                "Keep min_score, min_relevance, page, and limit within documented ranges.",
            ],
            "details": exc.errors(),
        },
    )


@app.get("/")
def root():
    return {
        "service": "NVIDIA supply-chain research API",
        "research_target": "NASDAQ: NVDA",
        "docs": "/docs",
        "health": "/health",
        "relations": "/v1/companies/NVDA/relations",
        "graph": "/v1/companies/NVDA/graph",
        "evidence": "/v1/companies/NVDA/evidence",
    }


@app.get("/health")
def health():
    snapshot = require_snapshot()
    return {
        "status": "ok",
        "ticker": snapshot.metadata.ticker,
        "cut_off_date": snapshot.metadata.cut_off_date,
        "version": snapshot.metadata.version,
        "relation_count": len(snapshot.relations),
    }


@app.get("/v1/metadata")
def get_metadata():
    return require_snapshot().metadata


def _filtered(
    symbol: str,
    rel_type: Optional[RelationType],
    fact_status: Optional[FactStatus],
    min_score: int,
    min_relevance: int,
    published_on_or_after: Optional[date],
    published_on_or_before: Optional[date],
):
    require_symbol(symbol)
    require_date_range(published_on_or_after, published_on_or_before)
    snapshot = require_snapshot()
    return snapshot, filter_relations(
        snapshot.relations,
        rel_type=rel_type,
        fact_status=fact_status,
        min_score=min_score,
        min_relevance=min_relevance,
        published_on_or_after=published_on_or_after,
        published_on_or_before=published_on_or_before,
    )


@app.get("/v1/companies/{symbol}/relations", response_model=PaginatedResponse)
def get_relations(
    symbol: str,
    rel_type: Optional[RelationType] = Query(None),
    fact_status: Optional[FactStatus] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    min_relevance: int = Query(0, ge=0, le=100),
    published_on_or_after: Optional[date] = Query(None),
    published_on_or_before: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    _, results = _filtered(
        symbol,
        rel_type,
        fact_status,
        min_score,
        min_relevance,
        published_on_or_after,
        published_on_or_before,
    )
    return {
        "total": len(results),
        "page": page,
        "limit": limit,
        "data": paginate(results, page, limit),
    }


@app.get("/v1/companies/{symbol}/graph", response_model=GraphResponse)
def get_graph(
    symbol: str,
    rel_type: Optional[RelationType] = Query(None),
    fact_status: Optional[FactStatus] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    min_relevance: int = Query(0, ge=0, le=100),
    published_on_or_after: Optional[date] = Query(None),
    published_on_or_before: Optional[date] = Query(None),
):
    snapshot, results = _filtered(
        symbol,
        rel_type,
        fact_status,
        min_score,
        min_relevance,
        published_on_or_after,
        published_on_or_before,
    )
    return build_graph(snapshot, results)


@app.get("/v1/companies/{symbol}/evidence", response_model=EvidenceResponse)
def get_evidence(
    symbol: str,
    target_ticker: Optional[str] = Query(None, description="Ticker such as NYSE: TSM"),
    rel_type: Optional[RelationType] = Query(None),
    fact_status: Optional[FactStatus] = Query(None),
):
    snapshot, results = _filtered(
        symbol,
        rel_type,
        fact_status,
        0,
        0,
        None,
        None,
    )
    hits = evidence_hits(results, target_ticker=target_ticker)
    if target_ticker and not hits:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "EVIDENCE_NOT_FOUND",
                "message": f"No evidence for target_ticker '{target_ticker}'.",
                "suggested_actions": ["Omit target_ticker or use a ticker from /relations."],
            },
        )
    return {"total": len(hits), "data": hits}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)
