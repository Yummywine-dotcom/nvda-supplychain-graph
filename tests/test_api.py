def test_get_metadata(client):
    response = client.get("/v1/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NASDAQ: NVDA"
    assert data["cut_off_date"] == "2026-09-05"
    assert "disclaimer" in data
    assert "scope" in data


def test_get_relations_happy_path(client):
    response = client.get("/v1/companies/NVDA/relations?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 2
    assert data["total"] >= 5
    assert len(data["data"]) == 2
    first_item = data["data"][0]
    assert "confidence_score" in first_item
    assert "score_explanation" in first_item
    assert "score_components" in first_item
    assert "evidence" in first_item
    assert "relevance_score" in first_item


def test_get_relations_with_filters(client):
    response = client.get(
        "/v1/companies/NVDA/relations?rel_type=supplier&min_score=95"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["data"]:
        assert item["relation_type"] == "supplier"
        assert item["confidence_score"] >= 95


def test_time_and_relevance_filters(client):
    response = client.get(
        "/v1/companies/NVDA/relations"
        "?published_on_or_after=2026-01-01&published_on_or_before=2026-09-05&min_relevance=80"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["data"]:
        assert item["evidence"]["publish_date"] >= "2026-01-01"
        assert item["relevance_score"] >= 80


def test_pagination_empty_page(client):
    response = client.get("/v1/companies/NVDA/relations?page=99&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert data["data"] == []


def test_invalid_entity_404(client):
    response = client.get("/v1/companies/TSLA/relations")
    assert response.status_code == 404
    error_data = response.json()
    assert error_data["error_code"] == "ENTITY_NOT_SUPPORTED"
    assert "suggested_actions" in error_data


def test_invalid_relation_type_422(client):
    response = client.get("/v1/companies/NVDA/relations?rel_type=competitor")
    assert response.status_code == 422
    error_data = response.json()
    assert error_data["error_code"] == "VALIDATION_ERROR"
    assert error_data["details"][0]["type"] == "enum"


def test_graph_endpoint(client):
    response = client.get("/v1/companies/NVDA/graph?rel_type=investor_or_investee")
    assert response.status_code == 200
    data = response.json()
    ids = {node["id"] for node in data["nodes"]}
    assert "NVDA" in ids
    assert "INTC" in ids
    assert "SPCX" in ids
    assert data["edges"][0]["relation_type"] == "investor_or_investee"


def test_evidence_endpoint(client):
    response = client.get("/v1/companies/NVDA/evidence?target_ticker=NYSE:%20TSM")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for hit in data["data"]:
        assert hit["target_ticker"] == "NYSE: TSM"
        assert "source_url" in hit["evidence"]


def test_health_and_root(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["relation_count"] >= 11
    root = client.get("/")
    assert root.status_code == 200
    assert "/docs" in root.json()["docs"]


def test_fact_status_filter(client):
    response = client.get("/v1/companies/NVDA/relations?fact_status=Unknown")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["data"]:
        assert item["fact_status"] == "Unknown"


def test_inverted_date_range_400(client):
    response = client.get(
        "/v1/companies/NVDA/relations"
        "?published_on_or_after=2024-03-01&published_on_or_before=2024-01-01"
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "DATE_RANGE_INVALID"


def test_evidence_missing_target(client):
    response = client.get("/v1/companies/NVDA/evidence?target_ticker=NASDAQ:%20FAKE")
    assert response.status_code == 404
    assert response.json()["error_code"] == "EVIDENCE_NOT_FOUND"
