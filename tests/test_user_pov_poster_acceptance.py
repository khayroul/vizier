"""User-POV poster acceptance tests.

These tests exercise the real governed poster path:

    raw brief -> route -> readiness -> policy -> workflow execution -> PDF deliverable

The external model/image calls are replaced with deterministic local fixtures so
the suite can run in CI, but the governed orchestration, poster template, PDF
rendering, and delivery path are real.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PosixPath
from typing import Any

import pytest
import yaml
from PIL import Image, ImageDraw, ImageFilter
from pypdf import PdfReader

from tools.orchestrate import run_governed

SUITE_PATH = (
    Path(__file__).resolve().parent.parent
    / "evaluations"
    / "reference_corpus"
    / "poster_ui_suite.yaml"
)


@dataclass(frozen=True)
class PosterAcceptanceCase:
    """Frozen user-POV poster case loaded from the reference corpus."""

    case_id: str
    title: str
    prompt: str
    poster_inputs: dict[str, Any]
    mock_brief_response: dict[str, Any]
    required_prompt_terms: tuple[str, ...]
    preferred_templates: tuple[str, ...]
    discouraged_templates: tuple[str, ...]
    manual_focus: tuple[str, ...]

    @property
    def user_prompt(self) -> str:
        """Prompt fed into the governed poster flow.

        We intentionally include the word "poster" so the request routes
        through the real poster fast path instead of drifting into a different
        workflow.
        """
        return f"Create a poster. {self.prompt}"


@dataclass(frozen=True)
class PosterAcceptancePacket:
    """Structured review packet captured for each acceptance run."""

    case: PosterAcceptanceCase
    report_dir: Path
    pdf_path: Path
    image_path: Path
    pdf_text: str
    image_prompt: str
    weighted_score: float
    qa_score: float
    stage_statuses: dict[str, str]
    poster_copy: dict[str, str]
    manual_focus: tuple[str, ...]


def _load_cases() -> list[PosterAcceptanceCase]:
    raw = yaml.safe_load(SUITE_PATH.read_text(encoding="utf-8"))
    cases: list[PosterAcceptanceCase] = []
    for item in raw.get("prompts", []):
        cases.append(
            PosterAcceptanceCase(
                case_id=item["id"],
                title=item["title"],
                prompt=item["prompt"],
                poster_inputs=item["poster_inputs"],
                mock_brief_response=item["mock_brief_response"],
                required_prompt_terms=tuple(item.get("required_prompt_terms", [])),
                preferred_templates=tuple(item.get("preferred_templates", [])),
                discouraged_templates=tuple(item.get("discouraged_templates", [])),
                manual_focus=tuple(item.get("manual_focus", [])),
            )
        )
    return cases


POSTER_ACCEPTANCE_CASES = _load_cases()


def _mock_llm_response(content: str) -> dict[str, Any]:
    return {
        "content": content,
        "model": "gpt-5.4-mini",
        "input_tokens": 120,
        "output_tokens": 60,
        "cost_usd": 0.0002,
    }


def _brand_summary(case: PosterAcceptanceCase) -> str:
    palette = case.poster_inputs.get("palette", {})
    return ", ".join(f"{key}={value}" for key, value in palette.items())


def _build_expand_brief_payload(case: PosterAcceptanceCase) -> dict[str, str]:
    brief = case.mock_brief_response
    composition_parts = [
        brief.get("visual_direction", ""),
        brief.get("hero_focus", ""),
        "Required terms: " + ", ".join(case.required_prompt_terms),
        "Use strong negative space and readable CTA placement.",
    ]
    return {
        "composition": " ".join(part for part in composition_parts if part).strip(),
        "style": brief.get("campaign_angle", ""),
        "brand": _brand_summary(case),
        "technical": "1080x1350 social poster, high contrast, text-free background",
        "text_content": (
            f"{brief.get('headline', '')}\n"
            f"{brief.get('body', '')}\n"
            f"{brief.get('cta', '')}"
        ).strip(),
    }


def _build_poster_copy_payload(case: PosterAcceptanceCase) -> dict[str, str]:
    brief = case.mock_brief_response
    return {
        "headline": brief.get("headline", case.title),
        "subheadline": brief.get("campaign_angle", ""),
        "cta": brief.get("cta", "Learn More"),
        "body_text": brief.get("body", ""),
    }


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _hash_seed(text: str) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _blend(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    return tuple(int((1 - ratio) * x + ratio * y) for x, y in zip(a, b))


def _render_case_background(case: PosterAcceptanceCase) -> bytes:
    """Generate a deterministic text-free hero background for the case."""
    palette = case.poster_inputs.get("palette", {})
    primary = _hex_to_rgb(palette.get("primary", "#1A365D"))
    secondary = _hex_to_rgb(palette.get("secondary", "#E2E8F0"))
    accent = _hex_to_rgb(palette.get("accent", "#ED8936"))
    background = _hex_to_rgb(palette.get("background", "#0B1020"))

    width, height = 1400, 1800
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image, "RGBA")

    # Vertical gradient to keep the composition stable and readable.
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = _blend(primary, background, ratio * 0.7)
        draw.line([(0, y), (width, y)], fill=color)

    seed = _hash_seed(case.case_id)
    hero_x = width // 2 + (seed % 180) - 90
    hero_y = height // 2 + ((seed // 7) % 120) - 60
    hero_w = 560 + (seed % 60)
    hero_h = 760 + ((seed // 11) % 120)

    # Large soft hero mass in the center to simulate an art-directed subject.
    draw.ellipse(
        [
            (hero_x - hero_w // 2, hero_y - hero_h // 2),
            (hero_x + hero_w // 2, hero_y + hero_h // 2),
        ],
        fill=(*accent, 120),
    )
    draw.rounded_rectangle(
        [(180, 340), (width - 180, height - 320)],
        radius=42,
        outline=(*secondary, 55),
        width=4,
    )

    # Protected text zones to mimic good poster composition.
    draw.rectangle([(0, 0), (width, 260)], fill=(0, 0, 0, 26))
    draw.rounded_rectangle(
        [(80, height - 640), (width * 0.62, height - 210)],
        radius=28,
        fill=(255, 255, 255, 42),
    )
    draw.rectangle([(0, height - 160), (width, height)], fill=(*accent, 190))

    image = image.filter(ImageFilter.GaussianBlur(radius=1.4))

    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a poster PDF.

    Uses pdftotext (poppler) when available — it handles Chromium-rendered
    PDFs more reliably than pypdf for text spacing at line boundaries.
    Falls back to pypdf if pdftotext is not installed.
    """
    import subprocess

    try:
        proc = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: pypdf
    reader = PdfReader(str(pdf_path))
    text_parts: list[str] = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def _write_review_packet(packet: PosterAcceptancePacket) -> None:
    packet.report_dir.mkdir(parents=True, exist_ok=True)

    result_json = packet.report_dir / "result.json"
    result_json.write_text(
        json.dumps(
            {
                "case_id": packet.case.case_id,
                "title": packet.case.title,
                "pdf_path": str(packet.pdf_path),
                "image_path": str(packet.image_path),
                "weighted_score": packet.weighted_score,
                "qa_score": packet.qa_score,
                "image_prompt": packet.image_prompt,
                "stage_statuses": packet.stage_statuses,
                "poster_copy": packet.poster_copy,
                "manual_focus": list(packet.manual_focus),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    review_md = packet.report_dir / "review.md"
    review_md.write_text(
        "\n".join(
            [
                f"# {packet.case.title}",
                "",
                f"- Case ID: `{packet.case.case_id}`",
                f"- PDF: `{packet.pdf_path}`",
                f"- Background image: `{packet.image_path}`",
                f"- Weighted score: `{packet.weighted_score:.2f}`",
                f"- QA score: `{packet.qa_score:.2f}`",
                f"- Preferred templates: {', '.join(packet.case.preferred_templates)}",
                (
                    "- Discouraged templates: "
                    f"{', '.join(packet.case.discouraged_templates)}"
                ),
                (
                    "- Required prompt terms: "
                    f"{', '.join(packet.case.required_prompt_terms)}"
                ),
                "",
                "## Manual Focus",
                *[f"- {item}" for item in packet.manual_focus],
                "",
                "## Poster Copy",
                f"- Headline: {packet.poster_copy.get('headline', '')}",
                f"- Subheadline: {packet.poster_copy.get('subheadline', '')}",
                f"- CTA: {packet.poster_copy.get('cta', '')}",
                f"- Body: {packet.poster_copy.get('body_text', '')}",
                "",
                "## Extracted PDF Text",
                "",
                "```text",
                packet.pdf_text.strip(),
                "```",
                "",
                "## Captured Image Prompt",
                "",
                "```text",
                packet.image_prompt.strip(),
                "```",
            ]
        ),
        encoding="utf-8",
    )


def _patch_acceptance_environment(
    *,
    case: PosterAcceptanceCase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, str]:
    """Patch model/image calls and isolate the home directory per case."""
    captured: dict[str, str] = {}

    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    monkeypatch.setattr(PosixPath, "home", classmethod(lambda cls: home_dir))

    def fake_case_image_generate(
        *,
        prompt: str,
        model: str = "fal-ai/flux/dev",
        width: int = 1024,
        height: int = 1024,
        guidance_scale: float = 3.5,
        image_url: str | None = None,
    ) -> bytes:
        del model, width, height, guidance_scale, image_url
        captured["image_prompt"] = prompt
        return _render_case_background(case)

    def fake_expand_brief_llm(
        *,
        stable_prefix: list[dict[str, str]],
        variable_suffix: list[dict[str, str]],
        model: str = "gpt-5.4-mini",
        temperature: float = 0.4,
        max_tokens: int = 800,
        response_format: dict[str, Any] | None = None,
        operation_type: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        del stable_prefix, variable_suffix, model, temperature, max_tokens
        del response_format, operation_type, job_id
        return _mock_llm_response(json.dumps(_build_expand_brief_payload(case)))

    def fake_general_llm(
        *,
        stable_prefix: list[dict[str, str]],
        variable_suffix: list[dict[str, str]],
        model: str = "gpt-5.4-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
        operation_type: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        del (
            variable_suffix,
            model,
            temperature,
            max_tokens,
            response_format,
            operation_type,
        )
        del job_id
        system_content = stable_prefix[0]["content"] if stable_prefix else ""

        if "Classify the artifact type" in system_content:
            return _mock_llm_response("poster")
        if "Generate poster copy" in system_content:
            return _mock_llm_response(json.dumps(_build_poster_copy_payload(case)))
        if "You are a quality scorer" in system_content:
            return _mock_llm_response(
                json.dumps(
                    {
                        "score": 4.3,
                        "critique": {
                            "relevance": 4.0,
                            "completeness": 4.0,
                            "clarity": 4.5,
                            "accuracy": 4.5,
                            "issues": [],
                        },
                    }
                )
            )
        if "You are a quality reviser" in system_content:
            return _mock_llm_response(json.dumps(_build_poster_copy_payload(case)))
        return _mock_llm_response("ok")

    def fake_visual_qa_llm(
        *,
        stable_prefix: list[dict[str, str]],
        variable_suffix: list[dict[str, str]],
        model: str = "gpt-5.4-mini",
        temperature: float = 0.3,
        max_tokens: int = 300,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del (
            stable_prefix,
            variable_suffix,
            model,
            temperature,
            max_tokens,
            response_format,
        )
        return _mock_llm_response(json.dumps({"score": 4.2, "issues": []}))

    monkeypatch.setattr("tools.image.call_llm", fake_expand_brief_llm)
    monkeypatch.setattr("tools.image.generate_image", fake_case_image_generate)
    monkeypatch.setattr("utils.call_llm.call_llm", fake_general_llm)
    monkeypatch.setattr("tools.visual_scoring.call_llm", fake_visual_qa_llm)

    return captured


def _build_packet(
    *,
    case: PosterAcceptanceCase,
    result: dict[str, Any],
    captured: dict[str, str],
    tmp_path: Path,
) -> PosterAcceptancePacket:
    stage_results = {stage["stage"]: stage for stage in result["stages"]}
    production = stage_results["production"]
    qa = stage_results["qa"]
    delivery = stage_results["delivery"]

    pdf_path = Path(delivery["pdf_path"])
    image_path = Path(delivery["image_path"])
    pdf_text = _extract_pdf_text(pdf_path)
    poster_copy = json.loads(production["poster_copy"])

    packet = PosterAcceptancePacket(
        case=case,
        report_dir=tmp_path / "acceptance_reports" / case.case_id,
        pdf_path=pdf_path,
        image_path=image_path,
        pdf_text=pdf_text,
        image_prompt=captured.get("image_prompt", ""),
        weighted_score=float(qa.get("score", 0.0)),
        qa_score=float(qa.get("score", 0.0)),
        stage_statuses={
            stage_name: str(stage_output.get("status", ""))
            for stage_name, stage_output in stage_results.items()
        },
        poster_copy=poster_copy,
        manual_focus=case.manual_focus,
    )
    _write_review_packet(packet)
    return packet


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.acceptance
@pytest.mark.skipif(not _torch_available(), reason="torch not installed — required for visual scoring")
@pytest.mark.parametrize(
    "case",
    POSTER_ACCEPTANCE_CASES,
    ids=[case.case_id for case in POSTER_ACCEPTANCE_CASES],
)
def test_user_pov_poster_acceptance(
    case: PosterAcceptanceCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poster deliverables meet a baseline user-visible quality bar."""
    if shutil.which("typst") is None:
        pytest.skip("typst is required for poster acceptance tests")

    captured = _patch_acceptance_environment(
        case=case,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )

    result = run_governed(
        case.user_prompt,
        client_id="acceptance-client",
        job_id=f"acceptance-{case.case_id}",
    )
    packet = _build_packet(
        case=case,
        result=result,
        captured=captured,
        tmp_path=tmp_path,
    )

    report_hint = f"Review packet: {packet.report_dir}"
    normalised_pdf_text = _normalise_text(packet.pdf_text)
    normalised_headline = _normalise_text(packet.poster_copy["headline"])
    normalised_cta = _normalise_text(packet.poster_copy["cta"])
    normalised_body = _normalise_text(packet.poster_copy["body_text"])
    normalised_prompt = _normalise_text(packet.image_prompt)

    assert result["workflow"] == "poster_production", report_hint
    assert packet.stage_statuses == {
        "intake": "ok",
        "production": "ok",
        "qa": "ok",
        "delivery": "ok",
    }, report_hint
    assert packet.image_path.exists(), report_hint
    assert packet.pdf_path.exists(), report_hint
    assert packet.pdf_path.stat().st_size > 0, report_hint
    assert packet.weighted_score >= 4.0, report_hint
    assert normalised_headline in normalised_pdf_text, report_hint
    assert normalised_cta in normalised_pdf_text, report_hint
    assert normalised_body[:40] in normalised_pdf_text, report_hint

    for term in case.required_prompt_terms:
        assert term.lower() in normalised_prompt, (
            f"Missing required prompt term '{term}'. {report_hint}"
        )

    for avoid_term in case.mock_brief_response.get("avoid", []):
        assert avoid_term.lower() not in normalised_prompt, (
            f"Prompt should not include avoid term '{avoid_term}'. {report_hint}"
        )
