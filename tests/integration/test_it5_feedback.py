"""IT-5: Feedback State Machine Integration Test.

Validates: S10a feedback triggers → quality exclusion logic.
Tests the state machine transitions enforced by database triggers.

States: awaiting → explicitly_approved | revision_requested | rejected | silence_flagged
        silence_flagged → prompted
        prompted → responded | unresponsive
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest

pytestmark = pytest.mark.requires_db

from utils.database import get_cursor


class TestSilenceDetection:
    """feedback_check_silence() flags stale awaiting records."""

    def test_silence_detection_flags_old_feedback(
        self, test_feedback_awaiting
    ) -> None:
        """Feedback delivered >24h ago transitions awaiting → silence_flagged."""
        feedback_id = test_feedback_awaiting["id"]

        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")
            row = cur.fetchone()
            flagged_count = row["feedback_check_silence"]

        assert flagged_count >= 1, (
            f"Expected at least 1 record flagged, got {flagged_count}"
        )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["feedback_status"] == "silence_flagged", (
            f"Expected 'silence_flagged', got '{row['feedback_status']}'"
        )

    def test_silence_detection_skips_recent_feedback(
        self, test_client, test_job, test_artifact
    ) -> None:
        """Feedback delivered <24h ago is NOT flagged."""
        feedback_id = str(uuid.uuid4())
        delivered_at = datetime.now(timezone.utc) - timedelta(hours=10)
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status, delivered_at)
                VALUES (%s, %s, %s, %s, 'awaiting', %s)
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"], delivered_at),
            )

        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["feedback_status"] == "awaiting", (
            f"Recent feedback should remain 'awaiting', got '{row['feedback_status']}'"
        )


class TestQualityExclusion:
    """silence_flagged and unresponsive records excluded from quality metrics."""

    def test_silence_flagged_excluded_from_quality_view(
        self, test_feedback_awaiting
    ) -> None:
        """v_feedback_quality view excludes silence_flagged records."""
        client_id = test_feedback_awaiting["client_id"]

        # Flag it as silence_flagged
        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        # Verify it's excluded from the quality view
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM v_feedback_quality WHERE client_id = %s",
                (client_id,),
            )
            row = cur.fetchone()

        # The silence_flagged record should not count in quality metrics.
        # If there's no row, all feedback was excluded (correct).
        # If there is a row, approved/revision_requested/rejected should be 0.
        if row is not None:
            assert row["approved"] == 0
            assert row["revision_requested"] == 0
            assert row["rejected"] == 0

    def test_quality_average_excludes_silence(
        self, test_client, test_job, test_artifact
    ) -> None:
        """Average operator_rating calculation excludes silence_flagged records.

        Create 2 feedback records:
        - One explicitly_approved with rating=5
        - One silence_flagged with rating=1

        Average should be 5.0 (only the approved one counts).
        """
        client_id = test_client["id"]

        # Create approved feedback with rating=5
        approved_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id,
                                      feedback_status, delivered_at, operator_rating)
                VALUES (%s, %s, %s, %s, 'awaiting', now() - interval '2 hours', 5)
                """,
                (approved_id, test_job["id"], test_artifact["id"], client_id),
            )

        # Transition to explicitly_approved
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'explicitly_approved' WHERE id = %s",
                (approved_id,),
            )

        # Create silence_flagged feedback with rating=1
        silence_id = str(uuid.uuid4())
        delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id,
                                      feedback_status, delivered_at, operator_rating)
                VALUES (%s, %s, %s, %s, 'awaiting', %s, 1)
                """,
                (silence_id, test_job["id"], test_artifact["id"], client_id, delivered_at),
            )

        # Flag silence
        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        # Check quality view — only the approved record's rating should count
        with get_cursor() as cur:
            cur.execute(
                "SELECT avg_operator_rating FROM v_feedback_quality WHERE client_id = %s",
                (client_id,),
            )
            row = cur.fetchone()

        assert row is not None, "Expected a row in v_feedback_quality for the approved record"
        assert float(row["avg_operator_rating"]) == 5.0, (
            f"Expected avg_operator_rating=5.0 (excluding silence_flagged), "
            f"got {row['avg_operator_rating']}"
        )


class TestValidTransitions:
    """Valid state machine transitions succeed."""

    def test_awaiting_to_explicitly_approved(
        self, test_client, test_job, test_artifact
    ) -> None:
        """awaiting → explicitly_approved is valid."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'explicitly_approved' WHERE id = %s",
                (feedback_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status, feedback_received_at, response_time_hours FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row["feedback_status"] == "explicitly_approved"
        assert row["feedback_received_at"] is not None
        assert row["response_time_hours"] is not None

    def test_awaiting_to_revision_requested(
        self, test_client, test_job, test_artifact
    ) -> None:
        """awaiting → revision_requested is valid."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'revision_requested' WHERE id = %s",
                (feedback_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row["feedback_status"] == "revision_requested"

    def test_awaiting_to_rejected(
        self, test_client, test_job, test_artifact
    ) -> None:
        """awaiting → rejected is valid."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'rejected' WHERE id = %s",
                (feedback_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row["feedback_status"] == "rejected"

    def test_silence_flagged_to_prompted(self, test_feedback_awaiting) -> None:
        """silence_flagged → prompted is valid."""
        feedback_id = test_feedback_awaiting["id"]

        # awaiting → silence_flagged
        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        # silence_flagged → prompted
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'prompted' WHERE id = %s",
                (feedback_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status, prompted_at FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["feedback_status"] == "prompted"
        assert row["prompted_at"] is not None, "prompted_at should be auto-set by trigger"

    def test_prompted_to_responded(self, test_feedback_awaiting) -> None:
        """prompted → responded is valid (full chain)."""
        feedback_id = test_feedback_awaiting["id"]

        # awaiting → silence_flagged
        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        # silence_flagged → prompted
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'prompted' WHERE id = %s",
                (feedback_id,),
            )

        # prompted → responded
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'responded' WHERE id = %s",
                (feedback_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status, feedback_received_at FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["feedback_status"] == "responded"
        assert row["feedback_received_at"] is not None

    def test_prompted_to_unresponsive(
        self, test_client, test_job, test_artifact
    ) -> None:
        """prompted → unresponsive is valid (client never responded after follow-up)."""
        feedback_id = str(uuid.uuid4())
        delivered_at = datetime.now(timezone.utc) - timedelta(hours=50)
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status, delivered_at)
                VALUES (%s, %s, %s, %s, 'awaiting', %s)
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"], delivered_at),
            )

        # awaiting → silence_flagged
        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        # silence_flagged → prompted
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'prompted' WHERE id = %s",
                (feedback_id,),
            )

        # prompted → unresponsive
        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'unresponsive' WHERE id = %s",
                (feedback_id,),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT feedback_status FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["feedback_status"] == "unresponsive"


