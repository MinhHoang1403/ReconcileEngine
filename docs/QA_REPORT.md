# Báo cáo nghiệm thu kỹ thuật

Ngày kiểm tra gần nhất: 2026-10-16. Môi trường: Windows/PowerShell, Docker Engine 29.7.2, Compose 5.5, Python 3.12 qua `uv`, Node 24.

## Kết quả tự động

| Nhóm | Lệnh | Kết quả |
|---|---|---|
| Python lint | `uv run ruff check .` | Pass |
| Python format | `uv run ruff format --check .` | Pass |
| Python tests | `uv run pytest -q` | 103 passed; một deprecation warning từ FastAPI TestClient và một warning event loop của Jupyter trên Windows |
| Golden | `uv run pytest tests/golden -q` | 28 tests pass; catalog đủ 24 fixtures F01–F24, gồm conflict F19 và undo dependency F20 |
| Property | `uv run pytest tests/property -q` | 4 passed; các bất biến bảo toàn tiền đạt |
| VND/CSV/XLSX/API | `uv run pytest tests/unit/test_money.py tests/integration/test_ingestion.py tests/api/test_workflow.py -q` | 36 passed |
| Frontend lint | `npm run lint` | Pass |
| Frontend unit | `npm run test -- --run` | 19 passed trong 6 test files |
| Frontend build | `npm run build` | Pass; Plotly basic bundle có cảnh báo chunk lớn, không phải lỗi build |
| Compose | `docker compose config --quiet` | Exit 0 |
| Images | `docker compose up --build -d` | Backend và frontend build sạch, ba services healthy |
| Migration | `docker compose exec -T backend uv run alembic current` | `20261015_03 (head)` |

## Review foundation và transaction safety

Ngày 2026-10-16, migration `20261015_03` được áp dụng trên PostgreSQL volume đang có dữ liệu. Trước và sau migration vẫn đọc được 45 upload sessions, 40 runs và 40 base revisions; một run cũ mở lại qua API thành công. Regression tại checkpoint này: `uv run ruff check .` pass và `uv run pytest -q` đạt 89 tests.

Acceptance PostgreSQL dùng run synthetic `d63e09ea-4508-4ac5-a36a-fd1ad5c72e75`. Approve nhóm N:1 `CAND-974f668fcf3ccae4` tạo revision 1, hai edges tổng 500.000 VND, nâng confirmed cash từ 66.431.000 lên 66.931.000 VND và conservation vẫn hợp lệ. Retry cùng idempotency key trả lại đúng action cũ; request revision 0 với key mới trả HTTP 409 `STALE_REVISION`. PostgreSQL có đúng một review action, hai run revisions và tổng allocation của `TXN00007` tại revision 1 đúng 500.000 VND.

Kiểm thử rollback gọi approve nhóm M:N không được hỗ trợ ở revision 1: API trả 409, `current_revision` vẫn là 1, số review actions vẫn là 1, không có row revision 2 và không có artifact revision 2. Unit test ép lỗi commit cũng xác nhận rollback về revision 0 và xóa result artifact chưa được công bố.

## Human-in-the-loop workflow

Review queue và history đọc cùng effective revision, có tìm kiếm, lọc loại quan hệ, phân trang, source amounts, allocation preview, evidence, proposal cạnh tranh và lý do khóa approve. UI yêu cầu ghi chú khi reject, ghi rõ `actor_label` không phải danh tính đã xác thực, tự tải lại khi gặp stale revision và dùng lại drawer nguồn/bằng chứng hiện có.

F19 được chạy trên PostgreSQL thật với hai proposal cạnh tranh cùng `TXN00007`: request từ revision 4 đầu tiên tạo revision 5 và đúng hai edges tổng 500.000 VND; request thứ hai vẫn gửi revision 4 trả HTTP 409. Conservation vẫn hợp lệ và bank không bị cấp vượt 500.000 VND. F20 được chạy trên run `32d41d11-58f2-409d-8d51-23c42bb2233b`: sau approve revision 3 và reject downstream revision 4, undo action ở revision 3 trả HTTP 409, current revision vẫn là 4. Unit/API tests cũng xác minh undo hợp lệ tạo revision mới, phục hồi snapshot trước và giữ audit cũ.

