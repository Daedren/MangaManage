"""Read-only series checks and explicit, revalidated problem resolution.

Checks do not depend on quarantine membership. Automation can call checkSeries
for a report (including incomplete checks), or listSeriesProblems for an array
that raises rather than silently returning incomplete findings.
"""
import logging

from manga.missingChapters import CheckGapsInChapters


CHECK_TYPES = ("tracker_gap", "consecutive_gap", "mangaupdates_lag")


def mangaUpdatesStatus(item, progress, progress_error=None):
    """Shared cached-release comparison for library rows and per-series checks."""
    latest = item.get("mangaupdates_latest_chapter")
    stored = item.get("latest_stored_chapter") or 0
    series_id = item.get("anilistId")
    last_read = progress.get(series_id) if progress is not None else None
    if latest is None:
        if series_id is None:
            reason = "No AniList ID assigned; MangaUpdates cannot be linked."
        elif item.get("mangaupdates_id") is None:
            reason = "No MangaUpdates ID linked to this series."
        else:
            reason = "MangaUpdates ID is linked, but no latest chapter has been cached."
        return "unavailable", reason
    if stored >= latest or (last_read is not None and last_read >= latest):
        return "up_to_date", None
    if series_id is None:
        return "unknown", "Stored chapters are behind; no AniList ID assigned to check read progress."
    if progress is None:
        return "unknown", progress_error or "AniList progress is unavailable. Try again later."
    if series_id in progress and last_read is None:
        return "unknown", "AniList returned no read progress for this series."
    reason = None if series_id in progress else "Stored chapters are behind; this series is not on your AniList list."
    return "missing_chapters", reason


class SeriesProblemError(Exception):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


