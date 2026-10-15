# NHIỆM VỤ CHO CODEX — TRIỂN KHAI GIAI ĐOẠN 1 SMARTRECON

Bạn là Senior Python/Data Engineer, Software Architect và Full-stack Engineer, đang làm việc trực tiếp trong **thư mục `ReconcileEngine` đã mở trong Antigravity IDE**. Hãy **triển khai Giai đoạn 1** của một dự án **Smart Financial Reconciliation & Analytics** mới, độc lập, chính xác và có khả năng mở rộng để deploy. Đây là yêu cầu **thực hiện code và kiểm thử thật**, không chỉ lập kế hoạch hoặc tạo giao diện mô phỏng.

## 0. Đọc tài liệu và kiểm tra trước khi sửa

1. Kiểm tra working directory, toàn bộ file hiện có, `git status`, Git remote, Python/uv, Node.js, Docker/Compose và môi trường Windows/WSL nếu liên quan. **Làm việc ngay tại root `ReconcileEngine`; không tạo thêm thư mục project lồng bên trong; không xoá/ghi đè file hiện có một cách tùy tiện.**
2. Tìm và đọc kỹ các tài liệu tham chiếu trong `docs/`:
   - `IMPLEMENTATION_PLAN.md`: **kế hoạch triển khai ưu tiên cao nhất**, đặc biệt Giai đoạn 1, kiến trúc Docker/PostgreSQL và acceptance gate.
   - `MASTER_PLAN.md`: chi tiết nghiệp vụ, canonical schema, matching, bảo toàn tiền, **Phụ lục A và B (golden fixtures)**.
   - Nếu có `PRIOR_EXECUTION_PLAN.md`, chỉ dùng tham khảo workflow, **không dùng lựa chọn SQLite cũ**.
3. **Nếu thiếu hai tài liệu bắt buộc đầu tiên: dừng trước khi code, báo rõ tên file cần bổ sung. Tuyệt đối không đoán nội dung bị thiếu.**
4. Thứ tự ưu tiên khi có mâu thuẫn: **các quy tắc người dùng dưới đây → kế hoạch V5 (hạ tầng, hai giai đoạn) → Phụ lục A/B của V3 (nghiệp vụ, test oracle) → phần còn lại của V3**. Nếu vẫn còn xung đột ảnh hưởng tính đúng đắn, báo vấn đề và hỏi trước khi đổi thiết kế.
5. Trước khi sửa code, trình bày ngắn gọn bằng tiếng Việt: trạng thái thư mục/môi trường, kiến trúc sẽ triển khai, các nhóm công việc, các lệnh kiểm thử dự kiến và rủi ro thực tế. Sau đó triển khai lần lượt theo checkpoint bên dưới; **không dừng ở bản kế hoạch nếu không có blocker**.

## 1. QUY TẮC BẮT BUỘC CỦA CHỦ DỰ ÁN

### 1.1. Mã nguồn sạch, dễ đọc, dễ bảo trì
- Dùng tên module/file/class/hàm/biến **đúng chức năng**, nhất quán; chỉ tạo các file thực sự cần thiết.
- Áp dụng trách nhiệm đơn nhất, type hints, docstrings và comment có ý nghĩa. **Chú thích rõ quy tắc nghiệp vụ, thuật toán không hiển nhiên, rủi ro tính tiền**, nhưng không rải comment giải thích từng lệnh quá đơn giản.
- Tách **domain/core thuần Python** khỏi API, giao diện, database, ingestion, generator và thử nghiệm.
- Không copy một thuật toán nhiều lần vào Notebook, API và Frontend; chỉ có **một Python Core**.