Browser smoke Edge headless đi qua upload demo, Health, reconcile, charts, drawer, export, chọn proposal có thể duyệt, xem allocation preview, approve, kiểm tra revision/conservation, undo và mở lại run. Kết quả `review_approve_undo_verified=true`; ảnh kiểm tra nằm ngoài repository trong thư mục tạm `smartrecon-review-checkpoint-b`. Frontend lint pass, 19 tests pass và production build pass; cảnh báo Plotly chunk lớn vẫn là hạn chế đã biết, không phải lỗi build.

## Analytics và báo cáo theo revision

Dashboard đọc analytics từ immutable result snapshot và audit actions đến đúng revision. Tỷ lệ xác nhận dùng toàn bộ relation groups làm mẫu số; lag dùng allocation pair đã xác nhận; residual orders/bank tách riêng. Frontend ghim dashboard, explorer, detail và phân trang vào revision đọc từ metadata run; review queue phát hiện snapshot lệch và khóa thao tác cho tới khi tải lại.

Excel giữ nguyên chín sheet, bổ sung `Trạng thái xác minh` trong group sheets và review audit thật gồm revision, allocation delta, note, actor label và liên kết undo. API export nhận `expected_revision` và trả 409 khi client cũ. Integration test xác nhận workbook revision 1 có action approve, group `APPROVED`, tổng allocation bằng KPI dashboard; historical dashboard/explorer revision 1 vẫn đọc đúng sau khi run đã sang revision 2.

Docker/browser acceptance tại `1366x768` dùng run `423395c5-1901-40c8-88ab-6926b38b0637`: approve tạo revision 1, dashboard ghi nhận một proposal `APPROVED` và một approve action; workbook revision 1 trả HTTP 200, 54.829 bytes; undo tạo revision 2 và analytics ghi nhận một undo action. Conservation vẫn hợp lệ, run mở lại được và không có lỗi browser/network. Ảnh analytics được sinh ngoài repository trong thư mục tạm `smartrecon-analytics-c`.

## Notebook và scientific evaluation

`notebooks/reconciliation_research.ipynb` được thực thi từ kernel mới bằng `nbclient`, không cần FastAPI/frontend và import trực tiếp `smartrecon.engine.run_reconciliation`. Notebook tạo EDA, biểu đồ L1–L4, phân tích group/split, oracle conservation, holdout metrics, ablation và benchmark từ dữ liệu thật trong repo; kiểm thử chống đường dẫn tuyệt đối và thất bại nếu bất kỳ cell nào lỗi.

Holdout 47 truth edges đạt edge precision `43/43 = 1,0000`, recall `43/47 = 0,9149`, F1 `0,9556`, group exact precision `43/43`, group recall `43/46`, candidate recall `47/47` và 0 false auto-confirm. Allocation MAE trên hợp predicted/truth edges là 14.893,62 VND, tổng absolute error 700.000 VND do các truth edges review-only được so với prediction bằng 0; các cạnh đã xác nhận đúng không lệch tiền. Thí nghiệm approve hai edges N:1 xác nhận chúng được đếm là reviewed-confirmed riêng và không làm tăng auto-confirm coverage. Benchmark profile 1.000 orders/998 bank rows, seed `20261016`, chạy 3,440 giây với peak `tracemalloc` 9.741.897 bytes trên máy kiểm thử; hashes, policy, phần cứng và giới hạn exact-filler được ghi tại `docs/EVALUATION_REPORT.md`.

Regression checkpoint: Ruff/format pass; 100 Python tests, 28 golden, 4 property và 19 frontend tests pass; frontend build pass, npm audit 0 vulnerabilities. `docker compose up --build -d` build lại backend thành công và `db`, `backend`, `frontend` đều healthy; không xóa named volume. Sau build, PostgreSQL còn 47 runs và API mở lại run `423395c5-1901-40c8-88ab-6926b38b0637` ở revision 2 thành công.

## Comprehensive QA và benchmark

### PostgreSQL concurrency và revisions

Script `scripts/qa_concurrency.py` tạo run synthetic `deff0a5b-690e-4f24-9857-e53448e7afae` và phát hai request approve độc lập cùng `expected_revision=0` qua hai threads được đồng bộ bằng barrier. Hai request hoàn tất trong 86–88 ms: đúng một request trả 200/commit revision 1 và request cạnh tranh trả 409 `STALE_REVISION`. Retry nguyên idempotency key/payload trả lại action cũ với `idempotent_replay=true`; tái sử dụng key với payload khác trả 409 và không tạo audit thứ hai.

