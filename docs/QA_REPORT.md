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
| Frontend unit | `npm run test` | 5 passed trong 3 test files |
| Frontend build | `npm run build` | Pass; Plotly basic bundle có cảnh báo chunk lớn, không phải lỗi build |
| Compose | `docker compose config --quiet` | Exit 0 |
| Images | `docker compose up --build -d` | Backend và frontend build sạch, ba services healthy |
| Migration | `docker compose exec -T backend uv run alembic current` | `20261015_02 (head)` |

## Workflow và bảo toàn tiền

API thực qua Nginx đã chạy demo 100 orders/98 bank rows: raw EDA → mapping → Health `READY` (một warning có audit) → run → dashboard → explorer → Excel. Run acceptance `d450f6b2-aeb0-4d57-8b23-2f0198c13f37` có semantic checksum `f3bd243a850d7dac55f5b544679d9c96eb98cd30925dcd010945c24f5baeffd8`, confirmed cash 66.431.000 VND, conservation `true` và 0 violations.

Workbook mở lại bằng OpenPyXL, đủ chín sheet theo contract; tổng `05_AllocationEdges.allocated_cash_minor` là 66.431.000, bằng dashboard KPI. Không có cell kiểu formula; user-origin formula prefix được lưu thành text. Sheets Orders/Bank có allocated và outstanding/unapplied.

## Browser smoke

`scripts/browser_smoke.py` dùng Microsoft Edge headless và Chrome DevTools Protocol để thao tác thật cả bốn màn hình. Script chạy ở `1440x900`, `1366x768`, `768x1024` và `390x844`; mỗi lần đều đi hết demo → khám phá/ánh xạ → Health Gate → đối soát → dashboard → tải XLSX → tạo phiên mới → mở lại đúng Run ID. Kết quả: confirmed cash `66.431.000 VND`, conservation hợp lệ, hai Plotly charts, bốn tab explorer, XLSX khoảng 46 KB và không có lỗi console/runtime/network.

Smoke cũng bắt buộc ghi nhận warning `POSSIBLE_REIMPORT` và chờ giao diện phản hồi `Đã ghi nhận cảnh báo` trước khi chạy engine. Regression API xác nhận mapping snapshot được kiểm tra lại qua schema khi đọc từ PostgreSQL, tránh lỗi kiểu dữ liệu currency mà không thay đổi API contract.

Kiểm tra layout xác nhận `documentElement.scrollWidth <= innerWidth` ở cả bốn viewport. Font thực tế là system sans (`Segoe UI Variable Text`, `Segoe UI`, Arial), không phát sinh request đến Google Fonts; tiêu đề tiếng Việt hiển thị liền mạch. Ảnh chụp bằng chứng được sinh ngoài repository trong thư mục tạm `smartrecon-redesign-after` để không đưa artifact runtime vào Git.

Các cặp màu chữ chính được đo theo công thức tương phản WCAG: chữ nội dung 16,21:1, chữ phụ 5,23:1, nút thương hiệu 6,47:1 và chữ cảnh báo 6,00:1; đều vượt ngưỡng AA 4,5:1 cho văn bản thường.

Kênh Windows `computer-use` đã được thử trước nhưng môi trường trả `apps: []`, `browsers: []`; vì vậy dùng Edge headless cục bộ làm fallback có thể tái lập. Smoke lần đầu đã phát hiện cột bank amount đọc sai field (0₫); lỗi đã sửa và assertion chống tái phát đã được thêm.

## Persistence sau restart

Đã tạo run/export, kiểm tra DB, chạy `docker compose down` (không `-v`), xác nhận file result và XLSX còn trong read-only artifacts volume, rồi `docker compose up -d`:

- DB trước/sau: `1 run, 98 match_groups, 91 allocation_edges`.
- Semantic checksum và confirmed cash không đổi.
- Dashboard mở lại, conservation vẫn `true`; export tải lại và mở được.
- Sau restart: `db`, `backend`, `frontend` đều healthy; log scan không có `ERROR`, `Traceback`, `FATAL` hoặc `panic`.

Kiểm tra lại sau đợt cải tiến giao diện với run `39f53085-d3e2-4256-b6d9-fce48c3a062a`: trước và sau `docker compose restart`, confirmed cash vẫn là `66.431.000`, conservation vẫn `true`, workbook tải lại đủ 9 sheet và toàn bộ giá trị cell giống nhau. Hash nhị phân XLSX có thể khác vì metadata thời gian khi workbook được tạo lại, nên persistence được đối chiếu theo dữ liệu workbook thay vì checksum file nén.

## Cải tiến giao diện

- Luồng bốn bước dùng nhãn nghiệp vụ chính xác; upload là hành động chính, dữ liệu mẫu và mở lại phiên là lựa chọn phụ.
- EDA hiển thị số dòng/cột/ô trống/trùng lặp; mapping tách trường bắt buộc và bổ sung, giữ mã kỹ thuật ở lớp thông tin phụ.
- Health Gate ưu tiên lỗi theo mức độ, hiển thị mã kỹ thuật trong phần mở rộng và thu lý do loại trừ ngay trong màn hình.
- Dashboard theo thứ tự Tổng quan → Phân tích → Tra cứu → Xuất báo cáo. Explorer tìm kiếm/lọc trong đúng trang API đã tải, không thay đổi pagination hay KPI backend.
- Focus state, semantic headings, labels, table captions, trạng thái bằng chữ và reduced-motion được bổ sung; không dùng màu làm tín hiệu duy nhất.

## Phạm vi và hạn chế đã biết

- Không có approve/reject/undo, concurrent review, auth/RBAC, public HTTPS, external bank API, OCR, FX hoặc queue worker; đây là phạm vi sau, không được triển khai sớm.
- Review queue ở giai đoạn hiện tại chỉ là các proposed groups/candidates có giải thích; chúng không tạo allocation và không đi vào confirmed KPI.
- Frontend Plotly basic bundle còn lớn (~1,48 MB raw, ~487 KB gzip). Đây là tối ưu hiệu năng không chặn demo local; build vẫn pass.