### 1.2. Không đem tên kế hoạch vào code/project
- **Cấm** đặt tên thư mục, module, file, class, hàm, biến, component hay API bằng nhãn như `v1`, `v2`, `s1`, `s2`, `e3`, `phase1`, `phase2`, `final`, `new`, `freeze`, `frozen`, v.v. Chỉ dùng nhãn giai đoạn/phiên bản **trong tài liệu kế hoạch làm việc**, không đặt tên các thành phần phần mềm như vậy.
- Ví dụ đúng: `matching/reference.py`, `matching/grouping.py`, `domain/allocations.py`, `ReconciliationDashboard.tsx`, `/api/runs`.
- Không sao chép nguyên tên đường dẫn API `/api/v1/...` của kế hoạch V3; **dùng `/api/...` không gắn nhãn phiên bản** theo yêu cầu mới của chủ dự án.
- Version constraints trong `uv.lock`, package metadata, Alembic migration identifiers, Git SHA và thông số giao thức được phép khi **đó là dữ liệu kỹ thuật cần thiết**, không phải tên tùy tiện cho tính năng.

### 1.3. Mọi phương pháp phải có nguồn và bằng chứng
- Tạo `docs/RESEARCH_REFERENCES.md` giải thích và **dẫn nguồn có thể kiểm tra** cho: record linkage/entity resolution (liên kết bản ghi), normalization, string similarity/RapidFuzz, blocking/candidate generation, constrained/subset matching, decimal arithmetic, data quality, SQL analytical processing, transaction isolation/concurrency, reconciliation conservation, test/evaluation metrics và công nghệ chính.
- Ưu tiên **bài báo bình duyệt, sách học thuật/tiêu chuẩn chuyên ngành**, bổ trợ bằng tài liệu chính thức từ Python, PostgreSQL, DuckDB, FastAPI, React, Docker, OWASP. Phân biệt rõ: kết quả nghiên cứu, đặc tả kỹ thuật chính thức, **giả định/heuristic tự đề xuất** và quy tắc nghiệp vụ của demo.
- Mỗi công thức/rule quan trọng phải có mô tả, điều kiện áp dụng, giới hạn, test minh chứng và nguồn dẫn; nếu là heuristic nội bộ, nói rõ đây **không phải công thức đã được chứng minh phổ quát**.
- **Không bịa DOI, bài báo, URL, kết quả benchmark hoặc con số độ chính xác.** Nếu không thể kiểm chứng một nguồn do thiếu truy cập, ghi `CHƯA XÁC MINH`, không coi như nguồn đã kiểm tra.

### 1.4. Kỷ luật triển khai và chống overengineering
- Bám sát Giai đoạn 1; **không tự mở rộng phạm vi hoặc thay stack**. Không thêm Redis, Celery, Kubernetes, S3 server, 3PL, FX, ML/LLM, microservices, auth enterprise, full accounting ledger.
- Chỉ sửa file cần thiết; không thay đổi ngoài phạm vi. Không hardcode dữ liệu kết quả hoặc mock số KPI để giao diện có vẻ chạy được.
- Sau mỗi checkpoint: chạy test tương ứng, sửa lỗi rồi mới tiếp tục. Nếu gặp blocker, mô tả rõ và dừng phần bị chặn; không làm lộn xộn nhiều nhánh việc cùng lúc.
- Giao tiếp/report bằng **tiếng Việt**, thuật ngữ kỹ thuật kèm chú thích dễ hiểu.
- Giữ nguyên dữ liệu gốc, không commit secrets, file `.env`, dữ liệu tài chính riêng tư hoặc artifacts lớn.

### 1.5. Repository tham khảo
- **KHÔNG** clone/fork/copy mã nguồn từ `dpduc/ReconEngine`, không dựa vào module nội bộ của repo đó.
- Chỉ được tham khảo ý tưởng và **dữ liệu có quyền sử dụng**. Nếu sử dụng Olist phải ghi `DATA_ATTRIBUTION.md` (nguồn, giấy phép, phần gốc/phần giả lập, cách tạo lại); Olist **không chứa bank statement thực tế**. Không tự bịa bản ghi Olist nếu không có dữ liệu gốc.

