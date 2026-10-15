# Báo cáo nghiệm thu kỹ thuật

Ngày kiểm tra: 2026-10-15. Môi trường: Windows/PowerShell, Docker Engine 29.7.2, Compose 5.5, Python 3.12 qua `uv`, Node 24.

## Kết quả tự động

| Nhóm | Lệnh | Kết quả |
|---|---|---|
| Python lint | `uv run ruff check .` | Pass |
| Python format | `uv run ruff format --check .` | Pass |
| Python tests | `uv run pytest -q` | 58 passed; một deprecation warning từ FastAPI TestClient |
| Golden | `uv run pytest tests/golden -q` | 26 assertions passed, phủ đúng 22 fixtures F01–F18 và F21–F24 |
| Frontend lint | `npm run lint` | Pass |
| Frontend unit | `npm test -- --run` | 1 passed |
| Frontend build | `npm run build` | Pass; Plotly basic bundle có cảnh báo chunk lớn, không phải lỗi build |
| Compose | `docker compose config --quiet` | Exit 0 |
| Images | `docker compose up --build -d` | Backend và frontend build sạch, ba services healthy |
| Migration | `docker compose exec -T backend uv run alembic current` | `20261015_02 (head)` |

## Workflow và bảo toàn tiền

API thực qua Nginx đã chạy demo 100 orders/98 bank rows: raw EDA → mapping → Health `READY` (một warning có audit) → run → dashboard → explorer → Excel. Run acceptance `d450f6b2-aeb0-4d57-8b23-2f0198c13f37` có semantic checksum `f3bd243a850d7dac55f5b544679d9c96eb98cd30925dcd010945c24f5baeffd8`, confirmed cash 66.431.000 VND, conservation `true` và 0 violations.

Workbook mở lại bằng OpenPyXL, đủ chín sheet theo contract; tổng `05_AllocationEdges.allocated_cash_minor` là 66.431.000, bằng dashboard KPI. Không có cell kiểu formula; user-origin formula prefix được lưu thành text. Sheets Orders/Bank có allocated và outstanding/unapplied.

## Browser smoke

`scripts/browser_smoke.py` dùng Microsoft Edge headless và Chrome DevTools Protocol để thao tác thật cả bốn màn hình. Kết quả cuối: title `SmartRecon`, conservation hiển thị hợp lệ, hai Plotly charts, bốn tables, export link tồn tại và bank amount đầu là `300.000 ₫`. Browser console/runtime/network không có lỗi.

Kênh Windows `computer-use` đã được thử trước nhưng môi trường trả `apps: []`, `browsers: []`; vì vậy dùng Edge headless cục bộ làm fallback có thể tái lập. Smoke lần đầu đã phát hiện cột bank amount đọc sai field (0₫); lỗi đã sửa và assertion chống tái phát đã được thêm.

## Persistence sau restart

Đã tạo run/export, kiểm tra DB, chạy `docker compose down` (không `-v`), xác nhận file result và XLSX còn trong read-only artifacts volume, rồi `docker compose up -d`:

- DB trước/sau: `1 run, 98 match_groups, 91 allocation_edges`.
- Semantic checksum và confirmed cash không đổi.
- Dashboard mở lại, conservation vẫn `true`; export tải lại và mở được.
- Sau restart: `db`, `backend`, `frontend` đều healthy; log scan không có `ERROR`, `Traceback`, `FATAL` hoặc `panic`.

## Phạm vi và hạn chế đã biết

- Không có approve/reject/undo, concurrent review, auth/RBAC, public HTTPS, external bank API, OCR, FX hoặc queue worker; đây là phạm vi sau, không được triển khai sớm.
- Review queue ở giai đoạn hiện tại chỉ là các proposed groups/candidates có giải thích; chúng không tạo allocation và không đi vào confirmed KPI.
- Frontend Plotly basic bundle còn lớn (~1,48 MB raw, ~487 KB gzip). Đây là tối ưu hiệu năng không chặn demo local; build vẫn pass.
