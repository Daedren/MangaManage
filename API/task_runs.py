"""Small single-worker task runner; run status survives browser and API restarts."""

import datetime
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from cross.last_run_logs import CaptureBusy, CaptureLease, capture_last_run_logs, get_last_run_log_path


class TaskRuns:
    def __init__(self, config):
        self.config = config
        self.directory = get_last_run_log_path(config).parent / "task-runs"
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="maintenance")

    def _write(self, run):
        path = self.directory / f"{run['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(run), encoding="utf-8")
        temporary.replace(path)

    def get(self, run_id):
        # Never accept a path supplied by a client.
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise KeyError(run_id)
        try:
            run = json.loads((self.directory / f"{run_id}.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(run_id) from None

        # A previous process may have stopped mid-run. Probe the cross-process lock
        # rather than reporting that task as running forever (or automatically rerunning it).
        if run["status"] == "running":
            try:
                lease = CaptureLease(self.config)
            except CaptureBusy:
                return run
            try:
                run = json.loads((self.directory / f"{run_id}.json").read_text(encoding="utf-8"))
                if run["status"] == "running":
                    run.update(
                        status="interrupted", finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        error="The API stopped before this task finished. Check its logs before running it again.",
                    )
                    self._write(run)
            finally:
                lease.release()
        return run

    def latest(self):
        paths = self._ordered_paths()
        # A run's completion/recovery time must not change which task started last.
        for path in reversed(paths):
            try:
                return self.get(path.stem)
            except KeyError:
                continue  # Retention may have removed a run during this read.
        return None

    def _ordered_paths(self):
        entries = []
        for path in self.directory.glob("*.json"):
            try:
                run = json.loads(path.read_text(encoding="utf-8"))
                entries.append((run.get("started_at", ""), path))
            except FileNotFoundError:
                continue
        return [path for _, path in sorted(entries)]

    def start(self, label, action):
        lease = CaptureLease(self.config)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            run = {
                "id": uuid.uuid4().hex, "label": label, "status": "running",
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "finished_at": None, "result": None, "error": None,
            }
            self._write(run)
            response = dict(run)
            self.executor.submit(self._execute, run, action, lease)
            return response
        except Exception:
            lease.release()
            raise

    def _execute(self, run, action, lease):
        try:
            with capture_last_run_logs(
                self.config, run["label"], log_path=self.log_path(run["id"]), lease=lease,
            ):
                result = action()
                # Validate before marking successful so persistence cannot strand a run.
                json.dumps(result)
                run.update(status="succeeded", result=result)
        except Exception:
            run.update(status="failed", error="Task failed. See its logs for details.")
        finally:
            run["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                self._write(run)
                self._prune()
            finally:
                lease.release()

    def log_path(self, run_id):
        self.get(run_id)
        return self.directory / f"{run_id}.log"

    def _prune(self):
        # Keep the latest 20 runs; last-run.log remains a separate hard link.
        for path in self._ordered_paths()[:-20]:
            path.with_suffix(".log").unlink(missing_ok=True)
            path.unlink(missing_ok=True)

    def close(self):
        self.executor.shutdown(wait=True)