Approve group M:N trả 409 `COMPLEX_GROUP_NOT_APPROVABLE` và rollback, không đổi revision. Sau reject ở revision 2, yêu cầu undo approval trước đó trả 409 `UNDO_DEPENDENCY_CONFLICT`; undo đúng action reject tạo revision 3. Audit cuối có đúng ba action `APPROVE_GROUP`, `REJECT_GROUP`, `UNDO_ACTION`. Oracle API tự cộng lại từng order/bank và toàn run ở revisions 0, 1, 2, 3; tất cả conservation đều hợp lệ. Excel revision 3 có 9 sheet, 0 formula cell và tổng allocation bằng dashboard.

Sau `docker compose up --build -d`, PostgreSQL còn 63 runs; run trên vẫn mở ở revision 3, conservation `true`, confirmed cash 66.531.000 VND và Excel 55.063 bytes tải lại thành công. Không xóa named volume.

### Browser E2E bốn viewport

Mỗi lượt Edge headless đi trọn demo → mapping → Health Gate → reconcile → dashboard/charts → detail → review approve → undo → export → mở lại run:

| Viewport | Run ID | Overflow ngang | Charts | Export | Review/undo | Mở lại |
|---|---|---:|---:|---:|---:|---:|
| 1440×900 | `51d58403-d88e-4640-9b77-44fd62c4570c` | Không | 2 | 200 / 54.662 bytes | PASS | PASS |
| 1366×768 | `e664073f-8aba-4ce1-abe9-dbcb88ae065d` | Không | 2 | 200 / 54.661 bytes | PASS | PASS |
| 768×1024 | `a281d311-42ea-40e2-bd03-755b5154875d` | Không | 2 | 200 / 54.660 bytes | PASS | PASS |
| 390×844 | `0510d3f6-6d39-4482-ba3a-92f15ea4b5cd` | Không | 2 | 200 / 54.663 bytes | PASS | PASS |

Desktop/tablet smoke xác minh tooltip Plotly bằng pointer. Ở viewport 390 px, CDP touch emulation không tạo Plotly hover layer ổn định nên gate dùng dữ liệu runtime của chart, nhãn/legend, tổng mẫu số, màu phân biệt, bounds và toàn bộ workflow; không báo rằng tooltip touch đã được kiểm chứng trong lượt này.

### Performance theo loại tình huống

`scripts/run_qa_benchmark.py --repeats 25` chạy cùng public core API, policy `2026-10-15`, seed 42, commit `325d4a94d6311e45d01773989d94f1f6408dfe45`, Python 3.12.14 trên Windows 11/AMD64 Family 25 Model 68. Truth chỉ được dùng ngoài engine để tách các feed benchmark. Thời gian là wall-clock mỗi run; memory là peak Python allocations từ `tracemalloc`:

| Scenario | Orders / banks | Mean | p95 | Peak |
|---|---:|---:|---:|---:|
| Strong reference | 3 / 3 | 13,01 ms | 13,90 ms | 1.097,8 KiB |
| Weak/ambiguous | 3 / 2 | 12,31 ms | 12,80 ms | 1.063,0 KiB |
| N:1 | 2 / 1 | 10,38 ms | 10,75 ms | 1.060,2 KiB |
| 1:N | 1 / 2 | 10,27 ms | 10,68 ms | 1.060,2 KiB |
| Subset search | 2 / 1 | 11,03 ms | 13,04 ms | 1.059,9 KiB |
| Nhiều proposal cạnh tranh | 6 / 4 | 16,33 ms | 21,46 ms | 1.063,2 KiB |

Benchmark 1.000 orders và hashes nằm trong `EVALUATION_REPORT.md`. Các microbenchmark nhỏ ở bảng trên dùng để so nhánh thuật toán, không phải tuyên bố throughput production; upload cap 100.000 rows vẫn chỉ là giới hạn bảo vệ đầu vào. Dashboard sau review đo 31,11 ms; Excel export 164,73 ms, 55.061 bytes trên run concurrency nói trên.

### Security regression

