"""Drive the local SmartRecon workflow through Edge's DevTools protocol."""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from websockets.sync.client import connect

EDGE_PATHS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


class DevTools:
    def __init__(self, websocket_url: str) -> None:
        self.socket = connect(websocket_url, max_size=20 * 1024 * 1024, legacy=True)
        self.next_id = 1
        self.failures: list[str] = []

    def command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"CDP {method}: {message['error']}")
                return message.get("result", {})
            self._record_event(message)

    def _record_event(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params", {})
        if method == "Runtime.exceptionThrown":
            self.failures.append(f"runtime: {params.get('exceptionDetails', {}).get('text')}")
        elif method == "Log.entryAdded" and params.get("entry", {}).get("level") == "error":
            self.failures.append(f"console: {params['entry'].get('text')}")
        elif method == "Network.loadingFailed" and not params.get("canceled"):
            self.failures.append(f"network: {params.get('errorText')}")

    def evaluate(self, expression: str) -> Any:
        result = self.command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("text", "Browser expression failed"))
        return result.get("result", {}).get("value")

    def close(self) -> None:
        self.socket.close()


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def find_edge() -> Path:
    for path in EDGE_PATHS:
        if path.is_file():
            return path
    raise FileNotFoundError("Microsoft Edge không được cài ở đường dẫn chuẩn")


def wait_for_tab(port: int, timeout: float = 20) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                tabs = json.load(response)
            tab = next((item for item in tabs if item.get("type") == "page"), None)
            if tab:
                return tab
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    raise TimeoutError("Không kết nối được Edge DevTools")


def wait_until(devtools: DevTools, expression: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if devtools.evaluate(expression):
            return
        time.sleep(0.2)
    body = devtools.evaluate("document.body?.innerText?.slice(0, 1200)")
    raise TimeoutError(f"Browser condition timeout: {expression}\n{body}")


def click_button(devtools: DevTools, text: str) -> None:
    encoded = json.dumps(text, ensure_ascii=False)
    clicked = devtools.evaluate(
        "(() => { const label = "
        + encoded
        + "; const button = [...document.querySelectorAll('button')].find((item) => "
        "item.textContent.includes(label)); if (!button || button.disabled) return false; "
        "button.click(); return true; })()"
    )
    if not clicked:
        raise RuntimeError(f"Không click được button: {text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="smartrecon-browser-"))
    process = subprocess.Popen(
        [
            str(find_edge()),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--window-size=1440,1100",
            args.url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    devtools: DevTools | None = None
    try:
        tab = wait_for_tab(port)
        devtools = DevTools(tab["webSocketDebuggerUrl"])
        for domain in ("Page", "Runtime", "Network", "Log"):
            devtools.command(f"{domain}.enable")
        wait_until(
            devtools, "document.readyState === 'complete' && document.body.innerText.includes('Hệ thống sẵn sàng')"
        )
        click_button(devtools, "Chạy dữ liệu demo VND")
        wait_until(devtools, "document.body.innerText.includes('Xác nhận ý nghĩa từng cột')")
        click_button(devtools, "Xác nhận mapping")
        wait_until(devtools, "document.body.innerText.includes('Dữ liệu sẵn sàng đối soát')")
        click_button(devtools, "Chạy đối soát")
        wait_until(devtools, "document.body.innerText.includes('Kết quả đối soát')", timeout=90)

        evidence = devtools.evaluate(
            "({"
            "title: document.title,"
            "conservation: document.body.innerText.includes('Bất biến bảo toàn tiền đã kiểm tra'),"
            "export_link: Boolean(document.querySelector('a[href*=\"exports?format=xlsx\"]')),"
            "tables: document.querySelectorAll('table').length,"
            "charts: document.querySelectorAll('.js-plotly-plot').length,"
            "first_bank_amount: [...document.querySelectorAll('.data-card')].find(x => "
            "x.innerText.includes('Giao dịch ngân hàng'))?.querySelector('tbody tr td:nth-child(2)')?.innerText,"
            "run_label: [...document.querySelectorAll('.eyebrow')].map(x => x.textContent)"
            ".find(x => x.startsWith('RUN '))"
            "})"
        )
        assert evidence["conservation"] is True
        assert evidence["export_link"] is True
        assert evidence["tables"] >= 4
        assert evidence["charts"] == 2
        assert evidence["first_bank_amount"] not in {None, "0 ₫"}
        if devtools.failures:
            raise AssertionError(f"Browser errors: {devtools.failures}")
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            captured = devtools.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            args.screenshot.write_bytes(base64.b64decode(captured["data"]))
            evidence["screenshot"] = str(args.screenshot)
        print(json.dumps(evidence, ensure_ascii=False))
    finally:
        if devtools:
            devtools.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
