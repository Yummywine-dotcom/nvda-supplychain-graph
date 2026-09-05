import json

from src.cli import main


def test_cli_happy_path_supplier(capsys):
    code = main(["--symbol", "NVDA", "--type", "supplier", "--min-score", "90", "--limit", "5"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_info"]["total"] >= 1
    for row in payload["data"]:
        assert row["relation_type"] == "supplier"
        assert row["confidence_score"] >= 90


def test_cli_investee_alias(capsys):
    code = main(["--symbol", "NVDA", "--type", "investee"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    tickers = {row["target_ticker"] for row in payload["data"]}
    assert "NASDAQ: INTC" in tickers
    assert "NASDAQ: CRWV" in tickers
    assert "NASDAQ: SPCX" in tickers
    assert "NASDAQ: GENB" in tickers
    assert "NYSE: COHR" in tickers
    for row in payload["data"]:
        assert row["relation_type"] == "investor_or_investee"


def test_cli_unsupported_symbol(capsys):
    code = main(["--symbol", "TSLA"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "ENTITY_NOT_SUPPORTED"


def test_cli_graph_mode(capsys):
    code = main(["--symbol", "NVDA", "--mode", "graph", "--type", "peer"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ticker"] == "NASDAQ: NVDA"
    assert any(node["id"] == "NVDA" for node in payload["nodes"])
    assert payload["edges"]
    assert "relation_id" in payload["edges"][0]


def test_cli_date_range_invalid(capsys):
    code = main([
        "--symbol", "NVDA",
        "--published-on-or-after", "2024-03-01",
        "--published-on-or-before", "2024-01-01",
    ])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "DATE_RANGE_INVALID"
