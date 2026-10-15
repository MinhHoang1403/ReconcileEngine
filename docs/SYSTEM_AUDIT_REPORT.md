# Báo cáo audit hệ thống SmartRecon

Ngày kiểm tra: 15/10/2026 (Asia/Ho_Chi_Minh)

Baseline: `4f6c375cac52adc08a29938e19b56b5cbcf5f097`

Phạm vi: toàn bộ Giai đoạn 1; không triển khai chức năng review/undo, xác thực doanh nghiệp, FX, ML/LLM hay chức năng Giai đoạn 2.

## 1. Kết luận điều hành

Kết quả tổng thể: **PASS có giới hạn đã nêu** cho phạm vi demo local Giai đoạn 1. Hai biểu đồ đã được sửa và kiểm tra trên bốn viewport. Oracle độc lập không phát hiện vi phạm bảo toàn tiền. Core, API, PostgreSQL, Excel, Docker, persistence và workflow trình duyệt đều đã được chạy thực tế.

Không có tuyên bố về độ chính xác 100% trên dữ liệu tài chính thật. Giới hạn upload 100.000 dòng chỉ là giới hạn bảo vệ đầu vào, không phải cam kết throughput đã được chứng minh.

## 2. Module đã kiểm tra

- Core: `domain/money.py`, `domain/invariants.py`, `engine.py`, `analytics/metrics.py`.
- Ingestion: readers, mapping, normalization, EDA, Health Gate và lineage/hash.
- Matching: strong reference, policy-constrained, RapidFuzz candidate, bounded group/split và resolver/allocation.
- Backend: schemas, upload/run/detail/export services, routers, SQLAlchemy models và Alembic migrations.
- Frontend: workflow App, mapping, Health Gate, Dashboard, hai chart, explorer, drawer và money formatting.
- Runtime: Compose, PostgreSQL, FastAPI, Nginx, named volumes, export và reopen saved run.
- Dữ liệu/QA: generator, 22 tình huống ground-truth được tách riêng, golden/property/integration/API/frontend/browser tests.

## 3. Phát hiện và thay đổi

| Mức | Trạng thái | Phát hiện / nguyên nhân gốc | Sửa đổi và bằng chứng hồi quy |
|---|---|---|---|
| P1 | FIXED | Hai bank row khác ID, cùng amount/date và không có `txn_ref` bị coi là re-import; cash thứ hai có thể bị loại khỏi eligibility. Fingerprint dùng chứng cứ amount/date quá yếu. | Chỉ tạo fingerprint re-import khi có stable `txn_ref`; test hai cash row hợp lệ cùng amount/date. |
| P1 | FIXED | Loại một dòng khỏi ID collision vẫn để Health Gate BLOCKED vì issue chỉ được gỡ khi loại toàn bộ dòng. | Collision được giải quyết khi còn tối đa một dòng; test exclusion một trong hai dòng trùng. |
| P1 | FIXED | Đơn giá trị 0 không có confirmed evidence bị tính là fully settled chỉ vì outstanding bằng 0. | KPI chỉ đếm `FULL`/`OVERPAID`; test `NO_CONFIRMED_RECEIPT` cho zero-value order. |
| P1 | FIXED | Pandas tự đổi tên header trùng trước validation, làm CSV/XLSX header trùng có thể lọt qua. | Kiểm tra header raw bằng `csv`/`openpyxl` trước Pandas; test cả CSV và XLSX. |
| P2 | FIXED | Chart lớp matching dùng bố cục khó đọc, tick dày và không giải thích denominator. | Horizontal grouped bars L1–L4 cố định, `tickmode:auto`, `nticks:6`, legend riêng, tooltip và empty state. |
| P2 | FIXED | Donut phụ thuộc thứ tự response, nhãn nhỏ có nguy cơ chồng và chưa tách `NOT_ELIGIBLE`. | Mapping status→label/color ổn định, legend số lượng/tỷ lệ, mẫu số eligible, note riêng và mismatch warning. |
| P2 | FIXED | Frontend biến dữ liệu thiếu thành 0 và có thể format integer ngoài `Number.MAX_SAFE_INTEGER` sai. | Formatter chung từ chối missing/non-finite/unsafe integer; bridge không tự xác nhận khi không thể biểu diễn an toàn. |
| P2 | FIXED | Exclusion API nhận feed hoặc số dòng không tồn tại, có thể lưu resolution không tác dụng. | Pydantic `Literal` cho hai feed và kiểm tra giới hạn dòng nguồn; API regression trả 422. |
| P2 | FIXED | 1.000 strong-reference pairs vượt 60 giây do regex được biên dịch lặp và vượt cache 512 pattern. | Biên dịch pattern đúng một lần mỗi run, giữ nguyên boundary semantics; sau sửa 1.000×1.000 hoàn tất 0,872 giây trên máy audit. |
| P3 | FIXED | `OVERPAY_RESIDUAL` không đồng nhất với label `OVERPAYMENT`; Excel thiếu nhãn `OVERPAID`. | Đồng bộ reason/status label giữa detail, Dashboard và Excel. |

