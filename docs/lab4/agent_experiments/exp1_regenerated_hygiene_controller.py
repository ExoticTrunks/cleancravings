"""HygieneController (FR-2.1 to FR-2.5).

Works out a stall's current SAFE grade from the dated SFA snapshots, its track record,
and whether it meets a user's Hygiene Threshold (also used for FR-5.4)."""

from collections.abc import Iterable

from ..models import Licensee, SAFEGrade, SafeGradeValue, Stall, StallType
from ..schemas import GradeSummary, SafeGradeOut, TrackRecordOut

# A > B > NEW > C. NEW (licensed under a year) ranks above C because SFA says it
# must not be presented as a failing grade (FR-2.2). All ranks are > 0, so callers
# can use 0 for "no current grade".
GRADE_RANK = {SafeGradeValue.A: 4, SafeGradeValue.B: 3, SafeGradeValue.NEW: 2, SafeGradeValue.C: 1}


def _history(licensee: Licensee) -> list[SAFEGrade]:
    # Newest first. The relationship is already ordered that way when loaded from the
    # database, but objects built in memory may not be
    return sorted(licensee.grades, key=lambda g: g.snapshot_date, reverse=True)


class HygieneController:
    @staticmethod
    def current_grade(licensee: Licensee | None) -> SAFEGrade | None:
        """The newest snapshot (FR-2.1), but only if it came from the latest SFA export that
        listed the licence. An older one means SFA no longer gives it a grade there
        (e.g. "Not Under SAFE"), so there is no current grade."""
        if licensee is None or not licensee.grades:
            return None
        newest = _history(licensee)[0]
        if licensee.last_seen_snapshot and newest.snapshot_date < licensee.last_seen_snapshot:
            return None
        return newest

    @staticmethod
    def passes_threshold(stall: Stall, threshold: SafeGradeValue | None) -> bool:
        """True if the stall's current grade ranks at or above the minimum (FR-2.5, FR-5.4).
        With no minimum every stall passes; with one, a stall with no current grade (or no
        licensee) fails, so ungraded stalls are never shown to someone who asked for a minimum."""
        if threshold is None:
            return True
        g = HygieneController.current_grade(stall.licensee)
        return g is not None and GRADE_RANK[g.grade_value] >= GRADE_RANK[threshold]

    @staticmethod
    def summary(stalls: Iterable[Stall]) -> GradeSummary:
        """How many of a centre's Cooked Food stalls (FR-1.6) hold each current grade."""
        counts = {"A": 0, "B": 0, "C": 0, "NEW": 0, "ungraded": 0}
        for s in stalls:
            if s.stall_type != StallType.COOKED_FOOD:
                continue
            g = HygieneController.current_grade(s.licensee)
            counts[g.grade_value.value if g else "ungraded"] += 1
        return GradeSummary(**counts)

    @staticmethod
    def track_record(stall: Stall) -> TrackRecordOut:
        """Built from the snapshots, not stored (FR-2.3, FR-2.4). SFA only publishes a
        "suspended in the past year" flag, not demerit points, so total_demerit_points stays null."""
        lic = stall.licensee
        if lic is None:
            return TrackRecordOut(suspended_past_year=False, grade_history=[], last_updated=None)
        return TrackRecordOut(
            suspended_past_year=lic.licence_status == "suspended",
            grade_history=[SafeGradeOut.model_validate(g) for g in _history(lic)],
            last_updated=lic.last_seen_snapshot,
        )
