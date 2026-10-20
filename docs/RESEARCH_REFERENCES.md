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

- [Python `decimal` documentation](https://docs.python.org/3/library/decimal.html) mô tả số học decimal, exact representation và rounding modes. SmartRecon chọn parse `Decimal` rồi lưu integer minor units; đây là quyết định thiết kế nhằm bảo toàn phép cộng/trừ tiền. So sánh chính xác trên `Decimal` được dùng để từ chối VND có phần thập phân khác 0 trước khi chuyển sang integer; không dùng phép làm tròn cho trường hợp này.
- [ISO 4217 currency list](https://www.six-group.com/en/products-services/financial-information/data-standards.html) là nguồn mã currency/minor unit. Phạm vi hiện tại khóa VND (0) và BRL (2); không có FX. Việc coi VND phân số khác 0 là lỗi `BLOCKING` là quyết định nghiệp vụ đã được chủ dự án phê duyệt, không phải kết quả benchmark hoặc diễn giải mở rộng từ ISO 4217; chính sách BRL không đổi.
- Wang, R. Y. & Strong, D. M. (1996), “Beyond Accuracy: What Data Quality Means to Data Consumers”, *Journal of Management Information Systems*, DOI [10.1080/07421222.1996.11518099](https://doi.org/10.1080/07421222.1996.11518099). Health Gate của dự án là contract nghiệp vụ riêng gồm blocking/warning/info, không tuyên bố bao phủ toàn bộ framework của bài báo.
- Các identity cash/receivable trong `MONEY_INVARIANTS.md` là **quy tắc nghiệp vụ của hệ thống simplified payment reconciliation**, không phải chuẩn kế toán tổng quát. Chúng chỉ đúng sau khi xác định eligibility, direction, amount basis và adjustment policy.

## Subset/group matching và giới hạn tính toán

- Garey, M. R. & Johnson, D. S. (1979), *Computers and Intractability*, W. H. Freeman, là nguồn kinh điển cho tính khó của các bài toán tổ hợp liên quan subset sum. SmartRecon không brute-force toàn tập: block trước, giới hạn group/block/combinations, và không auto-confirm từ amount sum đơn thuần.
- Giới hạn `k<=3`, `block_size<=20`, `max_combinations=2000` là guardrail demo nội bộ. Khi budget cạn, kết quả phải review; không được xác nhận từ search dở dang.

## SQL, transaction và persistence

- [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html) mô tả isolation levels và serialization failures. Review dùng optimistic `expected_revision` trong transaction để phát hiện client stale.
- [PostgreSQL Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html) là nguồn chính thức cho row-level locking. SmartRecon khóa hàng `runs` bằng `SELECT FOR UPDATE`, sau đó kiểm tra revision, idempotency, allocation và invariant trước khi commit revision/audit/effective state.
- [SQLAlchemy ORM documentation](https://docs.sqlalchemy.org/en/20/orm/) và [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) là tài liệu chính thức cho persistence/migration.
- [DuckDB concurrency](https://duckdb.org/docs/stable/connect/concurrency) nêu mô hình thư viện nhúng. Dự án dùng DuckDB cho analytics trong tiến trình, không làm shared transaction server.

## API, giao diện, container và bảo mật file

- [Python `csv` documentation](https://docs.python.org/3/library/csv.html) mô tả dialect, delimiter, quoting và `DictWriter`. SmartRecon dùng tập delimiter đóng và tự chấm điểm nhiều phương án thay vì coi `Sniffer` là quyết định nghiệp vụ cuối cùng.
- [openpyxl `load_workbook`](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/reader/excel.html) định nghĩa `read_only`, `keep_vba` và `data_only`. Reader dùng workbook read-only, không giữ/chạy VBA và đọc cached value thay vì thực thi công thức; các giới hạn ZIP riêng vẫn bắt buộc.
- [FastAPI file upload](https://fastapi.tiangolo.com/tutorial/request-files/) và [Pydantic documentation](https://docs.pydantic.dev/latest/) là contract framework chính thức.
- [React documentation](https://react.dev/), [Vite guide](https://vite.dev/guide/) và [Plotly JavaScript documentation](https://plotly.com/javascript/) là nguồn công nghệ frontend.
- [Docker Compose documentation](https://docs.docker.com/compose/) và [Docker volumes](https://docs.docker.com/engine/storage/volumes/) là nguồn cho stack ba service và named volumes.
- [Compose project name](https://docs.docker.com/compose/how-tos/project-name/) và [Compose networking](https://docs.docker.com/compose/how-tos/networking/) là nguồn cho project/network/storage độc lập. Lab dùng `--project-name` rõ ràng, named volumes riêng và không kết nối external network. Đây là cơ chế cách ly tài nguyên Compose, không phải mô hình phân quyền giữa các tài khoản quản trị Docker.
- [Docker Compose production guide](https://docs.docker.com/compose/how-tos/production/) là nguồn cho file override production, restart policy và image chứa code thay vì bind mount. [Startup order](https://docs.docker.com/compose/how-tos/startup-order/) định nghĩa `service_healthy` và `service_completed_successfully` dùng để chạy migration một lần trước backend.
- [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/17/app-pgdump.html) và [`pg_restore`](https://www.postgresql.org/docs/17/app-pgrestore.html) là nguồn cho custom-format database backup/restore. Artifact volume phải được backup cùng database theo contract riêng của SmartRecon; dump đơn lẻ không đủ phục hồi run.
- `pg_dump` cung cấp snapshot nhất quán của DB, không đồng bộ nguyên tử với filesystem artifacts. Quy trình lab thiết lập khoảng không ghi bằng cách drain/dừng writer duy nhất trước khi copy hai store, lưu checksum từng file và kiểm tra restore run/revision/audit/allocation. Đây là quy trình vận hành nội bộ được thử ở checkpoint môi trường, không được diễn giải thành bảo đảm backup online khi còn writer khác.
- [Nginx HTTPS guide](https://nginx.org/en/docs/http/configuring_https_servers.html) và [HTTP proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) là nguồn cấu hình TLS termination/reverse proxy ở host. Chúng không thay thế authentication hoặc access-control của ứng dụng.
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) là cơ sở kiểm tra extension/content/size/path; ứng dụng vẫn phải có tests riêng cho CSV/XLSX và formula injection.
- [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection) là nguồn cho việc escape chuỗi user-origin bắt đầu bằng `=`, `+`, `-`, `@` khi export. Không đổi numeric cells thành text tùy tiện.

## Đánh giá

- [scikit-learn `precision_recall_fscore_support`](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_fscore_support.html) được dùng làm nguồn định nghĩa Precision, Recall và F-score. SmartRecon tự tính các tỷ lệ trên tập predicted/truth edges để không thêm runtime dependency; trường hợp mẫu số 0 được công bố là N/A thay vì che bằng giá trị mặc định.
- Group exact match so cả tập order IDs và bank IDs; amount error đo riêng. Threshold/coverage/throughput chỉ được báo sau khi thực chạy, kèm data hash, seed, policy, rule version và phần cứng. SmartRecon chưa tuyên bố độ chính xác trên sao kê thật.
- [Jupyter Notebook format](https://nbformat.readthedocs.io/en/latest/) và [nbclient](https://nbclient.readthedocs.io/en/latest/) là tài liệu chính thức cho notebook artifact và thực thi kernel sạch trong kiểm thử.
