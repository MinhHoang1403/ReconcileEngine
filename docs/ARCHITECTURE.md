# Kiến trúc SmartRecon

## Storage generation bàn giao 2026-10-21

Cutover được phê duyệt phục hồi backup chính vào PostgreSQL/artifact volumes mới qua `compose.storage.yaml` và `.env` local. Hai volumes cũ giữ rollback; không đưa dữ liệu Lab vào chính. Stack và ranh giới pure core/backend/frontend không đổi, không thêm microservice/cache/model runtime. Xem DEPLOYMENT/ACCEPTANCE_REPORT về đối chiếu dữ liệu và rollback trước/sau ghi mới.

SmartRecon chạy bằng Docker Compose với ba service chạy dài hạn: React/Vite `frontend`, FastAPI `backend`, PostgreSQL `db`, cùng job one-shot `migrate`. PostgreSQL dùng named volume `pg_data`; file upload, snapshot và export dùng `artifacts_data`. Cổng PostgreSQL không được publish ra host.

Python core nằm trong `src/smartrecon`, không phụ thuộc HTTP hay persistence. Backend chịu trách nhiệm orchestration, validation, transaction metadata và artifact lifecycle. DuckDB là thư viện phân tích nhúng trong tiến trình backend, không phải service hoặc transaction store.

Backend chỉ chạy một worker trong demo local. Job `migrate` chờ PostgreSQL healthy, chạy Alembic đúng một lần rồi thoát; backend chờ job này thành công và chỉ chạy Uvicorn. Cấu trúc này tránh để mỗi backend replica tự chạy migration. Frontend chỉ lấy dữ liệu qua API; mọi phép tính tiền và trạng thái nghiệp vụ thuộc core/backend.

PostgreSQL lưu upload sessions, runs, revisions, groups, allocation edges và artifact manifests. Raw/canonical/result files nằm trên artifact volume với relative path và SHA-256 trong database. Một dashboard/export phải đọc cùng `run_id` và effective revision.

Các giới hạn hiện tại: chưa có xác thực/RBAC để public trực tiếp lên Internet, không có job queue và chưa có HA database. Review/undo có optimistic concurrency, immutable revision và audit record nhưng `actor_label` chưa phải danh tính đã xác thực.
