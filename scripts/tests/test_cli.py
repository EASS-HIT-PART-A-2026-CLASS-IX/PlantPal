"""CliRunner tests for the PlantPal Typer CLI (EX2 bonus + EX3 enhancement)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from plantpal_cli import cli

runner = CliRunner()


def _mock_client(get_json=None, post_json=None, post_status=201):
    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json = MagicMock(return_value=get_json or [])
    get_resp.status_code = 200

    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json = MagicMock(return_value=post_json or {})
    post_resp.status_code = post_status
    post_resp.is_success = 200 <= post_status < 300

    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get = MagicMock(return_value=get_resp)
    client.post = MagicMock(return_value=post_resp)
    return client


def test_list_plants_empty():
    client = _mock_client(get_json=[])
    with patch("plantpal_cli.httpx.Client", return_value=client):
        result = runner.invoke(cli, ["list-plants"])
    assert result.exit_code == 0
    assert "No plants yet" in result.stdout


def test_list_plants_populated():
    plants = [
        {
            "id": 1,
            "name": "Monstera",
            "species": "Monstera deliciosa",
            "health_status": "healthy",
            "location": "Living Room",
        }
    ]
    client = _mock_client(get_json=plants)
    with patch("plantpal_cli.httpx.Client", return_value=client):
        result = runner.invoke(cli, ["list-plants"])
    assert result.exit_code == 0
    assert "Monstera" in result.stdout


def test_export_csv(tmp_path: Path):
    plants = [
        {
            "id": 1,
            "name": "Basil",
            "species": "Ocimum basilicum",
            "location": "Kitchen",
            "light_need": "high",
            "water_frequency_hours": 48,
            "last_watered": "2026-04-20T10:00:00",
            "health_status": "healthy",
            "notes": "",
        }
    ]
    client = _mock_client(get_json=plants)
    out = tmp_path / "out.csv"
    with patch("plantpal_cli.httpx.Client", return_value=client):
        result = runner.invoke(cli, ["export-csv", "--output", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    content = out.read_text()
    assert "Basil" in content
    assert "name,species" in content


def test_import_csv_creates_plants(tmp_path: Path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text(
        "name,species,location,light_need,water_frequency_hours,notes\n"
        "Pothos,Epipremnum,Office,medium,120,\n"
        "Aloe,Aloe vera,Bedroom,high,240,\n"
    )
    client = _mock_client(post_json={"id": 1}, post_status=200)
    with patch("plantpal_cli.httpx.Client", return_value=client):
        result = runner.invoke(
            cli, ["import-csv", str(csv_path), "--token", "faketoken"]
        )
    assert result.exit_code == 0
    assert "Imported 2 plants" in result.stdout
    assert client.post.call_count == 2


def test_advice_command():
    advice_payload = {
        "plant_id": 1,
        "plant_name": "Basil",
        "summary": "Care tips for Basil.",
        "tips": ["Water weekly", "Bright light"],
        "source": "rule-based",
    }
    client = _mock_client(get_json=advice_payload)
    with patch("plantpal_cli.httpx.Client", return_value=client):
        result = runner.invoke(cli, ["advice", "1"])
    assert result.exit_code == 0
    assert "Basil" in result.stdout
    assert "Water weekly" in result.stdout
