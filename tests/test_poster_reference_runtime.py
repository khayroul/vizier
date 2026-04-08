from __future__ import annotations

import struct
import zlib
from pathlib import Path, PosixPath
from typing import Any, cast
from unittest.mock import MagicMock, patch

from contracts.policy import PolicyAction, PolicyDecision
from contracts.readiness import ReadinessResult
from contracts.routing import RoutingResult
from tools.orchestrate import run_governed
from tools.executor import ToolCallable


def _allow_decision() -> PolicyDecision:
    return PolicyDecision(
        action=PolicyAction.allow,
        reason="allowed",
        gate="all",
    )


def _png_bytes() -> bytes:
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + raw
            + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
        )

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat_data = zlib.compress(b"\x00\xff\xff\xff")
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr_data)
        + _chunk(b"IDAT", idat_data)
        + _chunk(b"IEND", b"")
    )


class TestPosterReferenceRuntime:
    def test_select_image_model_prefers_reference_adapt(self) -> None:
        from tools.image import select_image_model

        result = select_image_model(
            language="en",
            artifact_family="poster",
            image_mode="photorealistic",
            reference_image_url="https://fal.media/reference/poster.jpg",
        )

        assert result == "fal-ai/flux-pro/kontext"

    def test_select_image_dimensions_match_poster_platform(self) -> None:
        from tools.image import select_image_dimensions

        assert select_image_dimensions(
            artifact_family="poster",
            platform="telegram",
        ) == (1080, 1350)
        assert select_image_dimensions(
            artifact_family="poster",
            platform="print",
        ) == (1024, 1450)

    @patch("tools.image.generate_image")
    @patch("tools.image.expand_brief")
    @patch("utils.storage.upload_to_fal", return_value="https://fal.media/reference/poster.jpg")
    @patch(
        "tools.visual_dna.extract_visual_dna",
        return_value={
            "layout_type": "split-vertical",
            "dominant_colours": ["#112233", "#445566", "#778899"],
        },
    )
    def test_image_generate_uses_reference_poster_context(
        self,
        _mock_visual_dna: MagicMock,
        _mock_upload: MagicMock,
        mock_expand: MagicMock,
        mock_generate: MagicMock,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        from tools.registry import _image_generate

        reference_path = tmp_path / "reference.png"
        reference_path.write_bytes(_png_bytes())

        home_dir = tmp_path / "home"
        home_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
        monkeypatch.setattr(PosixPath, "home", classmethod(lambda cls: home_dir))

        mock_expand.return_value = {
            "composition": "Hero product in a premium campaign composition",
            "style": "premium traditional",
            "brand": "formal",
            "technical": "portrait poster",
            "text_content": "headline text",
        }
        mock_generate.return_value = _png_bytes()

        result = _image_generate(
            {
                "prompt": "Create a premium textile campaign poster",
                "job_context": {
                    "client_id": "dmb",
                    "artifact_family": "poster",
                    "language": "ms",
                    "platform": "telegram",
                    "reference_image_path": str(reference_path),
                    "reference_notes": "keep the diagonal energy and hierarchy",
                },
                "artifact_payload": {},
            }
        )

        expand_prompt = mock_expand.call_args.args[0]
        assert "Reference poster guidance" in expand_prompt
        assert "split-vertical" in expand_prompt
        assert "diagonal energy" in expand_prompt

        gen_kwargs = mock_generate.call_args.kwargs
        assert gen_kwargs["model"] == "fal-ai/flux-pro/kontext"
        assert gen_kwargs["image_url"] == "https://fal.media/reference/poster.jpg"
        assert (gen_kwargs["width"], gen_kwargs["height"]) == (1080, 1350)
        assert result["reference_visual_dna"]["layout_type"] == "split-vertical"
        assert result["reference_image_url"] == "https://fal.media/reference/poster.jpg"

    @patch("tools.visual_pipeline.evaluate_visual_artifact")
    def test_visual_qa_uses_expanded_brief_and_reference_context(
        self,
        mock_evaluate: MagicMock,
    ) -> None:
        from tools.registry import _visual_qa

        mock_evaluate.return_value = {
            "passed": True,
            "weighted_score": 4.2,
            "qa_threshold": 3.2,
            "nima_score": 6.2,
            "nima_action": "pass",
            "critique": "good",
            "guardrail_flags": [],
            "input_tokens": 10,
            "output_tokens": 6,
            "cost_usd": 0.001,
        }

        result = _visual_qa(
            {
                "job_context": {
                    "client_id": "dmb",
                    "artifact_family": "poster",
                    "language": "ms",
                    "copy_register": "formal",
                    "runtime_controls": {"qa_threshold": 3.2},
                },
                "artifact_payload": {
                    "image_path": "/tmp/poster.png",
                    "poster_copy": '{"headline": "Sale"}',
                    "template_name": "poster_default",
                },
                "previous_output": {
                    "expanded_brief": {
                        "composition": "Split vertical hero scene",
                        "style": "premium",
                    },
                    "reference_visual_dna": {
                        "layout_type": "split-vertical",
                        "dominant_colours": ["#112233", "#445566"],
                    },
                },
            }
        )

        brief = mock_evaluate.call_args.kwargs["brief"]
        assert brief["composition"] == "Split vertical hero scene"
        assert brief["reference_layout"] == "split-vertical"
        assert "#112233" in brief["reference_palette"]
        assert result["status"] == "ok"

    @patch("tools.orchestrate.WorkflowExecutor")
    @patch("tools.orchestrate.PolicyEvaluator")
    @patch("tools.orchestrate.evaluate_readiness")
    @patch("tools.orchestrate.route")
    def test_run_governed_passes_reference_fields_into_job_context(
        self,
        mock_route: MagicMock,
        mock_readiness: MagicMock,
        mock_policy_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        mock_route.return_value = RoutingResult(workflow="poster_production", job_id="j1")
        mock_readiness.return_value = ReadinessResult(status="ready", completeness=1.0)
        mock_policy_cls.return_value.evaluate.return_value = _allow_decision()
        mock_executor_cls.return_value.run.return_value = {
            "workflow": "poster_production",
            "stages": [],
            "trace": {},
        }

        run_governed(
            "Create a poster like my sample",
            client_id="dmb",
            job_id="j1",
            tool_registry={"x": cast(ToolCallable, lambda _: {"status": "ok", "output": "ok"})},
            platform="telegram",
            reference_image_path="/tmp/sample.png",
            reference_notes="reuse the same information hierarchy",
        )

        job_ctx = mock_executor_cls.return_value.run.call_args.kwargs["job_context"]
        assert job_ctx["platform"] == "telegram"
        assert job_ctx["reference_image_path"] == "/tmp/sample.png"
        assert job_ctx["reference_notes"] == "reuse the same information hierarchy"