class SeriesProblems:
    def __init__(self, database, filesystem, tracker, suwayomi=None):
        self.database = database
        self.filesystem = filesystem
        self.tracker = tracker
        self.suwayomi = suwayomi
        self.gaps = CheckGapsInChapters(database, filesystem, tracker)

    def _context(self, series_id, checks):
        rows = self.database.getActiveChaptersForAnilist(series_id)
        context = {"chapters": [float(row["chapter"]) for row in rows],
                   "title": rows[0]["series"] if rows else str(series_id),
                   "progress": None, "progress_error": None}
        if "tracker_gap" in checks or "mangaupdates_lag" in checks:
            try:
                entries = self.tracker.getAllEntries(reading_only=False)
                if entries is not None:
                    context["progress"] = {key: entry.progress for key, entry in entries.items()}
                else:
                    context["progress_error"] = "AniList returned no read-progress response."
            except Exception:
                logging.getLogger(__name__).warning("Unable to check AniList progress for series problems")
                context["progress_error"] = "AniList progress is unavailable. Check the connection and authentication, then try again."
        if "mangaupdates_lag" in checks:
            try:
                context["mangaupdates"] = self.database.getMangaUpdatesForAnilist(series_id)
            except Exception:
                logging.getLogger(__name__).warning("Unable to read cached MangaUpdates details")
                context["mangaupdates"] = {}
                context["mangaupdates_error"] = "Unable to read cached MangaUpdates details. Try again or check server logs."
        return context

    @staticmethod
    def _result(problems=(), status="checked", message=None):
        return {"problems": list(problems), "status": status, "message": message}

    def checkTrackerGap(self, series_id, *, context=None):
        context = context if context is not None else self._context(series_id, ["tracker_gap"])
        if not context["chapters"]:
            return self._result(status="unavailable", message="No active chapters available to check the tracker gap.")
        progress = context["progress"]
        last_read = progress.get(series_id) if progress is not None else None
        if last_read is None:
            return self._result(status="unavailable", message=context["progress_error"] or "No AniList read progress available for this series.")
        gap = self.gaps.checkTrackerGap(series_id, context["title"], last_read, context["chapters"])
        return self._result([{"type": "tracker_gap", "last_read": gap.tracker_chapter,
                              "first_stored": gap.stored_chapter}] if gap else [])

    def checkConsecutiveGaps(self, series_id, *, context=None):
        context = context if context is not None else self._context(series_id, ["consecutive_gap"])
        if not context["chapters"]:
            return self._result(status="unavailable", message="No active chapters available to check consecutive gaps.")
        gaps = self.gaps.checkConsecutiveGaps(series_id, context["title"], context["chapters"])
        return self._result([{"type": "consecutive_gap", "before": gap.first_chapter,
                              "after": gap.second_chapter} for gap in gaps])

    def checkMangaUpdatesLag(self, series_id, *, context=None):
        context = context if context is not None else self._context(series_id, ["mangaupdates_lag"])
        if context.get("mangaupdates_error"):
            return self._result(status="error", message=context["mangaupdates_error"])
        item = {**context["mangaupdates"], "anilistId": series_id,
                "latest_stored_chapter": max(context["chapters"], default=0)}
        status, reason = mangaUpdatesStatus(item, context["progress"], context["progress_error"])
        if status in ("unknown", "unavailable"):
            return self._result(status="unavailable", message=reason)
        if status == "up_to_date":
            return self._result()
        last_read = context["progress"].get(series_id) or 0
        return self._result([{"type": "mangaupdates_lag",
                              "after": max(item["latest_stored_chapter"], last_read),
                              "through": item["mangaupdates_latest_chapter"]}])

    def checkSeries(self, series_id, checks=None):
        """Report findings and check completeness, sharing one input snapshot."""
        selected = list(dict.fromkeys(CHECK_TYPES if checks is None else checks))
        if any(check not in CHECK_TYPES for check in selected):
            raise ValueError("Unknown series problem check")
        context = self._context(series_id, selected)
        handlers = {"tracker_gap": self.checkTrackerGap,
                    "consecutive_gap": self.checkConsecutiveGaps,
                    "mangaupdates_lag": self.checkMangaUpdatesLag}
        report = {"problems": [], "checks": []}
        for check in selected:
            try:
                result = handlers[check](series_id, context=context)
            except Exception:
                logging.getLogger(__name__).warning("Unable to run series problem check %s", check)
                result = self._result(status="error", message="Unable to complete this check. Try again or check server logs.")
            report["problems"].extend(result["problems"])
            report["checks"].append({"type": check, "status": result["status"], "message": result["message"]})
        return report

    def listSeriesProblems(self, series_id, checks=None):
        """Return an array; incomplete checks raise so automation cannot miss failures."""
        report = self.checkSeries(series_id, checks)
        unavailable = [check["message"] for check in report["checks"] if check["status"] != "checked"]
        if unavailable:
            raise SeriesProblemError(" ".join(unavailable))
        return report["problems"]

    def resolveSeriesProblem(self, series_id, problem):
        """Recheck this finding before queuing; never mark a queued problem resolved."""
        if problem["type"] != "consecutive_gap":
            self.tracker.clearCache()
        report = self.checkSeries(series_id, [problem["type"]])
        check = report["checks"][0]
        if check["status"] != "checked":
            raise SeriesProblemError(check["message"])
        if problem not in report["problems"]:
            raise SeriesProblemError("This problem has changed or is no longer present. Check this series again.", 409)
        return self._downloadProblem(series_id, problem)

    def resolveQuarantineGap(self, series_id, problem):
        """Compatibility action retaining quarantine membership and tracker priority."""
        if series_id not in self.filesystem.getQuarantinedSeries():
            raise SeriesProblemError("This series is no longer quarantined. Refresh its details.", 409)
        self.tracker.clearCache()
        details = self.gaps.getQuarantineDetails(series_id)
        if details["status"] == "tracker_unavailable":
            raise SeriesProblemError("AniList progress is unavailable. Try again later.")
        if problem not in details["reasons"]:
            raise SeriesProblemError("This gap has changed or is no longer present. Refresh its details.", 409)
        return self._downloadProblem(series_id, problem)

    def _downloadProblem(self, series_id, problem):
        if problem["type"] == "mangaupdates_lag":
            return self.suwayomi.queueChapterRangeDownloads(
                series_id, problem["after"], problem["through"], include_upper=True,
            )
        if problem["type"] == "tracker_gap":
            lower, upper = problem["last_read"], problem["first_stored"]
        else:
            lower, upper = problem["before"], problem["after"]
        return self.suwayomi.queueGapDownloads(series_id, lower, upper)
