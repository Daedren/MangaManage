import logging
import fcntl
import os
import sys
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_capture_mutex = threading.Lock()


class CaptureBusy(RuntimeError):
    pass


class CaptureLease:
    """Reserve capture before dispatch, including across CLI/API processes."""

    def __init__(self, config):
        if not _capture_mutex.acquire(blocking=False):
            raise CaptureBusy("Another task or log-writing operation is running. Try again after it finishes.")
        self.file = None
        try:
            path = get_last_run_log_path(config).with_suffix(".lock")
            path.parent.mkdir(parents=True, exist_ok=True)
            self.file = path.open("a")
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as error:
            if self.file is not None:
                self.file.close()
            _capture_mutex.release()
            if isinstance(error, BlockingIOError):
                raise CaptureBusy("Another CLI or API task is running. Try again after it finishes.") from None
            raise

    def release(self):
        if self.file is not None:
            self.file.close()
            self.file = None
            _capture_mutex.release()


def get_last_run_log_path(config) -> Path:
    database_path = Path(config["database"]["sqlitelocation"])
    return database_path.parent / "last-run.log"


def configure_console_logging(level, stream):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.basicConfig(level=level, handlers=[handler], force=True)


class TeeStream:
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file
        self.thread_id = threading.get_ident()

    def write(self, value):
        result = self.original.write(value)
        if threading.get_ident() == self.thread_id:
            self.log_file.write(value)
            self.log_file.flush()
        return result

    def flush(self):
        self.original.flush()
        if threading.get_ident() == self.thread_id:
            self.log_file.flush()

    def isatty(self):
        return self.original.isatty()

    def __getattr__(self, name):
        return getattr(self.original, name)


@contextmanager
def capture_last_run_logs(config, run_name: str, *, log_path=None, lease=None):
    owned_lease = lease is None
    lease = lease or CaptureLease(config)
    try:
        with _capture(config, run_name, log_path) as path:
            yield path
    finally:
        if owned_lease:
            lease.release()


@contextmanager
def _capture(config, run_name, log_path):
    latest_path = get_last_run_log_path(config)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    # Replace rather than truncate: followers can identify even an equally sized new run.
    temporary = latest_path.with_name(f".last-run-{uuid.uuid4().hex}")
    log_path = log_path or temporary
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output = log_path.open("w", encoding="utf-8", buffering=1)
    try:
        if log_path != temporary:
            os.link(log_path, temporary)
        os.replace(temporary, latest_path)
    except Exception:
        output.close()
        temporary.unlink(missing_ok=True)
        raise
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    thread_id = threading.get_ident()
    handler.addFilter(lambda record: record.thread == thread_id)

    root_logger = logging.getLogger()
    original_level = root_logger.level

    logger = logging.getLogger("last_run")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    try:
        root_logger.setLevel(config["system"].get("loglevel", "INFO"))
        root_logger.addHandler(handler)
        sys.stdout = TeeStream(original_stdout, output)
        sys.stderr = TeeStream(original_stderr, output)
        logger.info("Starting %s", run_name)
        yield latest_path
        logger.info("Finished %s", run_name)
    except Exception:
        logger.exception("Failed %s", run_name)
        raise
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)
        handler.close()
        output.close()
