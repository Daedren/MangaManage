"""Bounded binary reads and resumable SSE following for CLI and API logs."""

import asyncio
import codecs
import json
import os
import time


MAX_CHUNK_BYTES = 64 * 1024
POLL_SECONDS = 0.25
HEARTBEAT_SECONDS = 10


def read_log(path, cursor=None, limit=MAX_CHUNK_BYTES, complete=False):
    try:
        with path.open("rb") as file:
            stat = os.fstat(file.fileno())
            generation = f"{stat.st_dev:x}-{stat.st_ino:x}"
            offset = None
            if cursor:
                try:
                    previous_generation, previous_offset = cursor.rsplit(":", 1)
                    previous_offset = int(previous_offset)
                    if previous_generation == generation and 0 <= previous_offset <= stat.st_size:
                        offset = previous_offset
                except (ValueError, TypeError):
                    pass
            reset = offset is None
            offset = max(0, stat.st_size - limit) if reset else offset
            truncated = reset and offset > 0
            file.seek(offset)
            if reset and offset:
                # A tail may start mid-codepoint. Skip UTF-8 continuation bytes.
                for _ in range(min(3, limit)):
                    byte = file.read(1)
                    if not byte or byte[0] & 0xC0 != 0x80:
                        file.seek(-len(byte), 1)
                        break
            start = file.tell()
            data = file.read(limit - (start - offset))
            # Hold incomplete UTF-8 at EOF or a chunk boundary for the next read.
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            text = decoder.decode(data, final=complete and file.tell() >= stat.st_size)
            buffered, _ = decoder.getstate()
            consumed = len(data) - len(buffered)
            return {
                "logs": text, "exists": True, "cursor": f"{generation}:{start + consumed}",
                "reset": reset, "truncated": truncated,
                "has_more": start + consumed < stat.st_size,
            }
    except FileNotFoundError:
        return {"logs": "", "exists": False, "cursor": "", "reset": bool(cursor), "truncated": False, "has_more": False}


def sse(event, payload, cursor=None):
    identity = f"id: {cursor}\n" if cursor is not None else ""
    return f"{identity}event: {event}\ndata: {json.dumps(payload)}\n\n"


async def follow_logs(request, path, cursor=None, status=None):
    last_status = None
    heartbeat = time.monotonic()
    first = True
    while not await request.is_disconnected():
        chunk = await asyncio.to_thread(read_log, path, cursor)
        if first or chunk["logs"] or chunk["reset"] or chunk["cursor"] != cursor:
            yield sse("logs", chunk, chunk["cursor"])
            cursor = chunk["cursor"]
            first = False
            heartbeat = time.monotonic()
        if status:
            try:
                run = await asyncio.to_thread(status)
            except KeyError:
                yield sse("unavailable", {"message": "This run's logs are no longer retained."})
                return
            if run != last_status:
                yield sse("status", run)
                last_status = run
            if run["status"] != "running":
                # Re-read after observing completion so final flushes cannot be missed.
                final = await asyncio.to_thread(read_log, path, cursor, MAX_CHUNK_BYTES, True)
                if final["logs"] or final["reset"]:
                    yield sse("logs", final, final["cursor"])
                    cursor = final["cursor"]
                if not final["has_more"]:
                    yield sse("done", run)
                    return
        if time.monotonic() - heartbeat >= HEARTBEAT_SECONDS:
            yield ": heartbeat\n\n"
            heartbeat = time.monotonic()
        await asyncio.sleep(0 if chunk["has_more"] and chunk["logs"] else POLL_SECONDS)
