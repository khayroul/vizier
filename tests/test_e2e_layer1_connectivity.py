"""Layer 1 — Service Connectivity smoke tests.

Verify each external dependency is reachable and functional.
These are the cheapest, most impactful tests: if a service is down,
nothing above Layer 1 matters.

Markers:
  - requires_db: Postgres, MinIO (infrastructure services)
  - requires_api: OpenAI, fal.ai (paid external APIs)
  - (no marker): local tools — Typst binary, spans.db SQLite
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Layer 1a — Postgres connectivity + core schema
# ---------------------------------------------------------------------------


@pytest.mark.requires_db
class TestPostgresConnectivity:
    """Postgres is reachable and has the required core tables."""

    def test_connect_and_query(self) -> None:
        """Can open a connection and run a trivial query."""
        import psycopg2

        url = os.environ.get("DATABASE_URL", "postgres://localhost:5432/vizier")
        conn = psycopg2.connect(url, connect_timeout=5)
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)
        finally:
            conn.close()

    @pytest.mark.parametrize(
        "table",
        ["clients", "jobs", "artifacts", "feedback"],
    )
    def test_core_table_exists(self, table: str) -> None:
        """Core tables exist in the public schema."""
        import psycopg2

        url = os.environ.get("DATABASE_URL", "postgres://localhost:5432/vizier")
        conn = psycopg2.connect(url, connect_timeout=5)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'public' AND table_name = %s"
                ")",
                (table,),
            )
            exists = cur.fetchone()
            assert exists and exists[0], f"Table '{table}' not found in public schema"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Layer 1b — OpenAI chat completion
# ---------------------------------------------------------------------------


@pytest.mark.requires_api
class TestOpenAICompletion:
    """OpenAI API returns a valid chat completion."""

    def test_single_completion(self) -> None:
        """GPT-5.4-mini returns a non-empty response."""
        import httpx

        api_key = os.environ.get("OPENAI_API_KEY", "")
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "Reply with 'ok'"}],
                "max_completion_tokens": 8,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        assert content and len(content) > 0


# ---------------------------------------------------------------------------
# Layer 1c — OpenAI embeddings
# ---------------------------------------------------------------------------


@pytest.mark.requires_api
class TestOpenAIEmbeddings:
    """OpenAI embeddings endpoint returns the correct dimension vector."""

    def test_embed_returns_1536_dim(self) -> None:
        """text-embedding-3-small returns a 1536-dimension vector."""
        import httpx

        api_key = os.environ.get("OPENAI_API_KEY", "")
        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            json={"model": "text-embedding-3-small", "input": "hello world"},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        assert len(embedding) == 1536
        assert all(isinstance(v, float) for v in embedding)


# ---------------------------------------------------------------------------
# Layer 1d — MinIO storage
# ---------------------------------------------------------------------------


def _minio_available() -> bool:
    """Check if MinIO client is installed and server is reachable."""
    try:
        import minio  # noqa: F401
    except ImportError:
        return False
    import socket
    try:
        sock = socket.create_connection(("localhost", 9000), timeout=2)
        sock.close()
        return True
    except (OSError, ConnectionRefusedError):
        return False


@pytest.mark.requires_db
@pytest.mark.integration
@pytest.mark.skipif(not _minio_available(), reason="MinIO client not installed or server not reachable")
class TestMinIOConnectivity:
    """MinIO is reachable: upload + download round-trip."""

    def test_upload_download_roundtrip(self) -> None:
        """Upload 1-byte file, download it, verify contents, clean up."""
        from utils.storage import (
            BUCKET_NAME,
            delete_object,
            download_bytes,
            ensure_bucket,
            get_minio_client,
            upload_bytes,
        )

        client = get_minio_client()
        ensure_bucket(client)

        test_key = f"_e2e_test/{uuid.uuid4().hex}.bin"
        payload = b"\x42"

        try:
            path = upload_bytes(test_key, payload, client=client)
            assert path == f"{BUCKET_NAME}/{test_key}"

            downloaded = download_bytes(test_key, client=client)
            assert downloaded == payload
        finally:
            # Clean up test artifact
            try:
                delete_object(test_key, client=client)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Layer 1e — fal.ai image generation
# ---------------------------------------------------------------------------


@pytest.mark.requires_api
class TestFalAIConnectivity:
    """fal.ai returns an image URL for a minimal generation request."""

    def test_tiny_image_generation(self) -> None:
        """Submit a minimal image generation and verify URL returned."""
        import fal_client  # type: ignore[import-untyped]

        result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": "solid blue square",
                "image_size": {"width": 256, "height": 256},
                "num_inference_steps": 2,
            },
        )
        images = result.get("images", [])
        assert len(images) >= 1
        assert images[0].get("url", "").startswith("https://")


# ---------------------------------------------------------------------------
# Layer 1f — Typst PDF rendering
# ---------------------------------------------------------------------------


class TestTypstRendering:
    """Typst binary can compile a minimal .typ file to PDF bytes."""

    def test_minimal_typst_to_pdf(self, tmp_path: Path) -> None:
        """Compile a trivial Typst document and verify PDF header."""
        typ_file = tmp_path / "test.typ"
        typ_file.write_text('#set page(width: 100pt, height: 100pt)\nHello')
        pdf_file = tmp_path / "test.pdf"

        result = subprocess.run(
            ["typst", "compile", str(typ_file), str(pdf_file)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"typst compile failed: {result.stderr}"
        pdf_bytes = pdf_file.read_bytes()
        assert pdf_bytes[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Layer 1g — spans.db SQLite write + read
# ---------------------------------------------------------------------------


class TestSpansDB:
    """Local spans.db: init, write, read cycle."""

    def test_write_and_read_span(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Write a span row and read it back from a temp SQLite DB."""
        import utils.spans as spans_mod

        test_db = tmp_path / "test_spans.db"
        monkeypatch.setattr(spans_mod, "DB_PATH", test_db)

        spans_mod.init_db(test_db)

        step_id = str(uuid.uuid4())
        spans_mod.record_span(
            step_id=step_id,
            model="gpt-5.4-mini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            duration_ms=123.4,
            job_id="test-job-001",
            step_type="test",
        )

        conn = sqlite3.connect(str(test_db))
        try:
            row = conn.execute(
                "SELECT model, input_tokens, output_tokens FROM spans WHERE step_id = ?",
                (step_id,),
            ).fetchone()
            assert row is not None
            assert row[0] == "gpt-5.4-mini"
            assert row[1] == 100
            assert row[2] == 50
        finally:
            conn.close()