## 2. PHẠM VI SẢN PHẨM PHẢI HOÀN THÀNH Ở GIAI ĐOẠN 1

Người dùng mở website và thực hiện được quy trình **end-to-end**:

1. Chọn demo data hoặc upload **hai nguồn** (`Orders/Internal Receivables` và `Bank/PSP Transactions`) từ CSV/XLSX; hỗ trợ một workbook Excel có hai sheet đã chọn nếu không làm tăng complexity không cần thiết.
2. **Raw preview + EDA sơ bộ:** số dòng/cột, ví dụ bản ghi, missing/duplicate, phân bố ngày/tiền có ghi rõ độ tin cậy khi chưa chuẩn hóa.
3. **Mapping có xác nhận** cột nguồn → canonical, chọn source profile, money basis, date format, currency/direction; normalize ID, text, time, money; hiển thị **EDA sau chuẩn hóa**.
4. **Health Gate:** blocking/warning/info; bản ghi lỗi được giữ lineage và xử lý bằng chính sách rõ ràng (acknowledge, exclude có lý do, remap hoặc reupload); không tự bỏ dữ liệu.
5. Nhấn **Chạy đối soát**; chạy một Python Core theo waterfall 4 lớp; trả về groups/edges/proposals/exceptions/metrics có bằng chứng, reason codes và lời giải thích tiếng Việt.
6. Xem **Dashboard cơ bản** (đúng mẫu số), xem danh sách đơn, bank, nhóm ghép, exceptions, các khoản tiền phân bổ/thiếu/thừa.
7. **Xuất Excel thật** từ cùng run/snapshot và mở lại một run sau restart Docker.

**Chỉ có hai logical feeds.** Không bắt phải upload logistics. Ground truth chỉ để generator/evaluation/tests, tuyệt đối không đi qua matching runtime hoặc endpoint normal upload.

## 3. STACK VÀ HẠ TẦNG CHỐT — KHÔNG TỰ THAY ĐỔI

- **Python 3.12**, `uv`/`pyproject.toml` + lockfile, Pandas, `Decimal`/integer minor units, RapidFuzz, DuckDB nhúng trong Python Core.
- **FastAPI + Pydantic + SQLAlchemy + Alembic** cho API, schema/validation và lưu bền vững.
- **PostgreSQL** (KHÔNG SQLite) lưu upload sessions, runs, config/policy snapshots, groups, allocations, manifest, effective revision và các cấu trúc audit tối thiểu phục vụ mở rộng review.
- **React + TypeScript + Vite + Plotly** cho website tiếng Việt; không dùng Streamlit song song.
- **Docker Compose** gồm 3 service `frontend`, `backend`, `db`; PostgreSQL có volume `pg_data`; file artifacts có volume `artifacts_data` hoặc cấu hình tương đương. Không có DuckDB server/container riêng; không publish cổng PostgreSQL lên host công cộng.
- Backend chỉ **một worker cho local demo**. Các file gốc, snapshot normalized Parquet, manifest, export được lưu trong artifact storage, không phụ thuộc vào writable layer tạm của container.
- Dùng `.env.example`, `.gitignore`, `.dockerignore`, healthchecks; không ghi secrets thật vào mã nguồn/log. Migration áp dụng đáng tin cậy sau khi DB healthy; không race tạo schema.
- Không tạo thêm infrastructure service hoặc abstraction chỉ để “chuẩn bị mở rộng”; chỉ thiết kế interface khi thật sự cần cho feature hiện tại.

## 4. DOMAIN CONTRACT VÀ BẤT BIẾN TIỀN — ƯU TIÊN P0

Tạo các domain models/hợp đồng rõ ràng:

