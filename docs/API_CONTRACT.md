# Hợp đồng API

API HTTP không gắn nhãn phiên bản trong path. OpenAPI tương tác có tại `/docs`; schema máy đọc tại `/openapi.json`. Mọi số tiền nghiệp vụ đều là integer minor units kèm currency của run, không dùng `float`.

## Luồng chuẩn

1. `POST /api/demo/datasets` hoặc `POST /api/uploads/inspect` để tạo upload session bất biến và nhận raw EDA/mapping gợi ý.
2. Có thể gọi `POST /api/uploads/{session_id}/preview` nhiều lần để xem kết quả chuẩn hóa giới hạn mà không thay đổi session.
3. `POST /api/uploads/{session_id}/mapping` để xác nhận mapping, chuẩn hóa và chạy Health Gate.
4. Nếu còn lỗi chặn, remap/reupload hoặc `POST /api/uploads/{session_id}/resolutions` với danh sách dòng loại trừ cùng lý do. Warning có thể được ghi nhận bằng `acknowledged_issue_codes` nhưng không bị xóa khỏi audit snapshot.
5. Chỉ session `HEALTH_READY` được gửi tới `POST /api/runs`.
6. Dùng cùng `run_id` và `effective_revision` cho dashboard, explorer và export.

## Endpoints

| Method | Path | Kết quả |
|---|---|---|
| GET | `/healthz` | Readiness của API và PostgreSQL |
| POST | `/api/demo/datasets` | Session từ synthetic VND, chỉ khi `DEMO_MODE=true` |
| POST | `/api/uploads/inspect` | Hai file `orders_file` + `bank_file`, hoặc một `workbook_file` hai sheet |
| POST | `/api/uploads/{session_id}/preview` | Preview canonical giới hạn và lỗi dự kiến; không ghi mapping/health snapshot |
| POST | `/api/uploads/{session_id}/mapping` | Standardized EDA và Health Gate |
| GET | `/api/uploads/{session_id}/normalized/{feed}.csv` | CSV canonical có lineage; chỉ khi session `HEALTH_READY` |
| GET | `/api/uploads/{session_id}/health` | Health snapshot đã lưu |
| GET | `/api/uploads/{session_id}/health/issues/{issue_index}` | Dòng nguồn, giá trị gốc/chuẩn hóa và hướng xử lý của một vấn đề chất lượng |
| POST | `/api/uploads/{session_id}/resolutions` | Exclude có lý do/acknowledge và chạy lại gate |
| GET | `/api/import-profiles` | Danh sách cấu hình nhập liệu đã xác nhận |
| POST | `/api/import-profiles` | Lưu mapping của một upload session theo exact schema fingerprint |
| PATCH | `/api/import-profiles/{profile_id}` | Đổi tên hoặc cập nhật từ session có cùng schema |
| DELETE | `/api/import-profiles/{profile_id}` | Xóa import profile; raw/session/run không bị xóa |
| POST | `/api/runs` | Chạy một snapshot bằng Python Core duy nhất |
| GET | `/api/runs/{run_id}` | Metadata/policy để mở lại run |
| GET | `/api/runs/{run_id}/dashboard` | KPI, analytics, layer counts, payment statuses và conservation |
| GET | `/api/runs/{run_id}/groups` | Nhóm ghép, phân trang; lọc `link_status` |
| GET | `/api/runs/{run_id}/groups/{group_id}` | Nhóm, bản ghi hai phía, allocation edges, bằng chứng và lineage nguồn |
| GET | `/api/runs/{run_id}/orders` | Khoản phải thu + allocated/outstanding/status, phân trang |
| GET | `/api/runs/{run_id}/orders/{order_id}` | Chi tiết quan hệ, nguồn, phân bổ, điều chỉnh và ngoại lệ của một đơn hàng |
| GET | `/api/runs/{run_id}/bank-transactions` | Bank rows + allocated/unapplied, phân trang |
| GET | `/api/runs/{run_id}/bank-transactions/{bank_txn_id}` | Chi tiết quan hệ và truy vết của một giao dịch thanh toán |
| GET | `/api/runs/{run_id}/exceptions` | Exception cases, phân trang |
| GET | `/api/runs/{run_id}/exceptions/{exception_id}` | Chi tiết các bản ghi và bằng chứng liên quan đến một exception |
| GET | `/api/runs/{run_id}/exports?format=xlsx&expected_revision={revision}` | Workbook chín sheet; từ chối 409 nếu dashboard đã cũ |
| GET | `/api/runs/{run_id}/reviews` | Review queue theo effective revision; tìm kiếm, lọc loại quan hệ và phân trang |
| GET | `/api/runs/{run_id}/reviews/history` | Audit approve/reject/undo đã commit, phân trang |
| POST | `/api/runs/{run_id}/reviews/approve` | Chấp thuận proposal hợp lệ và tạo effective revision mới |
| POST | `/api/runs/{run_id}/reviews/reject` | Từ chối proposal, không tạo allocation, và tạo revision mới |
| POST | `/api/runs/{run_id}/reviews/undo` | Hoàn tác action gần nhất khi chưa có revision phụ thuộc |

