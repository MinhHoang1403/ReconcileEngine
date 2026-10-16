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

Backend host cần một `DATABASE_URL` PostgreSQL phù hợp. Trong Compose, job one-shot `migrate` chạy migration trước khi backend khởi động; trên host có thể chạy có kiểm soát bằng `uv run alembic upgrade head`.

## Luồng giao diện

Website tổ chức quy trình thành bốn bước: chọn nguồn dữ liệu; kiểm tra và ánh xạ; kiểm tra chất lượng và chạy đối soát; xem kết quả và xuất báo cáo. Dashboard sắp xếp theo Tổng quan → Phân tích → Giao dịch cần xác minh → Tra cứu → Xuất báo cáo. Review queue cho phép xem allocation preview và bằng chứng nguồn trước khi approve/reject; undo chỉ khả dụng khi chưa có revision phụ thuộc. Tìm kiếm và bộ lọc chỉ áp dụng trên phần dữ liệu đã tải; nút “Tải thêm” lấy trang kế tiếp và giao diện luôn hiển thị riêng số đã tải/tổng số trên server. Chọn mã giao dịch để xem hai phía đối chiếu, phân bổ, bằng chứng và dòng dữ liệu nguồn.

KPI tiền giữ riêng ba thành phần: tiền đã nhận và đối chiếu thành công, điều chỉnh đã xác minh và số còn phải thu. Dashboard bổ sung thống kê review, tỷ lệ xác nhận có mẫu số rõ ràng, loại quan hệ, ngoại lệ, residual và độ trễ trên cùng effective revision. Báo cáo Excel có chín trang tính với nhãn tiếng Việt, định dạng tiền/ngày, lịch sử review thực, trạng thái nhóm, bộ lọc và thông tin truy vết nguồn.

Kiểm tra workflow thật bằng Edge headless, bao gồm approve/undo, export và mở lại phiên đã lưu:

```powershell
uv run python scripts/browser_smoke.py --width 1440 --height 900
uv run python scripts/browser_smoke.py --width 390 --height 844
```

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

## Notebook và đánh giá

Notebook nghiên cứu dùng trực tiếp cùng public core API với backend, không cần website đang chạy:

```powershell
uv sync --extra dev
uv run pytest tests/research/test_research_notebook.py -q
uv run python scripts/run_evaluation.py --orders 1000 --seed 20261016 --output reports/evaluation_results.json
```

Mở `notebooks/reconciliation_research.ipynb` để xem EDA, Waterfall L1–L4, conservation, holdout metrics, ablation và hard-profile benchmark. Ground truth chỉ được evaluator đọc sau khi engine chạy. Kết quả, giới hạn và cách diễn giải chỉ số nằm trong `docs/EVALUATION_REPORT.md`.

Với Docker stack đang healthy, có thể chạy acceptance PostgreSQL và benchmark tình huống:

```powershell
uv run python scripts/qa_concurrency.py --output reports/qa_concurrency.json
uv run python scripts/run_qa_benchmark.py --repeats 25 --output reports/qa_benchmark.json
uv run python scripts/browser_smoke.py --width 390 --height 844
```

Hai file JSON trong `reports/` là runtime evidence theo máy và không được commit; kết quả kiểm chứng đã được ghi tại `docs/QA_REPORT.md`.

## Tài liệu vận hành và nghiệm thu

- `docs/API_CONTRACT.md`: endpoints, DTO, mã lỗi, pagination và an toàn upload/export.
- `docs/OPERATIONS.md`: hướng dẫn Windows/PowerShell, Docker Desktop/WSL2, restart và chẩn đoán.
- `docs/DEPLOYMENT.md`: cấu hình production, migration one-shot, Linux/HTTPS, backup và restore drill độc lập.
- `docs/EVALUATION_REPORT.md`: protocol, Precision/Recall/F1, ablation, benchmark và giới hạn.
- `docs/QA_REPORT.md`: lệnh và bằng chứng test/Docker/browser/persistence đã chạy thực tế.