- `Order` / `Receivable`: `order_id`, `ordered_at`, `expected_amount_minor`, `currency`, eligibility/status, optional refs, source lineage.
- `BankTransaction`: `bank_txn_id`, `txn_ref`, `txn_date`, optional `value_date`, `direction`, `posted_amount_minor`, `amount_basis`, `currency`, description, lineage.
- `MatchGroup` (ONE_TO_ONE / MANY_ORDERS_ONE_BANK / ONE_ORDER_MANY_BANKS / AMBIGUOUS), `AllocationEdge`, `MatchEvidence`, `Candidate`, `Exception`, `RunManifest`.
- Tách ba trạng thái độc lập `link_status`, `payment_status`, `review_status`; màu xanh/vàng/đỏ **chỉ là trạng thái hiển thị suy ra từ nghiệp vụ**.
- Một run chỉ một currency (VND hoặc BRL). Parser dùng `Decimal` rồi quy đổi về **integer minor units**; không dùng `float` để cộng/trừ tiền hoặc chấp nhận các nguồn tiền khác currency một cách ngầm định.
- Định nghĩa `POSTED_CASH`/`NET_SETTLEMENT`/gross đúng nghĩa. Không coi `gross PSP sales` là tiền ngân hàng đã ghi có. Fee/adjustment chỉ hợp lệ khi có chứng cứ và policy; không tự xem một khoản thiếu 1–2% là phí.

**Các bất biến cần code + test độc lập:**

```text
0 <= allocated_bank(b) <= eligible_credit(b)
unapplied_bank(b) = eligible_credit(b) - allocated_bank(b)
0 <= allocated_to_order(o) + verified_adjustments(o) <= expected(o)
outstanding(o) = expected(o) - allocated_to_order(o) - verified_adjustments(o)
SUM(eligible_bank_credit) = SUM(confirmed_cash_allocations) + SUM(unapplied_bank_credit)
SUM(eligible_receivables) = SUM(confirmed_cash_allocations) + SUM(verified_adjustments) + SUM(outstanding_receivables)
```

- Proposed candidates không góp vào confirmed KPI.
- Ngân hàng chuyển gộp được chia thành nhiều `AllocationEdge` nhưng **không được cộng nguyên số tiền ngân hàng nhiều lần**.
- Không xác nhận vượt số tiền bank/order; không sử dụng lại cùng dòng bank sai quy tắc.
- `CONFIRMED_LINK` không đồng nghĩa `FULL`; giao dịch xác định đúng nhưng chuyển thiếu phải là `PARTIAL`.
- Giữ hash hàng dữ liệu/file, nguồn ban đầu, mapping/policy snapshots, step/rule evidence và run ID; raw input bất biến.

## 5. WATERFALL MATCHING 4 LỚP

**Trước khi commit bất kỳ cặp 1:1**, phân tích trước các chứng cứ multi-reference rõ ràng để tránh chiếm nhầm bank/order đáng lẽ phải nằm trong group hoặc split. Dùng conflict resolver nhất quán; không làm mất ứng viên do thứ tự DataFrame.

1. **L1 — Strong Reference:** match 1:1 và xác định N:1/1:N từ full unique reference, đúng token boundary/currency/direction/eligibility; nhận diện nhiều mã trong bank memo; có thể `CONFIRMED` khi đủ chứng cứ và không xung đột. Không dùng substring sai `DH01`/`DH010`.
2. **L2 — Policy-Constrained:** hỗ trợ lệch ngày T+N và money/fee policies khi có nguồn tham chiếu đủ mạnh; không tự match chỉ vì amount+date gần giống. Thời điểm `ordered_at`, `txn_date`, `value_date` phải phân biệt rõ.
3. **L3 — Fuzzy Candidates:** RapidFuzz để đề xuất TOP-K ứng viên có blocking và guardrails; **PROPOSED/NEEDS_REVIEW**, không auto chỉ dựa similarity; missing features không được coi là khớp. Điểm similarity **không phải xác suất đúng**.
4. **L4 — Bounded Group/Split:** phát hiện N orders → 1 bank và 1 order → N bank từ phần chưa xử lý; blocking theo dữ liệu hợp lệ, hạn chế số phần tử/tổ hợp/thời gian. Thiếu strong evidence thì chỉ PROPOSED. M:N phức tạp chỉ `COMPLEX_MANY_TO_MANY_REVIEW`.

