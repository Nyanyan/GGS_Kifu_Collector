from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from typing import Optional

RawSink = Callable[[str, str], None]

LOGIN_PROMPT_RE = re.compile(
    r"(enter\s+login|login:|name:|username:)",
    re.IGNORECASE,
)
PASSWORD_PROMPT_RE = re.compile(
    r"(enter\s+(?:your\s+)?password|password:|password\s+for)",
    re.IGNORECASE,
)


class GGSClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        logger: logging.Logger,
        raw_sink: RawSink,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.logger = logger
        self.raw_sink = raw_sink

        self.incoming_queue: asyncio.Queue[str] = asyncio.Queue()
        self.status_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.connected_event = asyncio.Event()

        self._stop_event = asyncio.Event()
        self._writer: Optional[asyncio.StreamWriter] = None
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._write_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._reader_task is not None:
            return
        self._reader_task = asyncio.create_task(self._run(), name="ggs-client-runner")

    async def stop(self) -> None:
        self._stop_event.set()
        self.connected_event.clear()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        if self._reader_task:
            await self._reader_task

    async def send_command(self, command: str) -> None:
        await self.connected_event.wait()
        async with self._write_lock:
            writer = self._writer
            if writer is None:
                raise ConnectionError("GGS writer is not ready")
            line = command.rstrip("\r\n")
            writer.write((line + "\n").encode("utf-8"))
            await writer.drain()
            self.raw_sink("SEND", line)

    async def _run(self) -> None:
        backoff = 3
        while not self._stop_event.is_set():
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                self._writer = writer
                await self._login(reader, writer)
                self.connected_event.set()
                await self.status_queue.put(("connected", "ok"))
                self.logger.info("connected to %s:%s", self.host, self.port)
                backoff = 3
                await self._read_loop(reader)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                self.logger.warning("connection loop error: %s", detail)
                await self.status_queue.put(("disconnected", detail))
            finally:
                self.connected_event.clear()
                if self._writer:
                    self._writer.close()
                    try:
                        await self._writer.wait_closed()
                    except Exception:
                        pass
                self._writer = None

            if self._stop_event.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

        await self.status_queue.put(("stopped", "ok"))

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        while not self._stop_event.is_set():
            data = await reader.readline()
            if not data:
                raise ConnectionError("server closed the socket")
            text = data.decode("utf-8", errors="replace").rstrip("\r\n")
            self.raw_sink("RECV", text)
            await self.incoming_queue.put(text)

    async def _login(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        username_sent = False
        password_sent = False
        post_password_chunks = 0
        buffer = ""

        while not self._stop_event.is_set():
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=45)
            except TimeoutError as exc:
                sample = buffer.replace("\r", " ").replace("\n", " ")
                sample = re.sub(r"\s+", " ", sample).strip()[-240:]
                raise TimeoutError(
                    f"login handshake timeout; last prompt fragment={sample!r}"
                ) from exc
            if not data:
                raise ConnectionError("connection closed during login")
            chunk = data.decode("utf-8", errors="replace")
            self.raw_sink("RECV", chunk)
            buffer = (buffer + chunk)[-4096:]
            lower = buffer.lower()

            if not username_sent and LOGIN_PROMPT_RE.search(lower):
                await self._send_sensitive(writer, self.username, sensitive=False)
                username_sent = True
                continue

            if username_sent and not password_sent and PASSWORD_PROMPT_RE.search(lower):
                await self._send_sensitive(writer, self.password, sensitive=True)
                password_sent = True
                continue

            if password_sent:
                post_password_chunks += 1
                # GGS prompt format varies; after password we shift to streaming mode
                # once we have received enough data.
                if post_password_chunks >= 2:
                    break

    async def _send_sensitive(
        self,
        writer: asyncio.StreamWriter,
        content: str,
        *,
        sensitive: bool,
    ) -> None:
        line = content.rstrip("\r\n")
        writer.write((line + "\n").encode("utf-8"))
        await writer.drain()
        if sensitive:
            self.raw_sink("SEND", "***")
        else:
            self.raw_sink("SEND", line)
