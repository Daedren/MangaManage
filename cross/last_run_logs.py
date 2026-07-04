import logging
import sys
from contextlib import contextmanager
from pathlib import Path


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


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

    def write(self, value):
        self.original.write(value)
        self.log_file.write(value)

    def flush(self):
        self.original.flush()
        self.log_file.flush()

    def isatty(self):
        return self.original.isatty()


@contextmanager
def capture_last_run_logs(config, run_name: str):
    log_path = get_last_run_log_path(config)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    output = log_path.open("w", encoding="utf-8")
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(config["system"].get("loglevel", "INFO"))

    logger = logging.getLogger("last_run")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = TeeStream(original_stdout, output)
    sys.stderr = TeeStream(original_stderr, output)

    try:
        logger.info("Starting %s", run_name)
        yield log_path
        logger.info("Finished %s", run_name)
    except Exception:
        logger.exception("Failed %s", run_name)
        raise
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        root_logger.removeHandler(handler)
        handler.close()
        output.close()
