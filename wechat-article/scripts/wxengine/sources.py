"""Per-run source ledger for factual traceability."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .runs import load_run, resolve_run_id, run_dir

SOURCE_STATUSES = {"verified", "unverified", "user_provided"}


def source_path(run_id: str | None = None) -> Path:
    return run_dir(resolve_run_id(run_id)) / "sources.yaml"


def load_sources(run_id: str | None = None) -> dict:
    resolved = resolve_run_id(run_id)
    path = source_path(resolved)
    if not path.exists():
        return {"version": 1, "run_id": resolved, "sources": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources", []) if isinstance(data, dict) else []
    return {"version": 1, "run_id": resolved, "sources": sources if isinstance(sources, list) else []}


def save_sources(data: dict, run_id: str | None = None) -> Path:
    resolved = resolve_run_id(run_id)
    path = source_path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "run_id": resolved, "sources": data.get("sources", [])}
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix="sources", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def add_source(
    *,
    url: str,
    title: str,
    claim: str,
    publisher: str = "",
    published_at: str = "",
    status: str = "verified",
    run_id: str | None = None,
) -> dict:
    if status not in SOURCE_STATUSES:
        raise ValueError(f"Unknown source status: {status}")
    if status == "user_provided" and not url:
        url = "user-provided://material"
    parsed = urlparse(url)
    if status != "user_provided" and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
        raise ValueError("Verified and unverified sources require an http(s) URL")
    if status == "user_provided" and not parsed.scheme:
        raise ValueError("User-provided sources need a URL or an empty URL")
    if not title.strip() or not claim.strip():
        raise ValueError("Source title and claim are required")

    resolved = resolve_run_id(run_id)
    state = load_run(resolved)  # ensure the run exists
    if state.get("status") == "completed":
        raise ValueError("Completed runs are immutable; sources cannot be changed")
    data = load_sources(resolved)
    source_id = hashlib.sha256(f"{url}\n{claim}".encode("utf-8")).hexdigest()[:12]
    entry = {
        "id": source_id,
        "title": title.strip(),
        "publisher": publisher.strip(),
        "url": url,
        "published_at": published_at.strip() or None,
        "accessed_at": date.today().isoformat(),
        "claim": claim.strip(),
        "status": status,
    }
    existing = {item.get("id"): i for i, item in enumerate(data["sources"])}
    if source_id in existing:
        data["sources"][existing[source_id]] = entry
    else:
        data["sources"].append(entry)
    save_sources(data, resolved)
    return entry
