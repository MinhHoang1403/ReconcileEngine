# Báo cáo nghiệm thu kỹ thuật

Ngày kiểm tra: 2026-10-15. Môi trường: Windows/PowerShell, Docker Engine 29.7.2, Compose 5.5, Python 3.12 qua `uv`, Node 24.

## Kết quả tự động

| Nhóm | Lệnh | Kết quả |
|---|---|---|
| Python lint | `uv run ruff check .` | Pass |
| Python format | `uv run ruff format --check .` | Pass |
| Python tests | `uv run pytest -q` | 61 passed; một deprecation warning từ FastAPI TestClient |
| Golden | `uv run pytest tests/golden -q` | 26 assertions passed, phủ đúng 22 fixtures F01–F18 và F21–F24 |
| Frontend lint | `npm run lint` | Pass |
| Frontend unit | `npm run test` | 5 passed trong 3 test files |
| Frontend build | `npm run build` | Pass; Plotly basic bundle có cảnh báo chunk lớn, không phải lỗi build |
| Compose | `docker compose config --quiet` | Exit 0 |
| Images | `docker compose up --build -d` | Backend và frontend build sạch, ba services healthy |
| Migration | `docker compose exec -T backend uv run alembic current` | `20261015_02 (head)` |

## Workflow và bảo toàn tiền

API thực qua Nginx đã chạy demo 100 đơn hàng/98 giao dịch thanh toán: EDA dữ liệu gốc → ghép cột → Health `READY` (một warning có audit) → đối soát → dashboard → tra cứu → Excel. Run acceptance `72343e2e-254b-4a06-bc85-bfa220a57aa5` có tiền đã nhận và đối chiếu thành công 66.431.000 VND, điều chỉnh đã xác minh 2.000 VND, còn phải thu 1.432.000 VND, conservation `true` và 0 violations.

Chênh lệch 2.000 VND giữa tổng phải thu và phép cộng tiền mặt/còn phải thu đã được truy vết đến `VerifiedAdjustment` loại `PSP_FEE`, bằng chứng `declared_fee:TXN00016`, đơn `ORD00018`. Phương trình được kiểm tra là `67.865.000 = 66.431.000 + 2.000 + 1.432.000`; phí không bị gộp vào tiền mặt ngân hàng.

Workbook mở lại bằng OpenPyXL và Microsoft Excel, đủ chín sheet theo contract; tổng cột `Số tiền phân bổ` của `05_AllocationEdges` là 66.431.000, bằng dashboard KPI. Không có ô công thức; chuỗi nguồn có tiền tố công thức được lưu thành text. Tiền là numeric cell, ngày là date cell, các bảng có freeze/filter, thông tin file/dòng nguồn và mã liên quan. Verified adjustment 2.000 VND nằm ở cột riêng, không double count. Kiểm tra trực quan bằng Excel xác nhận tiêu đề, chữ tiếng Việt, màu, độ rộng và phương trình KPI đọc được.

## Browser smoke

`scripts/browser_smoke.py` dùng Microsoft Edge headless và Chrome DevTools Protocol để thao tác thật cả bốn màn hình. Đợt nghiệm thu mới chạy ở `1440x900` và `390x844`; cả hai đi hết demo → kiểm tra/ghép cột → xem chi tiết cảnh báo → đối soát → dashboard → xem chi tiết giao dịch → tải thêm 50 lên 100 bản ghi → tải XLSX → tạo phiên mới → mở lại đúng mã phiên. Kết quả: tiền xác nhận `66.431.000 VND`, điều chỉnh `2.000 VND`, conservation hợp lệ, hai biểu đồ, bốn tab, XLSX khoảng 54 KB và không có lỗi console/runtime/network.

Smoke bắt buộc mở warning `POSSIBLE_REIMPORT`, xác minh `bank.csv` và hai dòng nguồn trước khi chỉ ghi nhận cảnh báo. Drawer giao dịch xác minh `ORD00001`, `TXN00001`, hai file nguồn và khoản phân bổ 300.000 VND. Regression API phủ 1:1, N:1, 1:N, partial, overpayment, fuzzy proposal, hai loại orphan và mở lại kết quả đã lưu.

