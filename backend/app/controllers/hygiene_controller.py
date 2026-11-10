"""HygieneController (FR-2.1 to FR-2.5)."""

from collections.abc import Iterable

from ..models import Licensee, SafeGradeValue, Stall
from ..schemas import GradeSummary, SafeGradeOut, TrackRecordOut

# Ordering used for the Hygiene Threshold. NEW sits between B and C: it isn't a failing
# grade (FR-2.2), but it has no track record yet either. Team to confirm this choice.
GRADE_RANK = {SafeGradeValue.A: 4, SafeGradeValue.B: 3, SafeGradeValue.NEW: 2, SafeGradeValue.C: 1}


class HygieneController:
    @staticmethod
    def current_grade(licensee: Licensee | None):
        if licensee is None or not licensee.grades:
            return None
        latest = licensee.grades[0]  # relationship is ordered newest first
        if licensee.last_seen_snapshot and latest.snapshot_date < licensee.last_seen_snapshot:
            return None  # latest SFA export had no SAFE grade for this licence
        return latest

    @staticmethod
    def grade_passes(grade: SafeGradeValue | None, threshold: SafeGradeValue | None) -> bool:
        """The Hygiene Threshold rule (FR-2.5) on a grade value. Every list that filters by a
        minimum grade (centre list, centre page, recommendations) goes through this."""
        if threshold is None:
            return True
        if grade is None:
            return False  # can't show an ungraded stall to someone who set a minimum
        return GRADE_RANK[grade] >= GRADE_RANK[threshold]

    @classmethod
    def passes_threshold(cls, stall: Stall, threshold: SafeGradeValue | None) -> bool:
        if threshold is None:
            return True
        g = cls.current_grade(stall.licensee)
        return cls.grade_passes(g.grade_value if g else None, threshold)

    @staticmethod
    def suspended_past_year(licensee: Licensee | None) -> bool:
        return bool(licensee and licensee.licence_status == "suspended")

    @classmethod
    def summary(cls, stalls: Iterable[Stall]) -> GradeSummary:
        s = GradeSummary()
        for st in stalls:
            g = cls.current_grade(st.licensee)
            if g is None:
                s.ungraded += 1
            else:
                setattr(s, g.grade_value.value, getattr(s, g.grade_value.value) + 1)
        return s

    @classmethod
    def track_record(cls, stall: Stall) -> TrackRecordOut:
        history = list(stall.licensee.grades) if stall.licensee else []
        # Collapse consecutive identical snapshots so the history shows changes, not every day
        changes: list = []
        for g in reversed(history):
            if not changes or changes[-1].grade_value != g.grade_value:
                changes.append(g)
        return TrackRecordOut(
            suspended_past_year=cls.suspended_past_year(stall.licensee),
            grade_history=[SafeGradeOut.model_validate(g) for g in reversed(changes)],
            last_updated=stall.licensee.last_seen_snapshot if stall.licensee else None,
        )