Sau waterfall: giải quyết xung đột, tạo **confirmed cash allocations**, residual, exception/orphan classifications, deterministic KPIs, explainability bằng tiếng Việt. Luôn ưu tiên **đúng tiền > tránh ghép nhầm > truy vết > giao diện > tốc độ**.

## 6. DATASETS VÀ KHẢ NĂNG TÁI LẬP

- Viết generator **deterministic**, seeded: một bộ demo synthetic VND cỡ **80–120 orders**, có đủ các ca exact, T+N, fuzzy, N:1, 1:N, partial, overpayment, orphan, ambiguous, duplicate, fee verified/unverified, debit; số bank rows không bắt buộc bằng số orders.
- Xuất hai feed CSV (và workbook hai sheet nếu có thể), **`truth_edges.csv`, `truth_cases.csv`, `manifest.json` tách riêng**, ghi seed/hash/provenance/quota mẫu số. Không chèn `ground_truth_case` vào feed nghiệp vụ.
- Có adapter/sample generator **Olist-derived BRL** từ bộ Olist hợp lệ được cung cấp/tải về theo quyền sử dụng. Bank/PSP feed phải được **gắn nhãn synthetic**, không giả vờ là bank thực. Nếu không lấy được Olist, làm adapter có tests và ghi blocker dữ liệu thay vì tự bịa hoặc bỏ hẳn yêu cầu.
- Seed/config giống nhau phải tạo kết quả nghiệp vụ và source manifest tái lập; không đưa `now()`/ID ngẫu nhiên vào semantic result checksums.
- Không commit file tài chính thật, dataset Olist dung lượng lớn hoặc báo cáo generated nhạy cảm.

## 7. BACKEND VÀ FRONTEND GIAI ĐOẠN 1

Thiết lập API ổn định **không gắn nhãn phiên bản trong path**. Tối thiểu:

```text
GET  /healthz
POST /api/demo/datasets             # local/demo only
POST /api/uploads/inspect          # 2 feeds hoặc workbook 2 sheet
POST /api/uploads/{session_id}/mapping
GET  /api/uploads/{session_id}/health
POST /api/uploads/{session_id}/resolutions  # khi cần xử lý Health Gate
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/dashboard
GET  /api/runs/{run_id}/groups
GET  /api/runs/{run_id}/groups/{group_id}
GET  /api/runs/{run_id}/orders
GET  /api/runs/{run_id}/bank-transactions
GET  /api/runs/{run_id}/exceptions
GET  /api/runs/{run_id}/exports?format=xlsx
```

- Pydantic response schemas nhất quán; hỗ trợ pagination, status codes, lỗi giải thích bằng tiếng Việt; không trả 100k records trong một JSON.
- Upload kiểm tra extension, content type, magic/content, dung lượng, sheet count, shape; từ chối dữ liệu không phù hợp; export chống **Excel formula injection**. Không mở file lạ để thực thi macro.
- Giao diện tiếng Việt tối thiểu đủ các bước: **Upload + Raw EDA → Mapping + Standardized EDA/Health → Run → Dashboard/Explorer/Export**. Bảng, KPI, biểu đồ sử dụng **API thật**, không dữ liệu giả cố định.
- Mỗi KPI/chart/export được tính từ **cùng `run_id` + effective revision**. Phân biệt mẫu số: số đơn, số dòng bank và tổng tiền.
- Giai đoạn 1 **chưa cần** UI/API `APPROVE`, `REJECT`, `UNDO`, audit review đầy đủ, notebook research/holdout hoàn chỉnh, deployment HTTPS public. Đây là **Giai đoạn 2**, không làm sớm để tránh phình phạm vi.

