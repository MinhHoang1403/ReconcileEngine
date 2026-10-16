# Vận hành local

## Yêu cầu Windows

- Windows 10/11, Docker Desktop dùng Linux containers và WSL2 backend.
- Docker Engine/Compose đang chạy; Node 24 và `uv` chỉ cần khi phát triển trên host.
- Các cổng host cần trống: `5173` cho website và `8000` cho API. PostgreSQL chỉ ở Docker network, không publish cổng `5432`.

## Khởi động

```powershell
Set-Location C:\Work\ReconcileEngine
Copy-Item .env.example .env   # chỉ lần đầu; không commit .env
docker compose config
docker compose up --build -d
docker compose ps
```

Job one-shot `migrate` chờ PostgreSQL healthy và chạy `alembic upgrade head`; backend chỉ khởi động API sau khi job hoàn tất thành công. Frontend là static build phục vụ bởi Nginx và reverse proxy `/api`, `/healthz` tới backend.

- Website: `http://localhost:5173`
- API health: `http://localhost:8000/healthz`
- OpenAPI: `http://localhost:8000/docs`

Trong website, chọn demo VND hoặc upload hai feed, xác nhận mapping, xử lý Health Gate, chạy đối soát và tải Excel. Có thể dán `run_id` tại trang đầu để mở lại snapshot.

Review API yêu cầu client gửi `expected_revision` hiện đang hiển thị và một `idempotency_key` duy nhất cho thao tác. Khi nhận `STALE_REVISION`, client phải tải lại run/review queue trước khi thử quyết định mới. Retry do mất kết nối phải giữ nguyên cả key lẫn payload. Không sửa trực tiếp bảng revision/action hoặc result artifact trong volume.

## Kiểm tra và chẩn đoán

```powershell
docker compose ps
docker compose ps -a
docker compose run --rm migrate uv run alembic current
docker compose logs --tail 200 backend db frontend
Invoke-RestMethod http://localhost:8000/healthz
```

Browser smoke local dùng Microsoft Edge đã cài sẵn, không tải browser hoặc thêm test framework:

```powershell
uv run python scripts/browser_smoke.py --screenshot "$env:TEMP\smartrecon-browser-smoke.png"
```

Script thao tác demo → mapping → Health → run → dashboard trong browser headless, kiểm tra conservation, hai charts, bốn explorer tables, bank amount và link export.

## Dừng, khởi động lại và persistence

```powershell
docker compose down
docker compose up -d
```

Hai named volumes `pg_data` và `artifacts_data` giữ PostgreSQL cùng raw/result/Parquet/export artifacts. `docker compose down` không xóa chúng. **Không chạy `docker compose down -v`** nếu muốn giữ dữ liệu. Không sửa trực tiếp file trong volume; dùng API/run ID để đọc snapshot.

Để xác minh sau restart, gọi lại:

```powershell
$runId = '<run-id-da-luu>'
Invoke-RestMethod "http://localhost:8000/api/runs/$runId"
Invoke-RestMethod "http://localhost:8000/api/runs/$runId/dashboard"
Invoke-WebRequest "http://localhost:8000/api/runs/$runId/exports?format=xlsx" -OutFile report.xlsx
```

## Kiểm tra phát triển

```powershell
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest -q

Set-Location frontend
npm ci
npm run lint
npm test -- --run
npm run build
npm audit
```

Không đặt secret thật trong `.env.example`, commit `.env`, hoặc publish PostgreSQL ra host/public network.

Triển khai production, backup cả database/artifacts và restore drill độc lập được hướng dẫn tại `docs/DEPLOYMENT.md`.