Ba endpoint review nhận `expected_revision` và `idempotency_key` trong JSON body. Approve/reject nhận `group_id` và bắt buộc có `note` nêu bằng chứng hoặc lý do quyết định; undo nhận `action_id` và note tùy chọn. `actor_label` chỉ là nhãn audit do người dùng nhập trong demo local, không phải danh tính đã xác thực. Một retry có cùng key và cùng payload trả lại cùng `action_id` với `idempotent_replay=true`; cùng key nhưng payload khác bị từ chối.

Các endpoint dashboard, danh sách và detail nhận `revision >= 0` tùy chọn; khi không truyền sẽ đọc revision hiện hành. Các endpoint danh sách nhận `page >= 1`, `1 <= page_size <= 200`; response là `{run_id, effective_revision, items, page, page_size, total}`. Frontend đọc metadata run trước, ghim mọi request dashboard/explorer/detail vào cùng revision, tải 50 bản ghi mỗi lần và luôn tách “đã tải” khỏi tổng số trên server. Dữ liệu lớn không được trả toàn bộ trong một JSON.

## Upload và an toàn

- Cho phép `.csv`, `.xlsx`; tối đa 25 MB/file, 100.000 rows, 200 columns và 20 sheets.
- Reader kiểm tra extension, MIME, magic/ZIP content và uncompressed size; không chạy macro hay công thức.
- Tên file phía client không được dùng làm đường dẫn lưu trữ. Artifact nằm dưới volume root với server-generated UUID và SHA-256.
- Export đặt chuỗi bắt đầu bằng `=`, `+`, `-`, `@` thành text, đồng thời tắt tự động formula/URL của writer. Workbook dùng nhãn tiếng Việt, giữ số tiền ở dạng số, ngày ở dạng ngày, không đưa JSON thô vào ô người dùng.
- Ground truth synthetic không có trong response hoặc runtime input của API.
- Inspection trả `detected_structure`, `mapping_suggestions` và `import_profile`. Điểm mapping là heuristic có lý do, không phải xác suất. Profile lưu chỉ được đánh dấu `applied=true` khi exact fingerprint và schema version khớp.
- Mapping request giữ riêng date format từng feed, transformations, transformation version, cấu hình separator, profile ID/version và các xác nhận mơ hồ. Preview không tự bắt đầu matching; normalized CSV không được tải khi Health Gate còn lỗi chặn.

## Lỗi ổn định

Lỗi nghiệp vụ trả `detail.error_code` và thông điệp tiếng Việt. Các mã chính: `INVALID_UPLOAD` (400), upload quá 25 MB (413), `INVALID_MAPPING`/`INVALID_MAPPING_PREVIEW`/`INVALID_RESOLUTION` (422), `UPLOAD_NOT_FOUND`/`IMPORT_PROFILE_NOT_FOUND`/`RUN_NOT_FOUND`/`GROUP_NOT_FOUND`/`REVIEW_ACTION_NOT_FOUND` (404), `HEALTH_BLOCKED`, `MAPPING_REQUIRED`, `NORMALIZED_EXPORT_NOT_READY`, `IMPORT_PROFILE_CONFLICT`, `IMPORT_PROFILE_SCHEMA_CHANGED`, `STALE_REVISION`, `IDEMPOTENCY_KEY_REUSED`, `ALLOCATION_CONFLICT`, `COMPLEX_GROUP_NOT_APPROVABLE` hoặc `UNDO_DEPENDENCY_CONFLICT` (409), `DATABASE_UNAVAILABLE` (503). Pydantic trả 422 khi DTO sai kiểu hoặc ngoài giới hạn.

## Snapshot và tiền

Một run lưu mapping/policy, input hashes, rule identifier, semantic checksum, canonical Parquet, result JSON, groups, allocation edges và artifact manifest. Revision 0 là kết quả engine; mỗi review đã commit tạo một `RunRevision` bất biến, một `ReviewAction`, snapshot group/edge/adjustment và result artifact riêng. Dashboard và explorer có thể đọc một snapshot bất biến bằng `revision`; export yêu cầu `expected_revision` để không vô tình xuất revision khác màn hình. Analytics xác định rõ mẫu số: tỷ lệ xác nhận dùng toàn bộ relation groups; lag dùng từng cặp allocation đã xác nhận; outstanding và unapplied được trình bày thành hai sổ riêng để tránh cộng trùng. `conservation.is_valid` chỉ đúng khi mọi phương trình bank/order/toàn run không có vi phạm. Proposed groups không tạo allocation và không đi vào confirmed KPI. Điều chỉnh đã xác minh là thành phần phi tiền mặt riêng: `expected = confirmed cash + verified adjustments + outstanding`; không được gộp vào tiền mặt đã nhận.