## 8. KẾ HOẠCH THỰC HIỆN THEO CHECKPOINT (VẪN LÀ MỘT GIAI ĐOẠN)

Thực hiện theo thứ tự, **không code tất cả module trong một lần rồi mới chạy test**:

**Checkpoint A — Foundation & Docker**
- Kiến trúc, `AGENTS.md` ghi bộ quy tắc ở trên, thư mục đúng chức năng, `pyproject.toml`, lockfile, Python package, React scaffold, Dockerfiles, Compose 3 services, env example, CI/lint/test baseline.
- PostgreSQL connection, SQLAlchemy models tối thiểu, Alembic migrations, named volumes. Docker build/health smoke.

**Checkpoint B — Data Contracts & Synthetic/Olist Adapters**
- Canonical models, safe money/date parsing, generators, manifest và truth tách riêng, test deterministic và no truth leakage; tài liệu nguồn data.

**Checkpoint C — Ingestion, EDA, Mapping & Health Gate**
- CSV/XLSX read, preview, mapping, normalization, blocking/warning/info, source lineage; test format-equivalence và bad inputs.

**Checkpoint D — Reconciliation Engine**
- 4 matching layers, conflict-safe group/edges, invariants, residual, exceptions và test oracle thực tế. Không hardcode để qua fixture.

**Checkpoint E — API, Website & Export**
- REST endpoints, FE workflow thật, KPI/charts/tables, export Excel, persistence, run reopen.

**Checkpoint F — Integration & Acceptance**
- End-to-end docker/browser smoke, migrations, volumes, restart persistence, logs, README Windows/PowerShell+Docker WSL2, báo cáo QA.

Sau mỗi checkpoint: chạy các kiểm thử có liên quan, ghi lệnh/exit code/result, commit Git an toàn nếu repo được cấu hình; không tự thay đổi scope để né lỗi.

## 9. GOLDEN TESTS & ĐIỀU KIỆN NGHIỆM THU

**Trích oracle trực tiếp từ Phụ lục B của V3, không sáng tác expected results.** Ở Giai đoạn 1 phải xử lý/test **22 fixtures** sau:

- `F01` exact; `F02` T+2; `F03` ref normalization; `F04` fuzzy proposed; `F05` ambiguous no auto.
- `F06` strong N:1; `F07` weak N:1 proposed; `F08` strong 1:N.
- `F09` partial; `F10` overpayment residual; `F11` missing bank; `F12` orphan bank.
- `F13` duplicate import; `F14` distinct same-amount transfers.
- `F15` verified PSP fee; `F16` unverified fee; `F17` debit excluded; `F18` ref token boundary.
- `F21` different currency blocked; `F22` leading-zero Excel IDs; `F23` Excel export formula injection; `F24` complex many-to-many REVIEW.

`F19` (hai review đồng thời) và `F20` (undo) dành cho Giai đoạn 2, **không triển khai UI review chỉ để pass 2 fixture đó**.

Ngoài golden fixtures, bắt buộc có:

- Property/invariant tests: bảo toàn tiền ở mỗi bank/order/toàn run, không double count, không auto xác nhận ca mơ hồ, proposal không vào confirmed KPIs.
- Test chuẩn hóa `Decimal` VND/BRL, ID chuỗi, currency mismatch, duplicate policies, gross/net.
- Test cùng dữ liệu CSV và XLSX ra kết quả nghiệp vụ tương đương; truth không xuất hiện trong engine normal API.
- Test FastAPI upload→mapping→Health→run→dashboard→export, output XLSX mở được và số tiền khớp.
- Test frontend build, browser smoke và API↔dashboard consistency.
- Docker: `docker compose config`, clean image build, Postgres healthy + migrations, lưu/reopen run, `docker compose down` rồi `up -d` vẫn còn data, artifact export còn tồn tại; **không dùng `down -v` khi kiểm tra persistence**.
- Chạy Ruff, pytest và tests FE; **không báo pass nếu chưa chạy**. Nếu thiếu Docker/Node/network trong môi trường, ghi rõ blocker cùng lệnh để người dùng chạy, không giả lập test result.