Không thay đổi matching threshold, fee policy, công thức tiền hay expected value của golden fixtures.

## 4. Bằng chứng tái hiện và oracle độc lập

`tests/audit/test_system_oracles.py` tự cộng trực tiếp domain records, không gọi lại production KPI/conservation helper. Các phép kiểm tra gồm:

- từng edge không âm và thuộc confirmed group;
- từng order: expected = allocated + verified adjustment + outstanding;
- từng bank: eligible credit = allocated + unapplied;
- tổng run cho cả receivable và bank cash;
- layer counts được đếm lại từ từng group/rule/status;
- payment status được đếm lại từ map trạng thái từng order;
- `ORD00018`: 98.000 cash từ `TXN00016`, adjustment PSP 2.000, evidence `declared_fee:TXN00016`, outstanding 0.

Baseline được xác nhận độc lập:

| Thành phần | Kết quả |
|---|---:|
| Tổng phải thu | 67.865.000 VND |
| Cash đã phân bổ | 66.431.000 VND |
| Điều chỉnh PSP có chứng cứ | 2.000 VND |
| Còn phải thu | 1.432.000 VND |
| Conservation | PASS |

Golden/adversarial hiện bao phủ exact/timing/normalized/fuzzy, ambiguity, N:1, 1:N, partial, overpay, orphan, re-import, distinct same amount, fee có/không chứng cứ, debit, boundary, leading zero, formula injection, many-to-many review, out-of-window, currency, conflict, permutation và subset budget.

## 5. Input, money và Health Gate

- PASS: UTF-8/UTF-8-SIG, CSV/XLSX structure, header raw trùng/trống, leading-zero ID, explicit mapping, lineage/file/row hashes.
- PASS: tiền được parse bằng `Decimal`, sau đó chỉ dùng integer minor units; negative/non-finite/blank bị từ chối.
- PASS: quyết định nghiệp vụ VND đã được chốt ngày 2026-10-15: chỉ chấp nhận phần thập phân bằng 0; phần thập phân khác 0 sinh lỗi `BLOCKING`, giữ file/sheet/dòng/giá trị raw và không bị làm tròn hoặc đưa vào matching. BRL giữ nguyên `ROUND_HALF_UP`.
- PASS: BLOCKING chặn run; WARNING/INFO không tạo allocation; exclusion bắt buộc lý do và không tham gia core.

## 6. Matching, conflict và allocation

- PASS: L1 dùng full reference với token boundary; collision không tự confirm; hỗ trợ 1:1/N:1/1:N; M:N phức tạp là review-only.
- PASS: L2 amount/date chỉ là proposal nếu thiếu identity evidence.
- PASS: L3 RapidFuzz là ranking 0–100, không phải xác suất, không tạo effective allocation.
- PASS: L4 subset search bị chặn bởi block/group/combination budgets; exact sum đơn thuần vẫn là proposal; budget exhaustion sinh exception.
- PASS: confirmed participants không bị proposal yếu ghi đè; candidate conflicts được lưu; stable IDs/checksum không phụ thuộc thứ tự input trong cases đã kiểm tra.
- PASS: allocation không vượt order/bank; debit, gross report và duplicate-suspect không đi vào eligible cash; fee chỉ được adjustment khi có declared PSP evidence.

## 7. Backend/API và bảo mật phạm vi demo

- PASS: validation 400/404/409/422 theo workflow, upload extension/content/size, XLSX ZIP/macro limits, path được server kiểm soát và artifact path được resolve trong root.
- PASS: run snapshot/revision, groups và edges được persist; pagination và detail source rows hoạt động.
- PASS: export vô hiệu hóa strings-to-formulas/URLs; workbook audit có 0 formula cells.
- LIMITATION: không có authentication/RBAC theo đúng phạm vi. Nếu public deploy, đây là rủi ro truy cập dữ liệu nghiêm trọng và phải được xử lý trước khi mở mạng.
- LIMITATION: test suite báo deprecation warning của Starlette `TestClient`/httpx; chưa ảnh hưởng runtime.

## 8. Frontend và biểu đồ

Browser smoke bằng Microsoft Edge thật qua DevTools Protocol:

| Viewport | Overflow | Axis/legend bounds | Tooltip | Drawer/export/reopen | Kết quả |
|---|---|---|---|---|---|
| 1440×900 | Không | Trong card | Số thực | PASS | PASS |
| 1366×768 | Không | Trong card | Số thực | PASS | PASS |
| 768×1024 | Không | Trong card | Số thực | PASS | PASS |
| 390×844 | Không | Trong card | Số thực | PASS | PASS |

Runtime chart evidence: orientations `h/h`, `tickmode=auto`, `nticks=6`, không cấu hình `dtick`; bốn method label đầy đủ; donut values `[87,2,1,3,7]`, tổng 100; năm màu duy nhất, ổn định; tooltip mẫu `Đã xác nhận: 38 nhóm` và `87 đơn (87%)`.