- Upload CSV/XLSX giữ kiểm tra extension, content type, kích thước/ZIP/header; client filename chứa `../` hoặc `..\` vẫn được lưu bằng tên server `orders.csv`/`bank.csv` dưới session root.
- Artifact identifiers chứa path separator và relative path `../../...` bị từ chối; path hợp lệ được resolve dưới configured root.
- Formula-like source text vẫn được ghi thành text, workbook QA có 0 formula cell; money/date cells giữ đúng kiểu.
- Docker log 30 phút gần nhất có 0 match private-key/API-key/credential-URL và 0 `Traceback`/`FATAL`/`panic`/unhandled exception. `.env`/`.env.*` bị Git ignore; chỉ `.env.example` được track.
- Không có auth/RBAC, HTTPS hoặc rate limiting trong demo. Đây là rủi ro nghiêm trọng nếu public deploy và là giới hạn đã công bố, không phải P0/P1 của phạm vi local demo đã phê duyệt.

Gate comprehensive QA: 24/24 golden fixtures có trong catalog và 28 golden tests pass; 103 Python tests, 4 property tests, 19 frontend tests, lint/format/build/npm audit và Docker health đều pass. Không phát hiện P0/P1 chưa xử lý; warning Plotly bundle và hai dependency/test-runtime warnings là non-blocking, được giữ công khai.

## Quy tắc VND có phần thập phân

Quyết định nghiệp vụ ngày 2026-10-15 đã được kiểm tra ở ba lớp. Unit tests xác nhận VND có phần thập phân bằng 0 vẫn hợp lệ với cả cấu hình dấu `.` và `,`, còn phần thập phân khác 0 sinh `MoneyParseError` chứa giá trị đầu vào. Regression riêng xác nhận BRL vẫn dùng `ROUND_HALF_UP` (`1.005 BRL` thành `101` minor units).

Integration tests đọc cả CSV và XLSX. Dòng `100000.5 VND` tạo `ORDER_PARSE_ERROR`/`BANK_PARSE_ERROR` mức `BLOCKING`, giữ số dòng 2 và sample `100000.5`, bị đưa vào `rejected_rows`, không xuất hiện trong canonical input. Trường `declared_fee=0.5` cũng bị chặn ở cả hai định dạng nên lỗi không thể bị bỏ qua qua call site tùy chọn. API tests xác nhận Health Gate trả tên file `orders.csv`/`orders.xlsx`, sheet `Sheet` cho XLSX, dòng 2 và raw `expected_amount=100000.5`. Lệnh kiểm tra trực tiếp trong backend container cũng trả `container_money_policy=PASS`.

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

Sau khi chốt quy tắc VND, `docker compose up --build -d` build thành công và ba service healthy. Trước/sau `docker compose restart`, số lượng giữ nguyên: `45 upload_sessions`, `40 runs`, `3.920 match_groups`, `3.640 allocation_edges`, `277 artifact_manifest`. Run đã lưu `76119213-5c6a-431d-b4c8-7a24a745cb9f` vẫn trả `67.865.000` phải thu, `66.431.000` cash phân bổ, `2.000` adjustment, `1.432.000` còn phải thu, conservation `true` và 0 violations.

## Cải tiến giao diện

- Luồng bốn bước dùng nhãn nghiệp vụ chính xác; upload là hành động chính, dữ liệu mẫu và mở lại phiên là lựa chọn phụ.
- EDA hiển thị số dòng/cột/ô trống/trùng lặp; ghép cột tách trường bắt buộc và bổ sung, có giá trị mẫu, phát hiện cột dùng lặp và giữ mã kỹ thuật ở lớp thông tin phụ.
- Kiểm tra chất lượng ưu tiên lỗi theo mức độ; drawer đọc có giới hạn hiển thị file, dòng, giá trị gốc/chuẩn hóa và không tự thay đổi trạng thái cảnh báo.
- Dashboard theo thứ tự Tổng quan → Phân tích → Tra cứu → Xuất báo cáo. Tra cứu hiển thị `đã tải/tổng`, tải từng trang 50 bản ghi và mở drawer nguồn–đối ứng–phân bổ–bằng chứng.
- KPI hiển thị phương trình phải thu với adjustment riêng; biểu đồ cột dùng tên phương pháp nghiệp vụ và tách nhóm đã xác nhận khỏi đề xuất kiểm tra.
- Focus state, semantic headings, labels, table captions, trạng thái bằng chữ và reduced-motion được bổ sung; không dùng màu làm tín hiệu duy nhất.

## Phạm vi và hạn chế đã biết

- Không có auth/RBAC, public HTTPS, external bank API, OCR, FX hoặc queue worker. Demo local không được xem là hệ thống xác thực danh tính người thao tác.
- Proposal trong review queue không tạo allocation và không đi vào confirmed KPI cho tới khi approve transaction đã commit; reject không tạo allocation và undo không xóa audit history.
- Frontend Plotly basic bundle còn lớn (~1,48 MB raw, ~487 KB gzip). Đây là tối ưu hiệu năng không chặn demo local; build vẫn pass.

## Release readiness, backup và restore

Checkpoint vận hành ngày 2026-10-16 chuyển migration sang job one-shot `migrate`: job chờ PostgreSQL healthy, chạy `alembic upgrade head` và thoát mã 0; backend chờ job hoàn tất rồi mới chạy Uvicorn. Backend image chạy user `app`, frontend image chạy user `nginx`; PostgreSQL không publish cổng. Lần build đầu đã phát hiện Nginx non-root không ghi được `/run/nginx.pid`; Dockerfile được sửa dùng `/tmp/nginx.pid`, build lại và frontend healthcheck đạt thay vì hạ yêu cầu non-root.

`compose.production.yaml` được validate và khởi động thật bằng project cô lập `smartrecon_prodcheck_20261016`: `db`, `backend`, `frontend` đều healthy, `migrate` `Exited (0)`, API health trả `ok`. Cổng thử chỉ bind loopback; project, network và hai volume thử được xóa sau khi đạt, không tác động stack chính.

Backup thật của run `deff0a5b-690e-4f24-9857-e53448e7afae` tạo custom-format PostgreSQL dump 570.875 bytes (SHA-256 `480ea869d36632564584cad94ca6e1559cce87a1febda7fab6a873e4ad726dd1`) cùng 482 artifact files, tổng 32.680.774 bytes. Restore drill dùng project ngẫu nhiên `smartrecon_restore_1fa8c95d82`, database/artifact volumes và cổng riêng. Sau restore, hệ thống đọc đúng revision 3, ba audit actions, 92 allocation edges tổng 66.531.000 VND, KPI cash 66.531.000 VND, conservation `true` và sinh lại workbook 55.062 bytes. Project/volumes thử được dọn sau khi kiểm tra; stack thật vẫn đọc cùng run/revision/KPI.

Sau `docker compose down` không kèm `-v` và `docker compose up -d`, ba dịch vụ dài hạn trở lại healthy, migration thoát mã 0. PostgreSQL còn 64 runs, 100 run revisions và 479 artifact manifest rows; run revision 3 nói trên vẫn có cash 66.531.000 VND và conservation `true`.

Regression cuối trước commit: Ruff lint/format pass; 103 Python tests pass (hai warning môi trường đã công bố), 28 golden tests, 4 property tests, 19 frontend tests, frontend lint/build và `npm audit` 0 vulnerabilities đều đạt. Evaluation smoke 1.000 orders/998 bank rows chạy 3,112 giây, hard-profile edge F1 `0,9961`, false auto-confirm count `0`; holdout F1 vẫn `0,9556`. Production build còn warning Plotly chunk lớn đã biết, không có test failure.

Clean-clone cuối lấy trực tiếp `origin/main` tại commit `454cad3e3bc7d66685879ca5830fa610bb891e38`, worktree sạch, dùng project/image tags/ports/volumes riêng. Ba service healthy và migration exit 0; run `9c23f1a7-da5b-44ea-8ecb-d2316968cce2` qua concurrency `[409, 200]`, ba audit actions, revision 3 và conservation đúng ở revisions 0–3. Sau `down`/`up` không xóa volume, database giữ `1 → 1` run, dashboard mở lại đúng revision 3/cash 66.531.000 VND, frontend HTTP 200 và XLSX HTTP 200/55.069 bytes. Clone vẫn sạch; project cùng volumes thử đã được xóa, stack chính không bị tác động. GitHub Actions run `38847228208` cho cùng commit có cả backend, frontend và containers job success.
