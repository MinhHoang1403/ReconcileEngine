# Nguồn nghiên cứu và tài liệu kỹ thuật

Tài liệu này phân biệt nguồn nghiên cứu, đặc tả chính thức, quyết định nghiệp vụ và heuristic nội bộ. Không có benchmark hoặc độ chính xác nào được suy ra chỉ từ các nguồn dưới đây.

## Record linkage và entity resolution

- Fellegi, I. P. & Sunter, A. B. (1969), “A Theory for Record Linkage”, *Journal of the American Statistical Association*, 64(328), 1183–1210, DOI [10.1080/01621459.1969.10501049](https://doi.org/10.1080/01621459.1969.10501049). Đây là nền tảng nghiên cứu về quyết định match/non-match/review dựa trên evidence; SmartRecon không triển khai mô hình xác suất Fellegi–Sunter và không gọi heuristic score là xác suất.
- Christen, P. (2012), *Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection*, Springer, DOI [10.1007/978-3-642-31164-2](https://doi.org/10.1007/978-3-642-31164-2). Dùng làm tham chiếu khái niệm normalization, blocking, comparison và evaluation; không dùng để biện minh auto-confirm thiếu chứng cứ tài chính.

## Chuẩn hóa, fuzzy và candidate generation

- [Unicode Standard Annex #15 — Unicode Normalization Forms](https://unicode.org/reports/tr15/) là nguồn cho NFKC. Dự án giữ raw text và chỉ dùng normalized text làm evidence có kiểm soát.
- [RapidFuzz `fuzz` documentation](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) định nghĩa các similarity scorer trả điểm 0–100. Điểm này là similarity/ranking, không phải xác suất đúng và không tự xác nhận giao dịch.
- Blocking theo currency/date/amount/reference và `Top-K=5`, threshold 85, block size 20, group size 3 là **heuristic demo nội bộ chưa được chứng minh phổ quát**. Nó phải được ghi policy snapshot, test adversarial và hiệu chỉnh trên dữ liệu có truth tách riêng.

## Tiền, chất lượng dữ liệu và bảo toàn

- [Python `decimal` documentation](https://docs.python.org/3/library/decimal.html) mô tả số học decimal, exact representation và rounding modes. SmartRecon chọn parse `Decimal` rồi lưu integer minor units; đây là quyết định thiết kế nhằm bảo toàn phép cộng/trừ tiền.
- [ISO 4217 currency list](https://www.six-group.com/en/products-services/financial-information/data-standards.html) là nguồn mã currency/minor unit. Phạm vi hiện tại khóa VND (0) và BRL (2); không có FX.
- Wang, R. Y. & Strong, D. M. (1996), “Beyond Accuracy: What Data Quality Means to Data Consumers”, *Journal of Management Information Systems*, DOI [10.1080/07421222.1996.11518099](https://doi.org/10.1080/07421222.1996.11518099). Health Gate của dự án là contract nghiệp vụ riêng gồm blocking/warning/info, không tuyên bố bao phủ toàn bộ framework của bài báo.
- Các identity cash/receivable trong `MONEY_INVARIANTS.md` là **quy tắc nghiệp vụ của hệ thống simplified payment reconciliation**, không phải chuẩn kế toán tổng quát. Chúng chỉ đúng sau khi xác định eligibility, direction, amount basis và adjustment policy.

## Subset/group matching và giới hạn tính toán

- Garey, M. R. & Johnson, D. S. (1979), *Computers and Intractability*, W. H. Freeman, là nguồn kinh điển cho tính khó của các bài toán tổ hợp liên quan subset sum. SmartRecon không brute-force toàn tập: block trước, giới hạn group/block/combinations, và không auto-confirm từ amount sum đơn thuần.
- Giới hạn `k<=3`, `block_size<=20`, `max_combinations=2000` là guardrail demo nội bộ. Khi budget cạn, kết quả phải review; không được xác nhận từ search dở dang.

## SQL, transaction và persistence

- [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html) mô tả isolation levels và serialization failures. Phạm vi hiện tại chưa triển khai workflow review cạnh tranh, nhưng schema giữ revision/audit để mở rộng đúng transaction sau này.
- [SQLAlchemy ORM documentation](https://docs.sqlalchemy.org/en/20/orm/) và [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) là tài liệu chính thức cho persistence/migration.
- [DuckDB concurrency](https://duckdb.org/docs/stable/connect/concurrency) nêu mô hình thư viện nhúng. Dự án dùng DuckDB cho analytics trong tiến trình, không làm shared transaction server.

## API, giao diện, container và bảo mật file

- [FastAPI file upload](https://fastapi.tiangolo.com/tutorial/request-files/) và [Pydantic documentation](https://docs.pydantic.dev/latest/) là contract framework chính thức.
- [React documentation](https://react.dev/), [Vite guide](https://vite.dev/guide/) và [Plotly JavaScript documentation](https://plotly.com/javascript/) là nguồn công nghệ frontend.
- [Docker Compose documentation](https://docs.docker.com/compose/) và [Docker volumes](https://docs.docker.com/engine/storage/volumes/) là nguồn cho stack ba service và named volumes.
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) là cơ sở kiểm tra extension/content/size/path; ứng dụng vẫn phải có tests riêng cho CSV/XLSX và formula injection.
- [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection) là nguồn cho việc escape chuỗi user-origin bắt đầu bằng `=`, `+`, `-`, `@` khi export. Không đổi numeric cells thành text tùy tiện.

## Đánh giá

Precision, recall và F1 dùng định nghĩa chuẩn trên tập predicted/truth edges. Group exact match so cả tập order IDs và bank IDs; amount error đo riêng. Threshold/coverage/throughput chỉ được báo sau khi thực chạy, kèm data hash, seed, policy, rule version và phần cứng. SmartRecon chưa tuyên bố độ chính xác trên sao kê thật.