## 10. DEFINITION OF DONE — CHỈ BÁO HOÀN THÀNH KHI ĐẠT

1. Từ thư mục gốc chạy được `docker compose up --build -d`; `frontend`, `backend`, `db` hoạt động và healthchecks pass.
2. Người dùng trên trình duyệt chọn demo data/CSV/XLSX → xem raw EDA → mapping → standardized EDA → Health → chạy đối soát 4 lớp → dashboard/bảng groups/exceptions → xuất workbook Excel thật.
3. Các ca exact, N:1, 1:N, partial, over, ambiguous, orphan, duplicate/fee đúng oracle; 22 golden fixtures và money invariants pass; không false auto-confirm trên các fixture mơ hồ.
4. Khi dừng/khởi động lại Compose, run, group/edge snapshot và report vẫn có thể xem/xuất lại.
5. Có `AGENTS.md`, `README.md` tiếng Việt, `docs/ARCHITECTURE.md`, `docs/DATA_CONTRACT.md`, `docs/MONEY_INVARIANTS.md`, `docs/RESEARCH_REFERENCES.md`, `docs/DATA_ATTRIBUTION.md` và tài liệu API/vận hành cần thiết; nguồn học thuật/kỹ thuật được đánh dấu đã/ chưa xác minh trung thực.
6. Không còn lỗi P0; không có code sao chép từ repo tham khảo, hardcoded secrets, dataset truth leakage hoặc mở Postgres ra Internet.
7. Lệnh test, số lượng pass/fail, log và hạn chế ghi lại minh bạch. **Nếu một điều kiện không đạt thì báo `CHƯA HOÀN THÀNH GIAI ĐOẠN 1`, tuyệt đối không gọi là xong.**

## 11. GIT VÀ BÁO CÁO KHI KẾT THÚC

- Nếu chưa có Git repo thì `git init` trong **đúng thư mục hiện tại**, dùng nhánh `main`; kiểm tra và giữ nguyên remote nếu đã có. Không tự tạo repo GitHub công khai.
- Codex đảm nhiệm kiểm tra thay đổi, commit sau những checkpoint đạt test, push **khi có remote hợp lệ và được phép**. Không force-push, không xóa lịch sử hoặc thay đổi nhánh người khác; không commit `.env`, keys, dữ liệu cá nhân/raw Olist dung lượng lớn.
- Sau mỗi checkpoint, cập nhật ngắn bằng tiếng Việt các file thay đổi, chức năng đã hoạt động, test **thực sự** chạy và blocker.
- Báo cáo cuối cùng theo mẫu:

```text
A. Đã làm gì (theo các checkpoint A–F)
B. Cấu trúc source thực tế, các quyết định kỹ thuật có dẫn nguồn
C. Các lệnh đã thực thi và kết quả lint/test/build/Docker
D. Golden fixtures đã pass/fail; invariants và residual check
E. Cách khởi chạy trên Windows/PowerShell + Docker Desktop/WSL2
F. Demo thao tác thực tế trên browser, API URLs và export artifact
G. Git status/commit/push (nếu có)
H. Phần CHƯA làm hoặc blocker; xác nhận chưa lấn sang Giai đoạn 2
I. Kết luận: ĐẠT hoặc CHƯA ĐẠT gate Giai đoạn 1, kèm bằng chứng
```

**Hãy bắt đầu ngay bằng kiểm tra workspace và hai tài liệu nguồn. Sau khi đủ điều kiện, thực thi Checkpoint A rồi lần lượt B–F, sửa các lỗi kiểm thử trước khi chuyển tiếp. Không hỏi lại những quyết định đã được chốt; chỉ hỏi khi thực sự thiếu đầu vào hoặc gặp xung đột cần chủ dự án phê duyệt.**
