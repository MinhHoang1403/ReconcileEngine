"""Exercise SmartRecon in headless Edge and collect UI evidence."""

from __future__ import annotations

import argparse
import base64
import json
import re
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
            "Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True}
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
    body = devtools.evaluate("document.body?.innerText?.slice(0, 1500)")
    raise TimeoutError(f"Browser condition timeout: {expression}\n{body}")


def click_button(devtools: DevTools, text: str) -> None:
    encoded = json.dumps(text, ensure_ascii=False)
    clicked = devtools.evaluate(
        "(() => { const label = "
        + encoded
        + "; const button = [...document.querySelectorAll('button')].find((item) => item.textContent.includes(label)); "
        "if (!button || button.disabled) return false; button.click(); return true; })()"
    )
    if not clicked:
        raise RuntimeError(f"Không click được button: {text}")


def capture(devtools: DevTools, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    captured = devtools.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    path.write_bytes(base64.b64decode(captured["data"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--screenshot-dir", type=Path)
    parser.add_argument("--all-stages", action="store_true")
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
            f"--window-size={args.width},{args.height}",
            args.url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    devtools: DevTools | None = None
    screenshots: list[str] = []
    suffix = f"{args.width}x{args.height}"

    def stage_path(stage: str) -> Path | None:
        if not args.screenshot_dir or (not args.all_stages and stage != "source"):
            return None
        path = args.screenshot_dir / f"{stage}-{suffix}.png"
        screenshots.append(str(path))
        return path

    try:
        tab = wait_for_tab(port)
        devtools = DevTools(tab["webSocketDebuggerUrl"])
        for domain in ("Page", "Runtime", "Network", "Log"):
            devtools.command(f"{domain}.enable")
        devtools.command(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": args.width,
                "height": args.height,
                "deviceScaleFactor": 1,
                "mobile": args.width <= 768,
            },
        )
        devtools.command("Page.reload", {"ignoreCache": True})
        wait_until(
            devtools, "document.readyState === 'complete' && document.body.innerText.includes('Hệ thống sẵn sàng')"
        )
        capture(devtools, stage_path("source"))
        source_evidence = devtools.evaluate(
            "({heading: document.querySelector('h1')?.textContent, width: innerWidth, height: innerHeight, "
            "scrollWidth: document.documentElement.scrollWidth, font: getComputedStyle(document.body).fontFamily, "
            "externalFonts: performance.getEntriesByType('resource')"
            ".filter(x => /fonts\\.(googleapis|gstatic)/.test(x.name)).length})"
        )
        assert source_evidence["heading"] == "Đối soát giao dịch tài chính"
        assert source_evidence["scrollWidth"] <= source_evidence["width"]
        assert source_evidence["externalFonts"] == 0

        click_button(devtools, "Sử dụng dữ liệu mẫu")
        wait_until(devtools, "document.body.innerText.includes('Kiểm tra và chuẩn hóa dữ liệu')")
        capture(devtools, stage_path("mapping"))
        click_button(devtools, "Chuẩn hóa dữ liệu")
        wait_until(devtools, "document.body.innerText.includes('Dữ liệu sẵn sàng đối soát')")
        capture(devtools, stage_path("health"))
        click_button(devtools, "Xem dòng dữ liệu liên quan")
        wait_until(devtools, "document.body.innerText.includes('Chi tiết vấn đề dữ liệu')")
        capture(devtools, stage_path("health-detail"))
        health_detail = devtools.evaluate(
            "({rows: document.querySelectorAll('.source-record').length, "
            "hasSource: document.body.innerText.includes('bank.csv')})"
        )
        assert health_detail["rows"] >= 1
        assert health_detail["hasSource"] is True
        devtools.evaluate("document.querySelector('[aria-label=\"Đóng chi tiết\"]')?.click()")
        click_button(devtools, "Ghi nhận cảnh báo")
        wait_until(devtools, "document.body.innerText.includes('Đã ghi nhận cảnh báo')")
        click_button(devtools, "Chạy đối soát")
        wait_until(devtools, "document.body.innerText.includes('Kết quả đối soát')", timeout=90)
        capture(devtools, stage_path("dashboard"))

        evidence = devtools.evaluate(
            "({title: document.title, conservation: "
            "document.body.innerText.includes('Bảo toàn tiền đã được xác minh'), "
            "kpiBaseline: document.body.innerText.includes('66.431.000'), "
            "exportHref: document.querySelector('a[href*=\"exports?format=xlsx\"]')?.getAttribute('href'), "
            "charts: document.querySelectorAll('.js-plotly-plot').length, "
            "tabs: document.querySelectorAll('[role=tab]').length, "
            "adjustmentBridge: document.body.innerText.includes('2.000') && "
            "document.body.innerText.includes('điều chỉnh đã xác minh'), "
            "pagination: document.body.innerText.includes('Đã tải 50 / tổng 100'), "
            "runLabel: [...document.querySelectorAll('.eyebrow')].map(x => x.textContent)"
            ".find(x => x.startsWith('MÃ PHIÊN ')), "
            "width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth})"
        )
        assert evidence["conservation"] is True
        assert evidence["kpiBaseline"] is True
        assert evidence["charts"] == 2
        assert evidence["tabs"] == 4
        assert evidence["adjustmentBridge"] is True
        assert evidence["pagination"] is True
        assert evidence["scrollWidth"] <= evidence["width"]
        assert evidence["exportHref"]
        run_id_match = re.search(r"/api/runs/([^/]+)/exports", evidence["exportHref"])
        assert run_id_match
        run_id = run_id_match.group(1)

        click_button(devtools, "ORD00001")
        wait_until(devtools, "document.body.innerText.includes('Chi tiết đối chiếu')")
        capture(devtools, stage_path("transaction-detail"))
        detail_evidence = devtools.evaluate(
            "({hasSource: document.body.innerText.includes('orders.csv') && "
            "document.body.innerText.includes('bank.csv'), "
            "hasAllocation: document.body.innerText.includes('Phân bổ tiền đã xác nhận')})"
        )
        assert detail_evidence["hasSource"] is True
        assert detail_evidence["hasAllocation"] is True
        devtools.evaluate("document.querySelector('[aria-label=\"Đóng chi tiết\"]')?.click()")
        click_button(devtools, "Tải thêm")
        wait_until(devtools, "document.body.innerText.includes('Đã tải 100 / tổng 100')")

        export_evidence = devtools.evaluate(
            "(async () => { const r = await fetch(document.querySelector('a[href*=\"exports?format=xlsx\"]')?.href); "
            "const b = await r.arrayBuffer(); return {status: r.status, "
            "type: r.headers.get('content-type'), bytes: b.byteLength}; })()"
        )
        assert export_evidence["status"] == 200
        assert export_evidence["bytes"] > 1000

        click_button(devtools, "Tạo phiên mới")
        wait_until(devtools, "document.body.innerText.includes('Đối soát giao dịch tài chính')")
        encoded_run_id = json.dumps(run_id)
        set_value = devtools.evaluate(
            "(() => { const input = document.querySelector('#run-id'); if (!input) return false; "
            "const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; "
            f"setter.call(input, {encoded_run_id}); "
            "input.dispatchEvent(new Event('input', {bubbles:true})); return true; })()"
        )
        assert set_value is True
        click_button(devtools, "Mở phiên")
        wait_until(devtools, "document.body.innerText.includes('Kết quả đối soát')", timeout=45)
        reopened_href = devtools.evaluate(
            "document.querySelector('a[href*=\"exports?format=xlsx\"]')?.getAttribute('href')"
        )
        assert run_id in reopened_href

        if devtools.failures:
            raise AssertionError(f"Browser errors: {devtools.failures}")
        evidence.update(
            {
                "run_id": run_id,
                "export": export_evidence,
                "reopen_verified": True,
                "source": source_evidence,
                "screenshots": screenshots,
            }
        )
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