Ảnh bằng chứng được giữ ngoài repository tại `%TEMP%\smartrecon-system-audit\` để không commit runtime artifacts lớn. Các file `charts-*` và `payment-chart-*` tương ứng bốn viewport.

## 9. Excel reporting

Workbook run `528e9d1e-75a3-4ceb-9ddb-e3f690cea9f1` được đọc độc lập:

- PASS: 9/9 sheet đúng contract.
- PASS: 100 orders, 98 bank rows, 89 confirmed groups, 9 proposals, 22 exceptions, 91 allocation edges.
- PASS: tổng Excel = Core = API = PostgreSQL: 67.865.000 / 66.431.000 / 2.000 / 1.432.000 VND; unapplied cash 1.105.000 VND.
- PASS: `00017` giữ số 0 đầu; source lineage có trong order/bank sheets.
- PASS: proposal group IDs không xuất hiện trong allocation edges; bank amount không bị nhân đôi bởi N:1.
- PASS: 0 formula cells; source formula-like text không được thực thi.

## 10. Docker và persistence

- PASS: `docker compose config --quiet`, image build, Alembic startup, ba healthcheck và Nginx proxy.
- PASS: PostgreSQL không publish cổng host; `pg_data` và `artifacts_data` là named volumes.
- PASS: phép thử restart chuyên biệt giữ nguyên 38/38 runs; lần rebuild cuối xác nhận 39 runs vẫn tồn tại, ba container healthy và saved run mở lại được với conservation true.
- PASS: export sau restart có toàn bộ cell value giống trước restart. SHA-256 file ZIP có thể khác do metadata đóng gói khi tái sinh; đây không phải khác biệt dữ liệu báo cáo.

## 11. Hiệu năng

Máy audit: AMD Ryzen 5 7535HS, 6 cores/12 logical processors, RAM 16,44 GB, Windows/WSL2 Docker. Dataset benchmark là các cặp VND 1:1 có unique full reference, chạy core trong một process:

| Quy mô orders × banks | Trước sửa |
|---:|---:|
| 100 × 100 | 0,063 s |
| 250 × 250 | 0,309 s |
| 500 × 500 | 1,345 s |
| 1.000 × 1.000 | timeout >60 s |

Sau khi reuse compiled regex, 1.000 × 1.000 hoàn tất **0,872 s** và tạo đúng 1.000 allocations. Kết quả này chỉ chứng minh profile strong-reference nêu trên. Weak candidates vẫn có vòng lặp orders×banks; subset search có guardrail nhưng không chứng minh tải 100.000 dòng. Vì vậy 100.000 vẫn chỉ là upload cap.

## 12. Kết quả kiểm thử

| Kiểm tra | Kết quả |
|---|---|
| Ruff check / format check | PASS |
| Python full suite | PASS — 68 tests |
| Golden suite | PASS — 26 tests (22 fixtures nghiệp vụ cùng kiểm tra contract) |
| Property/conservation suite | PASS — 4 tests |
| Frontend ESLint / Vitest | PASS — 17 tests |
| Frontend production build | PASS; còn warning Plotly chunk lớn |
| `npm audit` | PASS; 0 vulnerabilities |
| Compose build/health | PASS |
| Browser 4 viewports | PASS |
| Excel cross-check | PASS |
| Restart persistence | PASS |

## 13. Nguồn và loại quyết định

- Tài liệu chính thức: Python Decimal, Unicode NFKC, RapidFuzz, PostgreSQL, SQLAlchemy/Alembic, FastAPI/Pydantic, Plotly, Docker volumes và OWASP upload/formula injection, được liệt kê tại `docs/RESEARCH_REFERENCES.md`.
- Quy tắc nghiệp vụ dự án: money invariants, eligibility, L1–L4, fee evidence, status và denominator trong `MONEY_INVARIANTS.md`, `MATCHING_POLICY.md`, `DATA_CONTRACT.md`.
- Heuristic cấu hình: fuzzy threshold 85, Top-K 5, date window 3 ngày, group/block/search budgets. Không coi các giá trị này là kết luận nghiên cứu hay xác suất.

## 14. Hạn chế còn lại

1. Không đánh giá accuracy trên dữ liệu thật; synthetic/golden không đại diện đầy đủ nhiễu production.
2. Không có auth/RBAC, retention policy, backup/restore drill hay deployment public hardening trong phạm vi hiện tại.
3. Chưa benchmark end-to-end 100.000 dòng hoặc worst-case weak-candidate cross product.
4. Frontend Plotly bundle khoảng 1,519 MB raw / 498 KB gzip và còn build warning; không ảnh hưởng tính đúng.
5. Giá trị vượt JavaScript safe integer được chặn hiển thị thay vì hỗ trợ đầy đủ; API numeric contract cần đổi có chủ đích nếu phạm vi tiền yêu cầu lớn hơn.

## 15. Mức sẵn sàng

**PASS cho demo local Giai đoạn 1 và sẵn sàng dùng làm baseline kỹ thuật trước khi lập kế hoạch Giai đoạn 2**, với điều kiện không diễn giải thành chứng nhận production/public deployment. Các giới hạn auth, dữ liệu thật, tải 100.000 dòng và backup/restore phải được quyết định/đo riêng trước production.
