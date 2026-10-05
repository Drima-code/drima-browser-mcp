"""Firefox native messaging relay, available only through a user-owned Unix socket."""

import fcntl
import json
import os
import socket
import stat
import struct
import sys
import threading
from pathlib import Path
from uuid import uuid4

MAX_MESSAGE = 256 * 1024


def socket_path() -> Path:
    directory = Path(
        os.environ.get(
            "DRIMA_REGULAR_BROWSER_DATA", Path.home() / ".local/share/drima-browser"
        )
    )
    return directory / "regular-browser.sock"


def read_exact(stream, size):
    result = bytearray()
    while len(result) < size:
        block = stream.read(size - len(result))
        if not block:
            raise EOFError("Native messaging stream closed")
        result.extend(block)
    return bytes(result)


def read_message(stream):
    size = struct.unpack("=I", read_exact(stream, 4))[0]
    if size > MAX_MESSAGE:
        raise ValueError("Native message too large")
    return json.loads(read_exact(stream, size))


def write_message(stream, value):
    encoded = json.dumps(value).encode()
    if len(encoded) > MAX_MESSAGE:
        raise ValueError("Native message too large")
    stream.write(struct.pack("=I", len(encoded)) + encoded)
    stream.flush()


def ensure_private_directory(directory):
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = directory.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise ValueError("Native bridge directory must be owned by user with mode 0700")


def main():
    path = socket_path()
    ensure_private_directory(path.parent)
    # Serialize host processes; never remove another live host's socket.
    lock_fd = os.open(
        path.parent / "regular-browser.lock", os.O_CREAT | os.O_RDWR, 0o600
    )
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("Refusing unexpected socket path")
        path.unlink()
    pending = {}
    pending_lock = threading.Lock()
    alive = threading.Event()
    alive.set()

    def receive():
        try:
            while alive.is_set():
                message = read_message(sys.stdin.buffer)
                with pending_lock:
                    entry = pending.get(message.get("id"))
                    if entry:
                        entry[1].append(message)
                        entry[0].set()
        except (EOFError, ValueError, OSError):
            alive.clear()

    threading.Thread(target=receive, daemon=True).start()
    try:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(path))
            os.chmod(path, 0o600)
            server.listen(4)
            server.settimeout(1)
            while alive.is_set():
                try:
                    client, _ = server.accept()
                except TimeoutError:
                    continue
                with client:
                    client.settimeout(20)
                    try:
                        with client.makefile("rb") as reader:
                            raw = reader.readline(MAX_MESSAGE + 1)
                            if len(raw) > MAX_MESSAGE:
                                raise ValueError("Request too large")
                            request = json.loads(raw)
                            if not isinstance(request, dict):
                                raise ValueError("Request must be an object")
                        request_id = str(uuid4())
                        event, replies = threading.Event(), []
                        with pending_lock:
                            pending[request_id] = (event, replies)
                        try:
                            write_message(
                                sys.stdout.buffer, {**request, "id": request_id}
                            )
                            if not event.wait(15):
                                response = {
                                    "error": "Extension timeout; outcome unknown. Do not repeat mutation."
                                }
                            else:
                                response = replies[0]
                        finally:
                            with pending_lock:
                                pending.pop(request_id, None)
                        client.sendall(json.dumps(response).encode() + b"\n")
                    except (OSError, ValueError, TypeError):
                        try:
                            client.sendall(
                                b'{"error":"Native bridge request failed; outcome unknown"}\n'
                            )
                        except OSError:
                            pass
    finally:
        path.unlink(missing_ok=True)
        os.close(lock_fd)


if __name__ == "__main__":
    main()