class TestInvalidTransitions:
    """Invalid state machine transitions raise errors."""

    def test_awaiting_to_prompted_is_invalid(
        self, test_client, test_job, test_artifact
    ) -> None:
        """awaiting → prompted is invalid (must go through silence_flagged first)."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with pytest.raises(psycopg2.errors.RaiseException, match="Invalid feedback transition"):
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE feedback SET feedback_status = 'prompted' WHERE id = %s",
                    (feedback_id,),
                )

    def test_awaiting_to_responded_is_invalid(
        self, test_client, test_job, test_artifact
    ) -> None:
        """awaiting → responded is invalid (must go through silence_flagged → prompted)."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with pytest.raises(psycopg2.errors.RaiseException, match="Invalid feedback transition"):
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE feedback SET feedback_status = 'responded' WHERE id = %s",
                    (feedback_id,),
                )

    def test_silence_flagged_to_approved_is_invalid(
        self, test_client, test_job, test_artifact
    ) -> None:
        """silence_flagged → explicitly_approved is invalid (must go through prompted)."""
        feedback_id = str(uuid.uuid4())
        delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status, delivered_at)
                VALUES (%s, %s, %s, %s, 'awaiting', %s)
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"], delivered_at),
            )

        # awaiting → silence_flagged
        with get_cursor() as cur:
            cur.execute("SELECT feedback_check_silence()")

        # Verify it's silence_flagged
        with get_cursor() as cur:
            cur.execute("SELECT feedback_status FROM feedback WHERE id = %s", (feedback_id,))
            row = cur.fetchone()
            assert row["feedback_status"] == "silence_flagged"

        # silence_flagged → explicitly_approved should fail
        with pytest.raises(psycopg2.errors.RaiseException, match="Invalid feedback transition"):
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE feedback SET feedback_status = 'explicitly_approved' WHERE id = %s",
                    (feedback_id,),
                )

    def test_explicitly_approved_is_terminal(
        self, test_client, test_job, test_artifact
    ) -> None:
        """explicitly_approved is a terminal state — no further transitions allowed."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "UPDATE feedback SET feedback_status = 'explicitly_approved' WHERE id = %s",
                (feedback_id,),
            )

        with pytest.raises(psycopg2.errors.RaiseException, match="Invalid feedback transition"):
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE feedback SET feedback_status = 'revision_requested' WHERE id = %s",
                    (feedback_id,),
                )


class TestInsertTrigger:
    """Verify the insert trigger auto-sets delivered_at."""

    def test_insert_sets_delivered_at(
        self, test_client, test_job, test_artifact
    ) -> None:
        """Inserting with status='awaiting' auto-sets delivered_at to now()."""
        feedback_id = str(uuid.uuid4())
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (id, job_id, artifact_id, client_id, feedback_status)
                VALUES (%s, %s, %s, %s, 'awaiting')
                """,
                (feedback_id, test_job["id"], test_artifact["id"], test_client["id"]),
            )

        with get_cursor() as cur:
            cur.execute(
                "SELECT delivered_at FROM feedback WHERE id = %s",
                (feedback_id,),
            )
            row = cur.fetchone()

        assert row["delivered_at"] is not None, (
            "Insert trigger should auto-set delivered_at when feedback_status='awaiting'"
        )
