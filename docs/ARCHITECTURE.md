# Kiến trúc SmartRecon

SmartRecon chạy bằng Docker Compose với đúng ba service: React/Vite `frontend`, FastAPI `backend`, và PostgreSQL `db`. PostgreSQL dùng named volume `pg_data`; file upload, snapshot và export dùng `artifacts_data`. Cổng PostgreSQL không được publish ra host.

Python core nằm trong `src/smartrecon`, không phụ thuộc HTTP hay persistence. Backend chịu trách nhiệm orchestration, validation, transaction metadata và artifact lifecycle. DuckDB là thư viện phân tích nhúng trong tiến trình backend, không phải service hoặc transaction store.

Backend chỉ chạy một worker trong demo local. Khi khởi động, backend chờ healthcheck PostgreSQL rồi chạy Alembic trước Uvicorn, tránh tạo schema đồng thời. Frontend chỉ lấy dữ liệu qua API; mọi phép tính tiền và trạng thái nghiệp vụ thuộc core/backend.

PostgreSQL lưu upload sessions, runs, revisions, groups, allocation edges và artifact manifests. Raw/canonical/result files nằm trên artifact volume với relative path và SHA-256 trong database. Một dashboard/export phải đọc cùng `run_id` và effective revision.

Các giới hạn hiện tại: ứng dụng local một người, chưa có xác thực để public Internet, không có job queue, và chưa hỗ trợ review/undo thuộc phạm vi sau.

