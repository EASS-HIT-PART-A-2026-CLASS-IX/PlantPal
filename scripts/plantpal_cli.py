"""PlantPal Typer CLI.

Satisfies the EX2 "Typer CLI" option (with the Streamlit dashboard as
the primary interface) and provides the EX3 CSV export/import
enhancement.

Commands:
    list-plants        Show plants in a table.
    add-plant          Create a plant.
    export-csv         Dump all plants to a CSV file.
    import-csv         Create plants from a CSV file.
    advice             Fetch AI advice for one plant.
    login              Authenticate and print a JWT.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import typer

cli = typer.Typer(help="PlantPal command-line interface")

DEFAULT_URL = os.getenv("API_URL", "http://localhost:8000")


def _client(api_url: str, token: Optional[str] = None) -> httpx.Client:
    headers = {"X-Trace-Id": "plantpal-cli"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=api_url, headers=headers, timeout=10.0)


@cli.command("list-plants")
def list_plants(
    api_url: str = typer.Option(DEFAULT_URL, "--api-url"),
    limit: int = typer.Option(100, "--limit"),
) -> None:
    """List all plants in the backend."""
    with _client(api_url) as client:
        resp = client.get("/plants/", params={"limit": limit})
        resp.raise_for_status()
        plants = resp.json()
    if not plants:
        typer.echo("No plants yet — add one with `add-plant`.")
        return
    typer.echo(f"{'ID':<4} {'Name':<24} {'Species':<24} {'Health':<18} {'Location':<16}")
    typer.echo("-" * 90)
    for p in plants:
        typer.echo(
            f"{p['id']:<4} {p['name'][:23]:<24} {p['species'][:23]:<24} "
            f"{p['health_status']:<18} {p['location'][:15]:<16}"
        )


@cli.command("add-plant")
def add_plant(
    name: str = typer.Option(..., "--name", prompt=True),
    species: str = typer.Option(..., "--species", prompt=True),
    location: str = typer.Option("Living Room", "--location"),
    light_need: str = typer.Option("medium", "--light"),
    frequency_hours: int = typer.Option(168, "--frequency"),
    notes: str = typer.Option("", "--notes"),
    token: Optional[str] = typer.Option(None, "--token", envvar="PLANTPAL_TOKEN"),
    api_url: str = typer.Option(DEFAULT_URL, "--api-url"),
) -> None:
    """Create a new plant.  Requires an editor-role JWT."""
    payload = {
        "name": name,
        "species": species,
        "location": location,
        "light_need": light_need,
        "water_frequency_hours": frequency_hours,
        "notes": notes,
    }
    with _client(api_url, token=token) as client:
        resp = client.post("/plants/", json=payload)
        if resp.status_code == 401:
            typer.echo("Authentication required: pass --token or set PLANTPAL_TOKEN.", err=True)
            raise typer.Exit(code=1)
        resp.raise_for_status()
        data = resp.json()
    typer.echo(f"Created plant id={data['id']} name={data['name']}")


@cli.command("export-csv")
def export_csv(
    output: Path = typer.Option(Path("plants_export.csv"), "--output"),
    api_url: str = typer.Option(DEFAULT_URL, "--api-url"),
) -> None:
    """Export the plant catalog to a CSV file (EX3 enhancement)."""
    with _client(api_url) as client:
        resp = client.get("/plants/", params={"limit": 1000})
        resp.raise_for_status()
        plants = resp.json()

    columns = [
        "id",
        "name",
        "species",
        "location",
        "light_need",
        "water_frequency_hours",
        "last_watered",
        "health_status",
        "notes",
    ]
    with output.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()
        for p in plants:
            writer.writerow({c: p.get(c, "") for c in columns})
    typer.echo(f"Exported {len(plants)} plants to {output}")


@cli.command("import-csv")
def import_csv(
    input_file: Path = typer.Argument(..., exists=True, readable=True),
    token: Optional[str] = typer.Option(None, "--token", envvar="PLANTPAL_TOKEN"),
    api_url: str = typer.Option(DEFAULT_URL, "--api-url"),
) -> None:
    """Import plants from a CSV file (EX3 enhancement).  Requires editor token."""
    created = 0
    errors = 0
    with _client(api_url, token=token) as client, input_file.open(encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            payload = {
                "name": row.get("name", "").strip(),
                "species": row.get("species", "").strip(),
                "location": row.get("location", "Unknown").strip() or "Unknown",
                "light_need": row.get("light_need", "medium").strip() or "medium",
                "water_frequency_hours": int(row.get("water_frequency_hours") or 168),
                "notes": row.get("notes", ""),
            }
            if not payload["name"] or not payload["species"]:
                errors += 1
                continue
            resp = client.post("/plants/", json=payload)
            if resp.status_code == 401:
                typer.echo("Authentication required: pass --token.", err=True)
                raise typer.Exit(code=1)
            if resp.is_success:
                created += 1
            else:
                errors += 1
    typer.echo(f"Imported {created} plants ({errors} errors) from {input_file}")


@cli.command("advice")
def advice(
    plant_id: int = typer.Argument(...),
    api_url: str = typer.Option(DEFAULT_URL, "--api-url"),
) -> None:
    """Fetch AI-generated care advice for a plant."""
    with _client(api_url) as client:
        resp = client.get(f"/plants/{plant_id}/advice")
        resp.raise_for_status()
        data = resp.json()
    typer.echo(data["summary"])
    for tip in data["tips"]:
        typer.echo(f"  - {tip}")
    typer.echo(f"(source: {data.get('source')})")


@cli.command("login")
def login(
    username: str = typer.Option(..., "--username", prompt=True),
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True),
    api_url: str = typer.Option(DEFAULT_URL, "--api-url"),
) -> None:
    """Authenticate against /token and print the JWT."""
    with _client(api_url) as client:
        resp = client.post(
            "/token",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            typer.echo(f"Login failed: {resp.status_code} {resp.text}", err=True)
            raise typer.Exit(code=1)
    typer.echo(resp.json()["access_token"])


if __name__ == "__main__":
    cli()
