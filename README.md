# SmartRecon

SmartRecon là ứng dụng đối soát hai nguồn: khoản phải thu nội bộ và giao dịch ghi có ngân hàng/PSP. Hệ thống ưu tiên bảo toàn tiền, tránh tự ghép khi thiếu bằng chứng, và lưu dấu vết cho từng kết quả.

## Khởi động bằng Docker Desktop

Yêu cầu: Docker Desktop/Engine có Compose. PostgreSQL không được publish ra host.

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Mở `http://localhost:5173`; API health ở `http://localhost:8000/healthz`. Lệnh dừng an toàn, vẫn giữ database và artifacts:

```powershell
docker compose down
```

Không chạy `docker compose down -v` nếu cần giữ dữ liệu. File `.env` chỉ dùng local và đã được loại khỏi Git.

## Phát triển trên host

Python chuẩn của dự án là 3.12 và dependencies được quản lý bằng `uv`:

```powershell
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest -q

Set-Location frontend
npm ci
npm run lint
npm test
npm run build
```

Backend host cần một `DATABASE_URL` PostgreSQL phù hợp. Migration được chạy tự động khi container backend khởi động; có thể kiểm tra thủ công bằng `uv run alembic upgrade head`.

## Nguyên tắc dữ liệu

- Một run chỉ có một currency, tiền được tính bằng integer minor units sau khi parse `Decimal`.
- Ground truth của dữ liệu synthetic không đi vào API upload hoặc matching runtime.
- Candidate fuzzy/amount/date không tự trở thành confirmed allocation.
- Raw input và các snapshot cấu hình có hash/lineage; artifacts được lưu ngoài writable layer của container.

Chi tiết kiến trúc và hợp đồng nghiệp vụ nằm trong `docs/`.

Luồng API và mã lỗi được mô tả tại `docs/API_CONTRACT.md`. Giao diện cho phép dán một `run_id` để mở lại dashboard và export từ PostgreSQL/artifact volume sau khi container khởi động lại.

## Sinh lại dữ liệu demo

Bộ VND gồm 100 khoản phải thu và feed bank/PSP synthetic. Truth được ghi ra file riêng, không nằm trong hai feed nghiệp vụ:

```powershell
uv run python scripts/generate_demo.py --seed 42 --orders 100
```

Xem provenance và giới hạn sử dụng Olist trong `docs/DATA_ATTRIBUTION.md`.

## Tài liệu vận hành và nghiệm thu

- `docs/API_CONTRACT.md`: endpoints, DTO, mã lỗi, pagination và an toàn upload/export.
- `docs/OPERATIONS.md`: hướng dẫn Windows/PowerShell, Docker Desktop/WSL2, restart và chẩn đoán.
- `docs/QA_REPORT.md`: lệnh và bằng chứng test/Docker/browser/persistence đã chạy thực tế.
