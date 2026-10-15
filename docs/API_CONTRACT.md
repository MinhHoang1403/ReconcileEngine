# Hợp đồng API

API HTTP không gắn nhãn phiên bản trong path. OpenAPI tương tác có tại `/docs`; schema máy đọc tại `/openapi.json`. Mọi số tiền nghiệp vụ đều là integer minor units kèm currency của run, không dùng `float`.

## Luồng chuẩn

1. `POST /api/demo/datasets` hoặc `POST /api/uploads/inspect` để tạo upload session bất biến và nhận raw EDA/mapping gợi ý.
2. `POST /api/uploads/{session_id}/mapping` để xác nhận mapping, chuẩn hóa và chạy Health Gate.
3. Nếu còn lỗi chặn, remap/reupload hoặc `POST /api/uploads/{session_id}/resolutions` với danh sách dòng loại trừ cùng lý do. Warning có thể được ghi nhận bằng `acknowledged_issue_codes` nhưng không bị xóa khỏi audit snapshot.
4. Chỉ session `HEALTH_READY` được gửi tới `POST /api/runs`.
5. Dùng cùng `run_id` và `effective_revision` cho dashboard, explorer và export.

## Endpoints

| Method | Path | Kết quả |
|---|---|---|
| GET | `/healthz` | Readiness của API và PostgreSQL |
| POST | `/api/demo/datasets` | Session từ synthetic VND, chỉ khi `DEMO_MODE=true` |
| POST | `/api/uploads/inspect` | Hai file `orders_file` + `bank_file`, hoặc một `workbook_file` hai sheet |
| POST | `/api/uploads/{session_id}/mapping` | Standardized EDA và Health Gate |
| GET | `/api/uploads/{session_id}/health` | Health snapshot đã lưu |
| POST | `/api/uploads/{session_id}/resolutions` | Exclude có lý do/acknowledge và chạy lại gate |
| POST | `/api/runs` | Chạy một snapshot bằng Python Core duy nhất |
| GET | `/api/runs/{run_id}` | Metadata/policy để mở lại run |
| GET | `/api/runs/{run_id}/dashboard` | KPI, layer counts, payment statuses và conservation |
| GET | `/api/runs/{run_id}/groups` | Nhóm ghép, phân trang; lọc `link_status` |
| GET | `/api/runs/{run_id}/groups/{group_id}` | Nhóm và allocation edges |
| GET | `/api/runs/{run_id}/orders` | Khoản phải thu + allocated/outstanding/status, phân trang |
| GET | `/api/runs/{run_id}/bank-transactions` | Bank rows + allocated/unapplied, phân trang |
| GET | `/api/runs/{run_id}/exceptions` | Exception cases, phân trang |
| GET | `/api/runs/{run_id}/exports?format=xlsx` | Workbook chín sheet của effective revision |

Các endpoint danh sách nhận `page >= 1`, `1 <= page_size <= 200`; response là `{items, page, page_size, total}`. Dữ liệu lớn không được trả toàn bộ trong một JSON.

## Upload và an toàn

- Cho phép `.csv`, `.xlsx`; tối đa 25 MB/file, 100.000 rows, 200 columns và 20 sheets.
- Reader kiểm tra extension, MIME, magic/ZIP content và uncompressed size; không chạy macro hay công thức.
- Tên file phía client không được dùng làm đường dẫn lưu trữ. Artifact nằm dưới volume root với server-generated UUID và SHA-256.
- Export đặt chuỗi bắt đầu bằng `=`, `+`, `-`, `@` thành text, đồng thời tắt tự động formula/URL của writer.
- Ground truth synthetic không có trong response hoặc runtime input của API.

## Lỗi ổn định

Lỗi nghiệp vụ trả `detail.error_code` và thông điệp tiếng Việt. Các mã chính: `INVALID_UPLOAD` (400), upload quá 25 MB (413), `INVALID_MAPPING`/`INVALID_RESOLUTION` (422), `UPLOAD_NOT_FOUND`/`RUN_NOT_FOUND`/`GROUP_NOT_FOUND` (404), `HEALTH_BLOCKED` hoặc `MAPPING_REQUIRED` (409), `DATABASE_UNAVAILABLE` (503). Pydantic trả 422 khi DTO sai kiểu hoặc ngoài giới hạn.

## Snapshot và tiền

Một run lưu mapping/policy, input hashes, rule identifier, semantic checksum, canonical Parquet, result JSON, groups, allocation edges và artifact manifest. `conservation.is_valid` chỉ đúng khi mọi phương trình bank/order/toàn run không có vi phạm. Proposed groups không tạo allocation và không đi vào confirmed KPI.