Kiểm tra layout xác nhận `documentElement.scrollWidth <= innerWidth` ở cả hai viewport mới. Font thực tế là system sans (`Segoe UI Variable Text`, `Segoe UI`, Arial), không phát sinh request đến Google Fonts; tiêu đề tiếng Việt hiển thị liền mạch. Ảnh chụp bằng chứng được sinh ngoài repository trong thư mục tạm `smartrecon-ux-final`, gồm nguồn, ghép cột, chất lượng, chi tiết cảnh báo, dashboard và chi tiết giao dịch. Ảnh tổng quan Excel nằm tại file tạm `smartrecon-excel-final-overview.png`.

Các cặp màu chữ chính được đo theo công thức tương phản WCAG: chữ nội dung 16,21:1, chữ phụ 5,23:1, nút thương hiệu 6,47:1 và chữ cảnh báo 6,00:1; đều vượt ngưỡng AA 4,5:1 cho văn bản thường.

Kênh Windows `computer-use` đã được thử trước nhưng môi trường trả `apps: []`, `browsers: []`; vì vậy dùng Edge headless cục bộ làm fallback có thể tái lập. Smoke lần đầu đã phát hiện cột bank amount đọc sai field (0₫); lỗi đã sửa và assertion chống tái phát đã được thêm.

## Persistence sau restart

Đã tạo run/export, kiểm tra DB, chạy `docker compose down` (không `-v`), rồi `docker compose up -d` và mở lại run `4d73464c-68d0-4a36-af21-c04c785470f9`:

- DB trước/sau tại thời điểm kiểm tra: `23 runs, 2.254 match_groups, 2.093 allocation_edges`.
- Tiền xác nhận `66.431.000`, điều chỉnh `2.000`, còn phải thu `1.432.000` không đổi.
- Dashboard và drawer `ORD00018` mở lại, conservation vẫn `true`; export cuối 54.195 bytes tải lại và mở được.
- Sau restart: `db`, `backend`, `frontend` đều healthy; log scan tính từ lúc ba service đã healthy không có `ERROR`, `Traceback`, `FATAL` hoặc `panic`.

Kiểm tra lại sau đợt cải tiến giao diện với run `39f53085-d3e2-4256-b6d9-fce48c3a062a`: trước và sau `docker compose restart`, confirmed cash vẫn là `66.431.000`, conservation vẫn `true`, workbook tải lại đủ 9 sheet và toàn bộ giá trị cell giống nhau. Hash nhị phân XLSX có thể khác vì metadata thời gian khi workbook được tạo lại, nên persistence được đối chiếu theo dữ liệu workbook thay vì checksum file nén.

## Cải tiến giao diện

- Luồng bốn bước dùng nhãn nghiệp vụ chính xác; upload là hành động chính, dữ liệu mẫu và mở lại phiên là lựa chọn phụ.
- EDA hiển thị số dòng/cột/ô trống/trùng lặp; ghép cột tách trường bắt buộc và bổ sung, có giá trị mẫu, phát hiện cột dùng lặp và giữ mã kỹ thuật ở lớp thông tin phụ.
- Kiểm tra chất lượng ưu tiên lỗi theo mức độ; drawer đọc có giới hạn hiển thị file, dòng, giá trị gốc/chuẩn hóa và không tự thay đổi trạng thái cảnh báo.
- Dashboard theo thứ tự Tổng quan → Phân tích → Tra cứu → Xuất báo cáo. Tra cứu hiển thị `đã tải/tổng`, tải từng trang 50 bản ghi và mở drawer nguồn–đối ứng–phân bổ–bằng chứng.
- KPI hiển thị phương trình phải thu với adjustment riêng; biểu đồ cột dùng tên phương pháp nghiệp vụ và tách nhóm đã xác nhận khỏi đề xuất kiểm tra.
- Focus state, semantic headings, labels, table captions, trạng thái bằng chữ và reduced-motion được bổ sung; không dùng màu làm tín hiệu duy nhất.

## Phạm vi và hạn chế đã biết

- Không có approve/reject/undo, concurrent review, auth/RBAC, public HTTPS, external bank API, OCR, FX hoặc queue worker; đây là phạm vi sau, không được triển khai sớm.
- Review queue ở giai đoạn hiện tại chỉ là các proposed groups/candidates có giải thích; chúng không tạo allocation và không đi vào confirmed KPI.
- Frontend Plotly basic bundle còn lớn (~1,48 MB raw, ~487 KB gzip). Đây là tối ưu hiệu năng không chặn demo local; build vẫn pass.
