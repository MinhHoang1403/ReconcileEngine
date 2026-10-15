# SMART FINANCIAL RECONCILIATION & ANALYTICS
## BẢN KẾ HOẠCH KỸ THUẬT & TRIỂN KHAI CUỐI CÙNG — V3.0

> **Ngày lập:** 14/10/2026  
> **Tình trạng:** Đặc tả triển khai được hoàn thiện từ các bản đề xuất; **chưa phải báo cáo phần mềm đã được xây dựng hoặc kiểm thử**. Các chuẩn nghiệm thu đã chốt, các ngưỡng dự đoán/hiệu năng vẫn cần xác thực khi chạy.  
> **Quyết định có hiệu lực:** Xây dựng **dự án mới hoàn toàn**, một repository độc lập; chỉ nghiên cứu ý tưởng/dữ liệu tham khảo từ `https://github.com/dpduc/ReconEngine`, **không fork và không kế thừa mã nguồn/kiến trúc bắt buộc**.  
> **Tên làm việc:** Smart Financial Reconciliation & Analytics (SmartRecon).  
> **Phạm vi sản phẩm ưu tiên:** Đối soát **2 nguồn** — khoản phải thu/đơn hàng nội bộ và giao dịch ngân hàng/PSP — có thanh toán gộp, chia nhiều lần, xác minh thủ công, dashboard và export.  
> **Mức độ sẵn sàng:** Sẵn sàng đưa vào giai đoạn M0 (khởi tạo repo/spec/test fixtures). Không được coi là đã hoàn thành các mốc triển khai M1–M8.

---

# MỤC LỤC

1. Quyết định chính và kết quả đối chiếu ba tài liệu
2. Bài toán nghiệp vụ, định nghĩa và ranh giới
3. Mục tiêu, tiêu chí thành công, phạm vi MVP và nâng cấp
4. Kiến trúc tổng thể; lựa chọn công nghệ có lý do
5. Chiến lược dữ liệu Olist, synthetic, nguồn gốc và giấy phép
6. Thiết kế dataset, scenario, phân bố và ground truth
7. Hợp đồng dữ liệu nhập, raw/canonical schema và mapping
8. Chuẩn hóa số tiền, thời gian, định danh và nguyên tắc tiền
9. Data Quality/Health Gate và quy trình upload
10. Mô hình miền nghiệp vụ: group, edge, evidence, residual
11. Waterfall 4 lớp + giai đoạn exception, tránh tự ghép sai
12. Chi tiết từng phương pháp matching, blocking và giải xung đột
13. Quản lý phí, gross/net, thanh toán thiếu/thừa và refund
14. Human-in-the-loop: review, undo, audit, trạng thái
15. Công thức KPI và hợp đồng Dashboard
16. Thiết kế cơ sở dữ liệu và vòng đời run
17. FastAPI: contract, endpoints, lỗi và ví dụ response
18. Frontend React: màn hình, luồng sử dụng, biểu đồ và UX
19. Jupyter Notebook: bố cục nghiên cứu, phép thử, đánh giá
20. Metrics, protocol đánh giá, tránh leakage và benchmark
21. Quy hoạch source code, mô-đun, interface và dependency
22. Kiểm thử tự động, fixture nghiệp vụ và điều kiện khóa release
23. Hiệu năng, độ phức tạp, giới hạn và bảo mật
24. Roadmap M0–M8, phụ thuộc, đầu ra và tiêu chí nghiệm thu
25. Chia việc, quản trị Git, CI và quy trình dùng coding agent
26. Checklist trước khi code, kịch bản demo và Definition of Done
27. Rủi ro, giả định, những việc cố ý chưa làm
28. Nguồn tham khảo, tài liệu bắt buộc và quyết định cuối cùng
29. Phụ lục A — Các quy tắc khóa chặt triển khai và diễn giải trạng thái
30. Phụ lục B — Golden test cases, oracle và kiểm tra bảo toàn
31. Phụ lục C — Ma trận truy vết yêu cầu → milestone → kiểm thử
32. Phụ lục D — Giao việc Codex theo milestones, không code ồ ạt
33. Phụ lục E — Checklist bàn giao & thứ tự các việc cần làm đầu tiên

---

# 1. QUYẾT ĐỊNH CHÍNH VÀ KẾT QUẢ ĐỐI CHIẾU

## 1.1. Ba nguồn lập kế hoạch đã được đối chiếu

**Nguồn A — Kế hoạch dự án mới độc lập V1.0:** quy định xây mới 100%, dùng Olist + synthetic, Python core độc lập, FastAPI, React, SQLite, group/edge, evaluation và lộ trình M0–M7.

**Nguồn B — Đề xuất mới (DuckDB / RapidFuzz / Waterfall / Streamlit):** bổ sung DuckDB cho phân tích, waterfall, regex, fuzzy, kiểm soát theo màu, review UI, data generator 1.000 ca, Excel nhiều sheet và ý tưởng master prompt.

**Nguồn C — ReconEngine của dpduc:** **chỉ là tài liệu tham khảo nghiệp vụ/dataset**. Tham khảo các khái niệm health checks, traceability, review, reproducibility, Olist và trường hợp ngoại lệ. Không nhận benchmark của repo làm bằng chứng chất lượng dự án mới.

## 1.2. Các điểm từ đề xuất mới được giữ

- DuckDB để đọc/xử lý/tổng hợp dữ liệu dạng bảng và hỗ trợ SQL phân tích.
- Pandas cho adapter CSV/XLSX và xử lý ở các biên; `openpyxl` để đọc/ghi Excel nhiều sheet có định dạng.
- Regex + RapidFuzz cho chuẩn hóa/trích xuất/candidate ranking; `itertools` **chỉ** được dùng trong những block nhỏ có giới hạn.
- Waterfall nhiều lớp, giải thích từng quy tắc, chỉ chạy tiếp trên **pool chưa được xác nhận**.
- Bảng review màu xanh/vàng/đỏ, xác nhận/từ chối có lưu audit.
- Notebook thể hiện từ EDA đến phân tích thuật toán; bộ dữ liệu mẫu có scenario và ground truth tách biệt.
- FastAPI làm service API, tài liệu OpenAPI/Swagger, export báo cáo Excel.

## 1.3. Những điểm được sửa bắt buộc

| Trong đề xuất mới | Vấn đề | Quyết định V2 |
|---|---|---|
| `SPLIT_1_TO_N` mô tả **nhiều đơn → một bank** | Đặt tên ngược nghĩa | `MANY_ORDERS_ONE_BANK` (N:1); `ONE_ORDER_MANY_BANKS` (1:N) |
| Waterfall gọi là 4 lớp nhưng ghi 5 tầng | Mơ hồ thứ tự và cách đếm | **4 lớp suy luận liên kết** + giai đoạn **Exception/Residual**, không tính exception là matching layer |
| 🟢 confidence `99–100%` = chính xác tuyệt đối | Điểm luật không phải xác suất | Tách `link_status`, `payment_status`, `review_status`; `rule_score` chỉ để **xếp hạng**, không tự phát biểu % xác suất |
| `ground_truth_case` trong file nội bộ đầu vào | Nguy cơ thuật toán nhìn thấy đáp án | Ground truth **chỉ** ở thư mục research, tách ra khỏi hai feed upload/feature matching |
| Mọi lệch 1,5–2% là phí | Không đủ chứng cứ nghiệp vụ | Chỉ công nhận phí qua chứng từ/biểu phí có phiên bản; trường hợp thiếu bằng chứng chuyển review |
| `float` để đối chiếu tiền | Sai số biểu diễn và rounding | `Decimal` tại ingestion, **integer minor units** trong core; quy tắc làm tròn được cấu hình |
| `ref_digits` là chốt chặn đủ cho fuzzy | Số cuối có thể trùng hoặc thiếu | Chỉ dùng như **một ràng buộc bổ sung**; kiểm chứng toàn ID, biên token, uniqueness và nguồn chứng cứ |
| Dùng `combinations` trên dữ liệu chưa khớp | Bùng nổ tổ hợp, xung đột nhóm | Blocking + giới hạn `k`, giới hạn `block_size`, budget + kiểm tra duy nhất/không double-use |
| Kết hợp 75%+…+2% orphan bank thành 100% | Orphan bank không phải **đơn hàng** | Tách **phân bố case theo đơn** và **số orphan bank bổ sung**, mẫu số khác nhau |
| Dùng DuckDB `reconcile.duckdb` làm kho duyệt | OLAP khác lưu giao dịch nghiệp vụ | **DuckDB = query/analytics**; **SQLite/SQLAlchemy = trạng thái review/run/audit** trong demo |
| `APPROVE` một dòng → 🟢 | Gộp/chia liên quan nhiều bản ghi | Approve/reject ở **group + allocations**, transaction atomic + kiểm tra conflict |
| Streamlit và React đều là FE chính | Hai sản phẩm dễ phân kỳ | **React chính thức**; Streamlit **không bắt buộc**, chỉ dùng spike/prototype nếu thực sự cần |
| Tên *Internal Ledger* mang nghĩa sổ cái | Dữ liệu mẫu chủ yếu là đơn/khoản phải thu | Tên giao diện **Đơn hàng/Khoản phải thu nội bộ**; gọi *ledger* chỉ khi người dùng map dữ liệu đúng loại |

## 1.4. Chốt stack chuẩn

| Layer | Chọn cho phiên bản đầu | Lý do / giới hạn |
|---|---|---|
| Ngôn ngữ core | Python 3.12 | Phổ biến, hệ sinh thái data, đủ phù hợp |
| Ingest/biên | Pandas + openpyxl; PyArrow/Parquet tùy chọn | Xử lý CSV/XLSX, preserve IDs, export đa sheet |
| SQL analytics | DuckDB | Tốt cho scan/aggregation/join theo lô; **không khẳng định nhanh hơn SQLite 10–50 lần trong mọi trường hợp** |
| Matching | Python regex, RapidFuzz, DuckDB SQL, cấu trúc conflict graph nhỏ | Kết hợp xác định + fuzzy ứng viên + nhóm có kiểm soát |
| Tiền tệ | `Decimal` + `int` minor units | Conservation, tránh float làm chuẩn nghiệp vụ |
| Domain persistence | SQLite + SQLAlchemy + Alembic | MVP một môi trường đơn giản, transaction cho review và audit |
| API | FastAPI + Pydantic + Uvicorn | Contract, validation, OpenAPI, upload và stream export |
| Website | React + TypeScript + Vite | UI tương tác, điều hướng, component review, lịch sử |
| Charts | Plotly.js (React wrapper) **hoặc** Recharts; chốt **Plotly.js** | Giữ tư duy trực quan từ đề xuất mới; FE chỉ render dữ liệu backend cấp |
| Notebook | Jupyter + cùng package `smartrecon` | Không có engine thứ hai |
| Tooling | `uv` + `pyproject.toml`, Ruff, pytest, GitHub Actions | Lock dependency, lint, regression; hỗ trợ pip như fallback |
| UI test | Playwright smoke/E2E | Chạy luồng upload→review→export |

**Quan trọng:** Các thư viện/tốc độ cụ thể phải được benchmark trên dữ liệu và cấu hình máy thực tế. DuckDB hiện hỗ trợ đọc `.xlsx`, nhưng vẫn cần kiểm soát lỗi kiểu dữ liệu/Excel; ta dùng adapter ingestion thống nhất thay vì để định dạng đầu vào quyết định logic nghiệp vụ.

---

# 2. BÀI TOÁN NGHIỆP VỤ, ĐỊNH NGHĨA VÀ RANH GIỚI

## 2.1. Hai nguồn thực sự được đối soát

- **Nguồn A — `internal_receivables`**: đơn hàng hoặc các khoản phải thu, có ID, số tiền phải thu, loại tiền, ngày, trạng thái. Một đơn có thể có nhiều khoản thanh toán.
- **Nguồn B — `bank_transactions`**: các **credit** phát sinh trên sao kê ngân hàng, hoặc các dòng **PSP settlement**. Một dòng bank có thể đại diện một khoản khách chuyển hoặc nhiều khoản được cổng thanh toán chi trả gộp; phải khai báo `source_profile`.

Tên `internal_ledger` trong đề xuất mới được hỗ trợ như nhãn nhập liệu, nhưng engine **không tự tuyên bố thực hiện đối soát sổ cái kế toán**: không có chứng minh số dư đầu/cuối kỳ, Nợ/Có, journal entry hoặc thanh toán thực tế đã hoàn thành tại ngân hàng.

**Hai nguồn đối soát không nhất thiết cùng độ hạt:** `order` là nghĩa vụ phải thu; `bank transaction` là dòng tiền đã ghi nhận. Khả năng N:1 và 1:N là yêu cầu nền tảng, không phải tính năng vá thêm.

## 2.2. Tình huống cần hiểu đúng

- **ONE_TO_ONE (1:1):** O1 300.000 ↔ B1 300.000.
- **MANY_ORDERS_ONE_BANK (N:1, gộp):** O1 300.000 + O2 200.000 ↔ B1 500.000.
- **ONE_ORDER_MANY_BANKS (1:N, trả nhiều lần):** O3 600.000 ↔ B2 200.000 + B3 400.000.
- **PARTIAL:** O4 500.000 ↔ B4 490.000; còn thiếu 10.000 **nếu liên kết có đủ bằng chứng**.
- **OVERPAY:** O5 500.000 ↔ B5 520.000; phân bổ 500.000, dư 20.000 **không được biến mất**.
- **MISSING EVIDENCE:** Có O6 nhưng chưa xác nhận được bank tương ứng. Giao diện nói *chưa tìm thấy bằng chứng thu*, không khẳng định chắc khách không trả.
- **ORPHAN BANK:** Có B7 nhưng chưa xác định được đơn tương ứng.
- **AMBIGUOUS:** Hai đơn có cùng tiền/ngày, memo thiếu mã; đề xuất ứng viên, **không chốt tự động**.
- **FEE:** PSP nhận ròng 98.000 cho nghĩa vụ tổng 100.000; chỉ hạch toán phí 2.000 nếu hợp đồng/biểu phí/chứng cứ phù hợp.
- **REFUND/DEBIT:** Tiền ra, hoàn trả, chargeback: **không** chạy như credit thường; để classification/review hoặc extension riêng.

## 2.3. Phân biệt ba trục trạng thái

1. `link_status`: mức xác lập **mối liên kết** (`CONFIRMED`, `PROPOSED`, `UNMATCHED`, `REJECTED`).
2. `payment_status`: mức đáp ứng **số tiền phải thu** (`FULL`, `PARTIAL`, `OVERPAID`, `NO_CONFIRMED_RECEIPT`, `UNKNOWN`, `NOT_ELIGIBLE`).
3. `review_status`: xử lý thủ công (`OPEN`, `APPROVED`, `REJECTED`, `NEEDS_MORE_INFO`, `UNDONE`).

Vì vậy một mối liên kết có thể `CONFIRMED + PARTIAL`: xác định được khoản trả nhưng số tiền **chưa đủ**. Dashboard màu xanh chỉ đại diện *đã được xác minh đúng trạng thái* hoặc *khớp đủ theo chính sách*, không đánh đồng "link đã tìm ra" và "đã trả đủ".

---

# 3. MỤC TIÊU, TIÊU CHÍ THÀNH CÔNG VÀ PHẠM VI

## 3.1. Các luồng phải hoàn thành

1. Người dùng mở website bằng trình duyệt, không cần dùng notebook.
2. Upload **2 file** CSV/XLSX, hoặc **1 workbook XLSX có 2 sheets** rồi chọn sheet tương ứng; không yêu cầu ground truth cho vận hành thông thường.
3. Preview dữ liệu, mapping cột; Health Gate với lỗi chặn/khuyến cáo và lý do.
4. Chọn profile/cấu hình hợp lệ, ấn **Chạy đối soát**.
5. Engine chạy đầy đủ exact, constrained, fuzzy candidates, N:1, 1:N, unresolved; có audit/explain.
6. Dashboard thống kê đúng số đơn, số bank rows, số tiền được phân bổ, dư ngân hàng và khoản phải thu còn lại.
7. Review các đề xuất ở **cấp nhóm**; chấp nhận/từ chối, lưu note, re-evaluate, undo.
8. Export XLSX/CSV; xem lại run và cấu hình với đủ nguồn truy vết.
9. Notebook dùng lại cùng engine, kiểm thử trên bộ dữ liệu có nhãn.

## 3.2. Trong phạm vi MVP / MVP+

**P0 — bắt buộc:** CSV/XLSX, mapping, health, exact 1:1, N:1, 1:N, partial/over, orphan, ambiguous, fees **được phân loại an toàn**, reviewer approve/reject/undo, Excel export, dashboard, notebook pair-level evaluation, demo generator, tests.

**P1 — nên có trong bản trình diễn hoàn chỉnh:** fuzzy text ranking có giải thích, export chi tiết 7–9 sheets, run history, filters, timer/performance profile, VN synthetic, repeatable hard benchmark, UI tiếng Việt nhất quán.

**Phase 2, không chặn P0:** 3PL/COD, tỷ giá ngoại tệ/FX, đa ngân hàng/số dư, nhiều-nhiều tổng quát, real bank API, OCR/PDF sao kê, thông báo, email, enterprise RBAC, PostgreSQL, AI/LLM hỗ trợ (không tự quyết định tiền), Docker deployment nhiều tiến trình.

## 3.3. Các tiêu chí chất lượng không thể đánh đổi

- **Correctness trước coverage:** không tăng số dòng xanh bằng cách tự chốt cặp mơ hồ.
- **No hidden mutation:** raw file và raw row nguyên vẹn.
- **Conservation:** tiền được phân bổ đúng một lần, residual không mất.
- **Explainable:** mọi auto/match đề xuất có rule ID, bằng chứng, thời điểm, delta, lý do tiếng Việt.
- **Reproducible:** cùng input bytes + mapping + config + rule version + seed ⇒ cùng kết quả nghiệp vụ.
- **Truth separation:** engine và website bình thường không bao giờ xem ground truth.
- **Format-independent:** cùng bản ghi hợp lệ từ CSV/XLSX phải cho cùng kết quả canonical/engine.
- **Safe default:** giả định thiếu bằng chứng ⇒ review/unmatched, không tự suy diễn phí/hạch toán.

---

# 4. KIẾN TRÚC HỆ THỐNG CHỐT ĐỂ XÂY MỚI

```text
  Người dùng qua trình duyệt
              │
     React + TypeScript SPA
     - Upload / Mapping / Health
     - Configuration & Run
     - Dashboard / Review / History / Export
              │ HTTP JSON / multipart
              ▼
           FastAPI
     - File validation/session
     - API contract and pagination
     - Review transaction / export
              │
       ┌──────┴───────────────┐
       ▼                      ▼
  Python package         SQLAlchemy
  smartrecon             SQLite app.db
  (SINGLE CORE)           runs/configs
  normalize → quality     review/audit
  → candidates            revisions
  → allocation            user demo state
  → exceptions
  → metrics/report
       │
       ├── Pandas / OpenPyXL: input/output adapter
       ├── DuckDB: set joins, blocking, analytical queries
       ├── Regex / RapidFuzz: references and fuzzy scores
       └── Artifacts/Parquet: raw snapshot, canonical, results
              ▲
              │ direct import SAME public API
       Jupyter Notebook / CLI / tests
              ▲
      Olist observed + synthetic generator
```

## 4.1. Phân vai DuckDB và SQLite

**DuckDB**: dùng memory query hoặc file trung gian/cached analytical tables để kiểm tra dữ liệu, join/blocking, dataset profiling, aggregation, candidates và benchmark. Có thể đọc CSV/Parquet và `.xlsx` qua hỗ trợ phù hợp; adapter đầu vào chịu trách nhiệm schema nhất quán. Tránh thiết kế một DuckDB file dùng làm nơi ghi liên tục các hành động review đa request.

**SQLite**: nguồn sự thật của **trạng thái ứng dụng** trong MVP: `runs`, config snapshot, `review_actions`, `run_revisions`, group decisions, artefact manifests. Review phải giao dịch atomic, kiểm tra version. Các kết quả lớn lưu artifact files/parquet dưới `storage/runs/{run_id}/` thay vì ép hàng trăm nghìn rows vào JSON/SQLite.

**Quy tắc**: DuckDB có thể chạy **không cần database server**, nhưng không đồng nghĩa đảm bảo nhanh gấp 10–50 lần trong tất cả workload. Tối ưu sau profiling. Với nhiều instance/web server thì cấu trúc lưu state cần nâng cấp.

## 4.2. Vì sao không lấy Streamlit làm FE chính?

Streamlit rất hợp demo/research một người và `st.data_editor` giúp thử review sớm. Tuy nhiên, yêu cầu người dùng là **website full stack** với API, run history, multi-step upload/review và bộ UI mở rộng. Để tránh tạo hai giao diện cạnh tranh, V3 chốt:

- **React SPA = giao diện sản phẩm duy nhất phải hoàn thành.**
- **FastAPI = lớp HTTP duy nhất.**
- Notebook/CLI = nghiên cứu và kiểm thử, không thay thế sản phẩm.
- Có thể tạo một trang Streamlit **spike dùng nội bộ** để nghiên cứu biểu đồ, nhưng không trong acceptance criteria; không nhân bản matching logic hoặc thêm vào production repo nếu không cần.

---

# 5. DỮ LIỆU OLIST VÀ CHÍNH SÁCH NGUỒN GỐC

## 5.1. Bộ dữ liệu tham khảo

Repo bạn cung cấp có thư mục `brazil ecom/` với 9 CSV Olist gốc, và các bộ feed được sinh bằng module riêng của repo. Bộ Olist cũng được công bố tại `https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`.

| Dataset nguồn | Dùng như thế nào trong dự án mới |
|---|---|
| `olist_orders_dataset.csv` | `order_id`, thời gian đặt/duyệt, trạng thái; chọn mẫu thực tế |
| `olist_order_items_dataset.csv` | `price + freight_value` theo order để nghiên cứu số tiền dự kiến |
| `olist_order_payments_dataset.csv` | Giữ **từng dòng** `payment_sequential`, `payment_type`, `payment_installments`, `payment_value` trong nghiên cứu trước khi tổng hợp |
| `olist_customers_dataset.csv` | Customer metadata khi cần EDA/blocking theo cùng mã; **không giả tạo tên người gửi từ ID** |
| 5 CSV còn lại (products/sellers/reviews/geo/translation) | EDA tùy chọn, không đưa vào engine nếu không có ý nghĩa matching |

**Olist không có sao kê ngân hàng thực và cũng không có báo cáo PSP settlement thực.** `bank_transactions.csv` cho benchmark là **synthetic** và phải ghi rõ nguồn/transform trong manifest. Không được lấy `payment_installments` làm số lần bank chuyển khoản. Không tự suy ra khoản lệch item-total/payment-total là người mua chuyển thiếu; khác biệt có thể do quy tắc nghiệp vụ chưa mô hình hóa.

## 5.2. Độc lập mã nguồn; hợp pháp khi dùng dữ liệu

- Có thể **tham khảo cấu trúc dữ liệu/senario và dùng dữ liệu được cấp phép phù hợp**; không sao chép code của repo để tái sử dụng mà chưa kiểm tra license/quyền.
- Dữ liệu Olist trên Kaggle tại thời điểm soạn tài liệu hiển thị **CC BY-NC-SA 4.0**. Khi tái phân phối **dữ liệu dẫn xuất**, cần đáp ứng yêu cầu ghi công, giới hạn phi thương mại và ShareAlike nếu áp dụng; xác minh điều khoản trước khi xuất bản/thương mại hóa.
- **Code license** của repo người bạn khác với **dataset license**; không đồng nhất hai thứ.
- Ưu tiên `scripts/prepare_olist.py` đọc dữ liệu người dùng tự tải từ Kaggle, có README attribution, thay vì commit toàn bộ CSV gốc vào repo mới. Dữ liệu synthetic-only không dựa trên Olist có thể công bố theo điều khoản riêng do nhóm xác định.
- Dữ liệu thật của người dùng có thể chứa thông tin tài chính/cá nhân; ví dụ công khai phải dùng sample vô danh/synthetic và không push raw inputs lên Git.

## 5.3. Profiles phân biệt minh bạch

| Profile | Ngữ cảnh | Tiền / năm | Mục đích |
|---|---|---|---|
| `olist_observed_research` | Olist raw | BRL / 2016–2018 | Nghiên cứu dữ liệu thực, **không có bank truth** |
| `olist_derived_demo` | Orders chọn từ Olist + bank sinh | BRL / lịch sử gốc | Demo 80–120 orders/cases có nhãn |
| `olist_derived_hard` | Olist + disturbances, conflicting candidates | BRL / lịch sử gốc | Đánh giá 1.000–3.000 orders |
| `vn_synthetic_demo` | Dữ liệu giả lập độc lập | VND / 2026 | Demo tình huống VN, mã `DH...`, memo tự do |
| `performance_scale` | Synthetic stress + Olist sampling | Một currency/profile/run | Đo tài nguyên 100–100.000+ rows |

**Không join trộn BRL lịch sử và VND 2026**, không gán người gửi tên thật cho Olist khi nguồn không có. Một run MVP chỉ dùng **một currency**; khi hai feed bất nhất currency, báo issue/review/block có chỉ dẫn.

---

# 6. THIẾT KẾ BỘ DỮ LIỆU VÀ GROUND TRUTH

## 6.1. Người dùng phải upload bao nhiêu file?

**Thao tác thông thường:** 2 nguồn logic, gồm `internal_receivables.csv|xlsx` và `bank_transactions.csv|xlsx`; có thể là 1 workbook `sample_reconciliation.xlsx` với **2 sheet** được chọn. Ground truth không upload vào quy trình bình thường.

**Chế độ research/evaluation:** bên cạnh hai feed có **truth edges + truth cases + manifest** lưu ngoài nguồn input. `manifest.json` không phải feed thứ ba.

## 6.2. Bộ data tiêu chuẩn cần sinh

```text
data/
  raw/olist/                         # Không commit nếu ràng buộc license/dung lượng
  demo/olist_derived_demo/
    internal_receivables.csv
    bank_transactions.csv
    sample_reconciliation.xlsx      # 2 sheet cùng dữ liệu
    truth_edges.csv                  # KHÔNG gửi vào engine
    truth_cases.csv                  # KHÔNG gửi vào engine
    manifest.json
  demo/vn_synthetic_demo/           # cấu trúc tương tự
  benchmark/olist_derived_hard/     # generated, versioned manifests
  benchmark/performance_scale/      # generated
```

**Bốn thành phần trên thuộc một profile đánh giá nhưng không phải 4 file cần upload website.** Data generator tạo input + truth + manifest; bài test xác nhận truth **không rò vào cột input**.

## 6.3. Thiết kế scenario và tỷ lệ mẫu, không lẫn mẫu số

**Đề xuất cho profile `evaluation_hard`:** chọn **1.000 anchor orders** (nếu chọn 2.000–3.000 thì giữ tỷ lệ tương ứng). Sau đó sinh số **bank rows biến động** theo quan hệ N:1 / 1:N; orphan bank là số dòng bổ sung.

| Scenario (trên anchor orders) | Tỷ lệ mục tiêu | Ghi chú |
|---|---:|---|
| `EXACT_REF` | 60% | Khớp định danh + tiền; dùng làm baseline |
| `TIMING_T_PLUS_N` | 8% | Định danh mạnh, ngày ghi có T+1…T+3 |
| `NORMALIZED_REF` | 6% | Case/hyphen/spacing; exact sau normalize |
| `FUZZY_OR_TYPO_REF` | 4% | OCR 0/O, thiếu ký tự; đề xuất, không auto |
| `FEE_DEDUCTED_PSP` | 5% | Settlement có fee hypothesis/evidence policy |
| `MANY_ORDERS_ONE_BANK` | 4% | Tính theo **số order tham gia**, số group ít hơn |
| `ONE_ORDER_MANY_BANKS` | 3% | Mỗi order có 2–3 bank credits |
| `PARTIAL_UNDERPAY` | 3% | Mã mạnh nhưng tiền chưa đủ |
| `OVERPAY` | 2% | Bank cash lớn hơn phải thu; residual |
| `ORPHAN_INTERNAL` | 2% | Không tạo counterpart bank |
| `AMBIGUOUS_CANDIDATES` | 2% | Trùng amount/time, thiếu ID, đối ứng có thể có |
| `STATUS_OR_DIRECTION_EXCEPTION` | 1% | Pending/canceled hoặc dòng thiếu data, loại eligibility |
| **TỔNG** | **100%** | Đây là **target quotas cho order-level assignment**, không phải bank percentages |

**Bổ sung không lấy khỏi 100% order quotas:** sinh khoảng **2% orphan bank rows** so với số bank rows đủ điều kiện sau khi tạo, và khoảng **1% duplicate-import suspicion fixtures** trên **bank rows** (có thể overlap). Số này là cấu hình benchmark, không là quy luật thực tế. **Một scenario target không đảm bảo đúng số group khi group có 2–3 orders:** generator phân bổ ca theo block/group rồi xác nhận quota order-level, ghi sai lệch thực tế trong manifest.

**Phân bố này là đề xuất mới để khó hơn mẫu 75% exact, không phải tỷ lệ được quan sát từ Olist.** Demo 80–120 orders nên chọn cố ý ít nhất 1–3 ca của mỗi nhóm, không áp tỷ lệ máy móc.

## 6.4. Bắt buộc có ít nhất 16 fixture nghiệp vụ

1. Exact ref 1:1 tiền/ngày đúng.
2. Strong ref, T+1 hoặc T+3, tiền đúng.
3. Ref normalize hyphen/space/case.
4. Ref typo/fuzzy, digits có thể đủ nhưng vẫn phải review.
5. Same amount/date, **hai** order cạnh tranh một bank, không auto.
6. N:1 với **hai refs rõ ràng** và tiền tổng đúng.
7. N:1 **không có refs**, giống ngày/tiền: chỉ proposed, nếu nhiều subset thì ambiguous.
8. 1:N với **hai bank refs rõ cùng order** và tổng đủ.
9. Partial có strong ref, order 500, bank 490.
10. Overpay có strong ref, order 500, bank 520.
11. Orphan internal.
12. Orphan bank.
13. Duplicate import: cùng `source_transaction_id` và fingerprint (tùy bank semantics).
14. Two legitimate credits cùng amount/date nhưng **bank identity khác**.
15. PSP fee 2% có policy; bank transfer thiếu 2% không được tự coi là PSP fee.
16. Refund/debit không được ghép thành payment credit.
17. `DH01` không ghép `DH010` (false substring).
18. Conflict: cùng bank bị hai group đề xuất/approve; từ chối auto double-use.
19. Khác currency hoặc không có amount basis rõ.
20. Excel scientific notation/leading zeros/date format và CSV `=HYPERLINK(...)` khi export.

## 6.5. Ground truth được thiết kế như thế nào?

**`truth_edges.csv`** (thật theo scenario generator):

```csv
case_id,truth_group_id,order_id,bank_txn_id,allocated_cash_minor,currency,truth_relation
CASE_006,G_006,O001,B001,300000,VND,MANY_ORDERS_ONE_BANK
CASE_006,G_006,O002,B001,200000,VND,MANY_ORDERS_ONE_BANK
CASE_008,G_008,O003,B002,200000,VND,ONE_ORDER_MANY_BANKS
CASE_008,G_008,O003,B003,400000,VND,ONE_ORDER_MANY_BANKS
```

**`truth_cases.csv`** giữ cả ca **không có edge**:

```csv
case_id,scenario,order_ids,bank_txn_ids,expected_link_status,expected_payment_status,note
CASE_011,ORPHAN_INTERNAL,O011,,UNMATCHED,NO_CONFIRMED_RECEIPT,no_bank_generated
CASE_012,ORPHAN_BANK,,B012,UNMATCHED,UNKNOWN,no_order_generated
```

Các ví dụ là minh họa cấu trúc; định dạng `order_ids`/`bank_txn_ids` nên dùng bảng quan hệ dài hoặc JSON được document rõ, tránh chuỗi phân tách mơ hồ. **Để test fee và overpay**, bổ sung truth cho `verified_adjustment_minor`, `unapplied_bank_cash_minor`, `residual_receivable_minor`; không nhét phí vào `allocated_cash_minor`.

**`manifest.json`** tối thiểu: `dataset_id`, `profile`, `generator_version`, `seed`, `source_file_sha256`, `generated_file_sha256`, `source_semantics`, `observed_vs_synthetic_columns`, `scenario_target_and_realized_counts`, `currency`, `timezone`, `rounding_policy`, `truth_version`.

## 6.6. Ngăn đáp án rò rỉ vào matching

- Hai feed upload **không chứa** `ground_truth_case`, `truth_group_id`, `true_bank_id`, `injected_scenario`, `case_id` nếu các ID này tiết lộ chính xác mối liên kết; nếu cần public correlation trong feed thì phải chứng minh đó là business field hợp lệ.
- Không đưa seed, truth path, label, expected pair vào input engine.
- Synthetic bank memo **không mặc định chèn order ID** trong toàn bộ trường hợp hard benchmark.
- Chia dev/holdout ở **mức order/customer/group source**, không để các bản biến thể cùng tình huống lọt cả hai tập.
- `Generator` và `Evaluator` được gọi ngoài `engine.run()` và không import ngược vào `matching`.

---
# 7. INPUT CONTRACT: RAW → CANONICAL → EVIDENCE

## 7.1. Quy tắc chung

- File nguồn **bất biến**; lưu `original_filename`, `file_sha256`, `source_profile`, row number, row hash và config mapping.
- Tất cả khóa tham chiếu/ID là **string** từ đầu đến cuối; không ép `ORD-000012` thành số hay làm mất `0` đầu. Với Excel đã làm mất chữ số đầu do người tạo file định dạng sai, báo warning không thể khôi phục chắc chắn.
- Các trường thời gian có `date_format`/`timezone` trong mapping profile; xác định bằng người dùng nếu mơ hồ `03/04/2026`.
- Parse tiền dùng `Decimal` và khai báo `decimal_separator`, `thousand_separator`, currency; không dùng `.astype(float)` làm đại diện tiền.
- Định danh `bank_txn_id` cần là **unique canonical ID trong run**; nếu `txn_ref` gốc không duy nhất, tạo surrogate ổn định từ source file hash + sheet + source row index, giữ `txn_ref` gốc riêng.
- Không tự gọi một khoản trùng `txn_ref` là trùng tiền thật: duplicate-ID, duplicate-import và repeated-legitimate cần các cờ khác nhau.
- `posting_amount`/`net_amount`/`gross_amount` phải có khai báo `amount_basis`; không tự cộng phí vào dòng tiền đã ghi ngân hàng.

## 7.2. Canonical schema — Internal receivables (`orders`)

| Tên chuẩn | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `order_id` | string | Có | Định danh nghĩa vụ phải thu; unique trong profile MVP, nếu không cần cấu hình composite key |
| `ordered_at` | datetime | Có | Ngày phát sinh khoản phải thu; configurable date format/timezone |
| `expected_amount_minor` | int64 | Có | Số phải thu >=0 theo currency minor unit; lưu bản raw riêng |
| `currency` | string ISO | Có | MVP một currency/run; default chỉ khi người dùng xác nhận |
| `order_status` | enum/string | Có hoặc default có xác nhận | `ELIGIBLE`, `PENDING`, `CANCELED`, `EXCLUDED` theo mapping policy |
| `customer_id` | string | Không | Chỉ hỗ trợ blocking khi thật sự cùng định danh/business context |
| `customer_name` | string | Không | Có thể trống; xử lý bảo mật/độ nhạy |
| `payment_channel` | string | Không | `BANK_TRANSFER`, `CARD`, `VNPAY`, `PSP`, `UNKNOWN` |
| `external_ref` | string | Không | Mã thanh toán/PSP/hóa đơn độc lập với order ID |
| `batch_ref` | string | Không | Group/batch ID nếu nguồn nội bộ có |
| `description` | string | Không | Mô tả nguồn; không đồng nghĩa ref đáng tin |
| `source_file_id`, `source_row_number`, `source_row_hash` | metadata | Engine tự sinh | Audit/trace |

**Về kiểu amount:** file người dùng có thể chứa `amount`, `order_amount`, `receivable`, v.v.; `mapping` chuyển thành `expected_amount_minor`. Không yêu cầu người dùng tự đặt tên cột giống chuẩn. Với source status chưa được định nghĩa thì `order_status` không thể tự coi `PAID` hay `CANCELED` đúng nghĩa; cần profile/status policy.

## 7.3. Canonical schema — Bank/PSP (`bank_transactions`)

| Tên chuẩn | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `bank_txn_id` | string | Engine có thể tạo surrogate | Unique trong run, khác `txn_ref` |
| `txn_ref` | string | Không | Mã từ ngân hàng/PSP, không đảm bảo duy nhất |
| `txn_date` | datetime | Có | Ngày phát sinh/ghi sổ theo feed |
| `value_date` | datetime/null | Không | Ngày hiệu lực; báo rõ dùng loại nào trong window |
| `direction` | `CREDIT`/`DEBIT` | Có | Có thể suy từ cột credit/debit **theo mapping xác nhận** |
| `posted_amount_minor` | int64 | Có | Độ lớn không âm, `direction` biểu diễn dấu |
| `amount_basis` | enum | Có | `POSTED_CASH`, `NET_SETTLEMENT`, `GROSS_SETTLEMENT`/profile declared |
| `currency` | string | Có | Không ghép khác currency nếu chưa có FX policy ngoài MVP |
| `description` | string | Không | Memo tự do, xử lý token boundary |
| `sender_name` | string | Không | Có thể null, không giả định từ Olist |
| `channel` | enum/string | Không | BANK/PSP/TRANSFER/UNKNOWN |
| `batch_ref` | string | Không | Ref gộp PSP, nếu thực tế tồn tại |
| `declared_fee_minor` | int/null | Không | **Chỉ** nếu feed cung cấp và khai báo ý nghĩa |
| `source_file_id`, `source_row_number`, `source_row_hash` | metadata | Engine tự sinh | Audit/trace |

**Chốt cash basis:** `posted_amount_minor` chỉ được đưa vào invariant cash khi trường nguồn thực sự là dòng tiền đã ghi có hoặc *net cash settlement* xác nhận. Một cột báo cáo **gross PSP sales** không có dòng tiền về ngân hàng thì không được giả làm `posted_amount_minor` cash; yêu cầu map đúng nguồn, hoặc dừng/review vì thiếu chứng cứ về số tiền thực nhận.

**Sai khác của tên input:** mẫu trong đề xuất mới dùng `tx_id`, `order_ref`, `tx_date`, `amount`, `bank_id`, `clear_date`, `net_amount`. Các tên này **được hỗ trợ qua mapping**, không khóa schema core theo chúng. `net_amount` không mặc nhiên là ngân hàng thực nhận nếu người dùng không xác nhận source profile.

## 7.4. Mapping profile (ví dụ minh họa)

```yaml
profile_id: vn_sample_v1
mode: payment_2way
currency: VND
money:
  decimal_separator: "."
  thousand_separator: ","
  minor_units: 0
  rounding: HALF_UP
orders:
  source_sheet: Internal
  mapping:
    order_id: order_ref
    ordered_at: tx_date
    expected_amount: amount
    customer_name: customer_name
    payment_channel: payment_method
bank:
  source_sheet: Bank
  mapping:
    txn_ref: bank_id
    txn_date: clear_date
    posted_amount: net_amount
    description: description
    channel: channel
  defaults_confirmed_by_user:
    currency: VND
    direction: CREDIT
    amount_basis: POSTED_CASH
policy:
  max_days_diff: 3
  max_group_orders: 3
  max_split_bank_rows: 3
  fuzzy_threshold_for_candidate: 85
  auto_confirmation_mode: STRICT
```

Trên thực tế **không tự chèn** default `direction=CREDIT` khi file có dòng debit. Phải phân loại/loại trừ đúng. Những giá trị 3 ngày, 85 điểm là cấu hình đề xuất nghiên cứu, **chưa được chứng minh tối ưu**, không phải ngưỡng universal.

## 7.5. Data lineage

- `source_file`: tên, bytes hash, content type, size, sheet name, import time.
- `source_row`: number/Excel row, raw values, raw row hash, errors, resolutions.
- `canonical_row`: canonical IDs, normalization decisions, source row link, validation flags.
- `match evidence`: `rule_id`, `rule_version`, `block_key`, `candidate_features`, `reason_codes`, `source_hashes`.
- `run manifest`: input hashes, mapping/config hashes, dataset profile, code commit SHA/rule version, report version.

Nếu xóa raw uploads theo TTL để bảo mật, manifest và audit có thể vẫn còn, nhưng **không thể hứa tái dựng chính xác toàn bộ source rows**; UI/README phải công bố retention policy. Với demo local, có thể giữ data đã được người dùng xác nhận và mở lại cho đến lúc chủ động xóa.

---

# 8. CHUẨN HÓA VÀ MONEY INVARIANTS

## 8.1. Luồng normalize

1. Đọc file theo encoding, delimiter, sheet/format đã chọn; kiểm tra số cột/header/trống.
2. Chuẩn hóa tên cột chỉ để **gợi ý** mapping, không silently force.
3. Chuẩn hóa ID sang string không đổi ký tự có ý nghĩa, trim invisible characters phù hợp.
4. Chuẩn hóa ngày có timezone và parse policy rõ ràng.
5. Chuẩn hóa tiền `Decimal`, chuyển sang minor-unit integer theo currency và rounding policy.
6. Chuẩn hóa text (`NFKC`, whitespace, casefold, optional ASCII fold cho fuzzy), giữ cả **raw** và **normalized**, không loại hết ký tự trước khi trích token.
7. Trích **danh sách** refs với regex được cấu hình; preserve token spans/offsets/nguồn.
8. Phát hiện duplicate/ambiguous reference và source-row lineage.
9. Tạo canonical records, có thể materialize Parquet cho DuckDB.

**Không** chỉ lấy `extracted_ref` đầu tiên: `"THANH TOAN DH001 DH002"` phải trả cả 2 refs để có thể phát hiện N:1. Regex cần có prefix/length/boundary; `DH01` không khớp `DH010`; mẫu `ORD2026 0045` là một variant được parse theo configured normalization, còn `0RD` (chữ số 0) khác `ORD` (chữ O) phải được coi là candidate/proposed trừ khi profile chứng minh transformation an toàn.

## 8.2. Nguyên tắc tiền tệ

- BRL: 2 minor digits (centavos) ⇒ `123.45 BRL` thành 12.345 minor units.
- VND: 0 minor digits ⇒ 300.000 VND thành 300.000 minor units.
- Không có `amount_tolerance=0.01` chung cho VND/BRL.
- Không dùng float để cộng/so khớp cuối cùng; fuzz/score có thể float vì **không phải giá trị tiền**.
- Số tiền âm đi vào `direction`/transaction type; với input âm không giải thích được thì health issue.
- Group chỉ ghép các khoản cùng currency và cùng amount semantics tương thích; mixed currency ⇒ block/review ngoài MVP.

## 8.3. Hai loại phân bổ không được nhập nhằng

**`cash_allocation_minor`** là tiền thực nhận được phân bổ vào order. **`verified_adjustment_minor`** là phí/giảm trừ/điều chỉnh **có chứng cứ**, không phải tiền ngân hàng. Nếu PSP nhận tiền ròng 98.000 cho khoản gross 100.000 và phí được chứng minh 2.000 (chỉ khi **hợp đồng settlement cho phép coi khoản phí đó là điều chỉnh nhằm tất toán khoản phải thu theo chính sách đã phê duyệt**):

- Dòng tiền ngân hàng 98.000 ⇒ **cash allocated <= 98.000**.
- Điều chỉnh phí được duyệt 2.000 ⇒ có thể làm nghĩa vụ phải thu được settlement đủ theo policy.
- Không viết một cash edge 100.000 trên bank 98.000 vì vi phạm bảo toàn cash.

Đây là khác biệt bắt buộc giữa **cash reconciliation** và **gross-to-net settlement reconciliation**. Trong mode bank transfer thông thường, thiếu 2% vẫn là khoản thiếu, không tự tạo fee adjustment.

## 8.4. Invariant phải kiểm thử bằng property tests

Ký hiệu: `E(o)` số phải thu hợp lệ, `C(b)` posted eligible credit, `A(o,b)` cash allocation confirmed >=0, `F(o)` verified adjustments approved >=0 trong policy, `R(o)` còn phải thu, `U(b)` cash credit chưa phân bổ.

**Cash conservation theo từng dòng bank:**

```text
For every bank b:
  sum_o A(o,b) + U(b) = C(b)
  sum_o A(o,b) <= C(b)
  U(b) >= 0
```

**Order fulfillment theo nghĩa vụ đã quy ước:**

```text
For every order o:
  sum_b A(o,b) + F(o) + R(o) = E(o)
  sum_b A(o,b) + F(o) <= E(o)
  R(o) >= 0
```

**Overpay** không âm thầm biến thành `F(o)` hay đổi `E(o)`: khi B1=520, O1=500 thì `A=500`, `U=20`. Nếu người dùng muốn giữ customer credit balance, phase sau có nghiệp vụ riêng, không trộn nghĩa vụ.

**Ngoại lệ:** các debit/refund, chargeback, fee paid separately không thuộc `C(b)` của credit pool này; đưa vào ledger adjustment/reversal domain riêng khi mở rộng. Các identities/invariants phải dùng cùng revision snapshot, không cộng candidate proposal vào cash confirmed.

## 8.5. Hợp đồng status của amount

- `FULL`: residual phải thu = 0 với evidence hợp lệ và order eligible.
- `PARTIAL`: có cash/adjustment được xác nhận nhưng residual > 0.
- `OVERPAID`: cash credit liên quan lớn hơn nghĩa vụ hoặc có dư credit đi kèm linked bank; residual bank phải được lưu, không ghi cash edge vượt nghĩa vụ.
- `NO_CONFIRMED_RECEIPT`: chưa xác nhận được dòng tiền nào; **không khẳng định khách chưa thanh toán**.
- `UNKNOWN`: có evidence thiếu/chồng chéo hoặc policy chưa đủ để kết luận.
- `NOT_ELIGIBLE`: canceled/pending chưa phải thu theo policy; không tính vào unmatched denominator.

---

# 9. UPLOAD, DATA HEALTH, PREVIEW VÀ QUALITY GATE

## 9.1. Luồng bắt buộc

`Upload → Detect/Preview → Confirm Mapping → Parse/Normalize → Health Gate → Resolve/Acknowledge → Confirm Policy → Run`.

### Severity levels

| Severity | Điều kiện ví dụ | Ứng xử |
|---|---|---|
| `BLOCKING` | Thiếu cột ID/amount/date; parse sai không được xử lý; tiền/currency không xác định; số ID nội bộ trùng không có mapping composite/solution | Không chạy matching; hiển thị lỗi + gợi ý sửa/exclude có audit |
| `WARNING` | Missing memo/tên; value date trống; nghi trùng; status chưa rõ; dấu phân cách tiền được suy đoán | Cho confirm/acknowledge có ghi chú; hạn chế auto nếu ảnh hưởng evidence |
| `INFO` | Phân bố số tiền, số dòng, currency profile, thời gian, tỷ lệ null | Hiển thị tóm tắt, không chặn |

Không được cho qua lỗi `BLOCKING` chỉ bằng nút “tôi chấp nhận” nếu nó làm dữ liệu canonical không thể xác định. Khi người dùng chọn *loại trừ dòng*, lưu exclusion record/row hash, số tiền ảnh hưởng và lý do.

## 9.2. Duplicate policy

- **Primary key collision orders:** có cùng `order_id` nhưng khác nghĩa vụ: block hoặc require configured composite key; không `drop_duplicates('order_id')` bừa.
- **Source bank duplicate import:** cùng reference + amount + time + stable source fingerprint: route suspicion; bản thứ hai không được tự coi là credit thứ hai nếu dấu hiệu duplicate mạnh.
- **Legitimate repeated credits:** hai transaction IDs nguồn khác nhau dù cùng tiền/ngày: vẫn là hai dòng có thể hợp lệ; không loại chỉ vì `amount` giống nhau.
- Cần `duplicate_type`: `ID_COLLISION`, `POSSIBLE_REIMPORT`, `POSSIBLE_REAL_REPEAT`, kèm chứng cứ.

## 9.3. Upload security & normalization

- Chấp nhận `.csv`, `.xlsx`; không yêu cầu `.xls`, `.xlsm`, macro, PDF cho MVP.
- Giới hạn sơ bộ **25 MB/file, 100.000 rows/feed** cho demo local; đây là guardrail ban đầu, chỉnh sau profiling và hardware.
- Check file signature/structure, byte limits, sheet count, max rows/cols, parser timeouts, đường dẫn; CSV encoding UTF-8/UTF-8-SIG trước rồi fallback có kiểm soát.
- Trước import Excel: không thực thi macro/formula; nếu formula-only cell không có cached value hợp lệ ⇒ warning/error, không `eval` formula.
- Không dùng tên file gốc làm đường dẫn trực tiếp; file private nằm dưới upload session safe-id; xóa sau TTL theo policy.
- Preview giới hạn 20–100 rows; engine tải đầy đủ khi run, không lọc dữ liệu vì pagination UI.

---

# 10. MÔ HÌNH MIỀN NGHIỆP VỤ: GROUP + ALLOCATION + EVIDENCE

## 10.1. Các thực thể cốt lõi

| Entity | Mục đích | Các field tiêu biểu |
|---|---|---|
| `UploadSession` | Giữ lựa chọn file/map trước run | id, hashes, preview, TTL, quality report |
| `ReconciliationRun` | Phiên đối soát bất biến về input/config | run_id, config_hash, rule_version, status, created_at, artifact paths |
| `SourceRow` | Truy vết về dữ liệu gốc | file_id, row_number, raw_hash, canonical_row_id |
| `Order` | Nghĩa vụ phải thu | order_id, amount, currency, eligibility |
| `BankTransaction` | Dòng tiền/PSP | bank_txn_id, amount, direction, profile |
| `MatchGroup` | Nhóm quan hệ n↔m | group_id, group_type, link_status, score, evidence |
| `AllocationEdge` | Cash từ bank b vào order o | edge_id, group_id, bank_txn_id, order_id, cash_minor, source hashes |
| `Adjustment` | Phí/điều chỉnh được chấp nhận | adjustment_id, target order/group, type, minor, basis, evidence |
| `CandidateProposal` | Đề xuất chưa cam kết | proposal_id, participants, features, reasons, conflicts |
| `ExceptionCase` | Tình huống cần xác minh | reason_code, affected_ids, risk_amount, status |
| `ReviewAction` | Quyết định của người dùng | action_id, previous/current state, actor_label, note, timestamp, revision |
| `RunRevision` | Snapshot hiệu lực sau mỗi review | revision_id, parent_revision, current groups/edges checksum |
| `RunManifest` | Tái tạo | input/config hashes, seed, version, origin, benchmark info |

## 10.2. MatchGroup types

`ONE_TO_ONE`, `MANY_ORDERS_ONE_BANK`, `ONE_ORDER_MANY_BANKS`, `AMBIGUOUS_CANDIDATES`. Nhóm nhiều-nhiều tổng quát có thể được biểu diễn bằng graph domain nhưng **không phải đầu ra được auto-accept trong MVP**; route `COMPLEX_MANY_TO_MANY_REVIEW`.

## 10.3. Evidence model

Mỗi đề xuất/xác nhận có:

```json
{
  "rule_id": "REF_GROUP_001",
  "rule_version": "3.0.0",
  "reference_hits": ["DH001", "DH002"],
  "reference_source": "bank.description",
  "reference_evidence_level": "EXACT_FULL_TOKEN",
  "amount_delta_minor": 0,
  "date_delta_days": 1,
  "sender_similarity": null,
  "memo_similarity": null,
  "candidate_competitor_count": 0,
  "score": 100,
  "score_semantics": "heuristic_ranking_not_probability",
  "explanation_vi": "Một giao dịch có hai mã đơn rõ ràng và tổng khoản phải thu đúng số tiền đã ghi có."
}
```

Vì không phải mọi score đều tương đương xác suất, giao diện nên ghi **`Điểm xếp hạng`** / `rule score`, không ghi “Tự tin 100% chính xác”.

## 10.4. Candidate ≠ confirmed allocation

- Candidates có thể **chồng lên cùng bank/order** trong queue để analyst so sánh; chúng chưa làm thay đổi cash allocations.
- Chỉ khi auto-commit hợp lệ hoặc review `APPROVED` thì mới tạo effective confirmed edges/adjustments trong một revision.
- Khi xác nhận một group, mọi proposal xung đột phải được mark `CONFLICTED`/recomputed. Không giữ hai group đã xác nhận dùng cùng một đồng tiền.
- Review không sửa raw; nếu analyst sửa mapping/policy cần tạo **run mới** hoặc explicit new revision với nguồn cấu hình versioned (chốt MVP: **mapping/policy change ⇒ new run**).

---

# 11. THIẾT KẾ WATERFALL: 4 LỚP MATCHING + EXCEPTION

## 11.1. Tiền xử lý trước waterfall

```text
0A. Read/Map/Normalize
0B. Data Health Gate & Eligibility
0C. Ref extraction, blocking keys, amount basis, evidence index
0D. Discover strong ref candidate sets; detect cross-layer conflicts

L1. Strict identity matching (full/structured refs; 1:1 and obvious grouped/split)
L2. Policy-constrained matching (time windows / fee evidence / extra identifiers)
L3. Fuzzy candidate ranking (text/name; NEVER auto by similarity alone)
L4. Bounded grouped/split proposal search (subset sum within safe blocks)

POST. Conflict resolution → confirmed/proposed edges
      → partial/over/unmatched/orphans/exceptions
      → invariants → KPIs/audit/export
```

**Tại sao có `0D`?** Waterfall ngây thơ "chốt 1:1 rồi loại bank ngay" có thể giành mất dòng bank thật sự thanh toán hai đơn. Trước khi **commit**, engine phải biết bank memo có **nhiều references**, hoặc có nhiều bank cùng một ref để không cố đóng thành 1:1. Các lớp được lưu để demo/đánh giá, nhưng conflict graph và cash budget là **ràng buộc toàn cục**.

## 11.2. Nguyên tắc chốt kết quả

1. **Strong evidence, no conflict:** có thể auto-confirm **link**. Nếu amount thấp, `link_status=CONFIRMED`, `payment_status=PARTIAL`, không đưa vào "khớp đủ".
2. **Known time lag** với cùng mã đầy đủ/tiền và không tranh chấp: có thể auto-confirm trong strict policy vì trễ T+1 không làm mất định danh; phải ghi reason/time warning. Config có thể bảo thủ yêu cầu review.
3. **Policy-based PSP fee:** chỉ auto-settle nếu có fee record/contract policy đầy đủ và tổng tiền reconcile; đề xuất V2 giữ fee ở **review** mặc định để không tự hạch toán.
4. **Fuzzy hoặc amount/time-only:** proposal, `NEEDS_REVIEW`. Khi có ít nhất hai ứng viên khả dĩ, gắn `AMBIGUOUS_CANDIDATES` và không auto.
5. **Grouped reference evidence:** nhiều refs có token đầy đủ, đúng tổng tiền, không tranh chấp có thể auto-confirm theo strict rule tùy policy; grouped không ref ⇒ review dù sum exact.
6. **Split reference evidence:** nhiều bank records cùng full order ref, tổng đủ/chưa đủ và không conflict ⇒ có thể auto-confirm các cash edges; các khoản thiếu/dư vẫn đúng trạng thái.
7. Mỗi step chạy trên **candidate pool chưa có confirmed cash reservation**; những bank/order được reserve một phần vẫn có thể xét phần residual theo giới hạn (split) nhưng **không** dùng lại cash đã phân bổ.

## 11.3. Luật "giao thông" mới chính xác hơn

| UI Bucket | Ý nghĩa | Ví dụ |
|---|---|---|
| 🟢 `VERIFIED_FULL` | Liên kết đã xác nhận, khoản phải thu đã được giải quyết đủ theo policy | Exact 1:1, N:1 tiền đủ |
| 🟡 `REVIEW_REQUIRED` | Proposed/ambiguous hoặc có khoản chênh cần xử lý dù link có thể đã xác định | Fuzzy; group không ref; fee chưa chứng minh; partial |
| 🔴 `UNRESOLVED` | Chưa xác nhận có đối ứng, invalid/excluded/exception chưa giải quyết | Orphan internal, orphan bank, data issue; có thể điều tra sau |

**Đặc biệt:** `OVERPAY` dù order đã đủ tiền vẫn cần cờ cảnh báo và review số dư chưa phân bổ; một group có `U(b)>0` không thể chỉ hiện xanh rồi giấu phần tiền thừa. **Không dùng 3 màu làm thay thế trạng thái domain.** Hiển thị chip bổ sung: `CONFIRMED_LINK + PARTIAL`, `APPROVED_BY_USER`, `OVERPAY + RESIDUAL`. Reviewer approve một **đề xuất liên kết** không mặc nhiên biến thành `VERIFIED_FULL` khi thiếu tiền.

---

# 12. CHI TIẾT MATCHING, FUZZY, BLOCKING VÀ CONFLICTS

## L1. Strong reference 1:1 / N:1 / 1:N

- Parse toàn bộ full-order refs từ `txn_ref`, `description`, `batch_ref` theo **configured grammar**; ưu tiên shared unique ID nếu được xác minh.
- Single full ref xuất hiện một lần ở bank và order ⇒ candidate strong 1:1; kiểm tra order eligible, same currency, amount basis, direction và không có strong split khác.
- Một bank có **nhiều full refs** ⇒ N:1; đối chiếu từng order, tổng tiền, không duplicate, không conflicted.
- Một full ref xuất hiện trong **nhiều bank credits** ⇒ 1:N; ghép tổng, giữ edge riêng để giải thích từng lần trả.
- Mọi **full ref collision** (hai order cùng ref, bank ref trùng không unique, mapping ambiguity) ⇒ `REVIEW`, không auto.
- Thứ tự mạnh/yếu của evidence: unique structured external identifier > full exact token ref > normalized ref with explicit grammar > fuzzy partial candidate > amount/date coincidence.

## L2. Date / amount / fee-constrained

- Điều kiện ví dụ: `0 <= (bank_date - order_date).days <= 3` **cho profile T+N**, nhưng không áp mặc định cho tất cả. Cho late-arrival/out-of-window phải có reason code.
- `amount exact` hoặc `amount within currency-specific absolute tolerance` không đủ để auto khi không có định danh độc lập; amount+date-only là **candidate**.
- Nếu có `external_ref`/customer batch token đáng tin, có thể xác lập link mạnh hơn; nếu có nhiều ứng viên, chuyển review.
- Không dùng điều kiện `net BETWEEN 0.97*amount AND amount` để tự xác nhận fee. Trường `payment_channel` hỗ trợ giải thích, nhưng **không tự chứng minh phí thực phát sinh**.
- Tolerance cho **số tiền** chỉ xử lý rounding thật được chứng minh; under/over vẫn phải thể hiện explicit residual.

## L3. RapidFuzz / candidate ranking

Tạo candidate với `blocking_key` trước: cùng currency, window phù hợp, amount band, reference hints/customer/channel nếu có. Tính các feature:

| Feature | Giá trị | Ý nghĩa |
|---|---|---|
| `full_ref_hit` | boolean | Có full token ref khớp |
| `normalized_ref_hit` | boolean | Khớp sau normalization có kiểm soát |
| `trailing_digits_hit` | boolean/null | Chốt phụ, **không chứng minh unique một mình** |
| `memo_similarity` | 0–100/null | RapidFuzz fuzz.ratio/token_set_ratio; `partial_ratio` dễ thiên lệch với memo dài |
| `sender_similarity` | 0–100/null | Chỉ tính khi cả hai bên có tên đáng tin |
| `amount_delta_minor` | int | Sai khác tiền hợp lệ để candidate, không override domain |
| `date_gap_days` | int/null | Độ trễ ghi nhận |
| `competing_candidates` | int | Có bao nhiêu đối thủ trong block |
| `channel_compatible` | boolean/null | Chỉ là evidence, không bằng chứng trả tiền |

- Chọn `Top-K=5` hoặc ít hơn để giải thích, nhưng **không bỏ thông tin conflict** của ứng viên khác do cắt top K.
- Threshold ban đầu có thể `85/100` cho đưa vào review; cần tune trên dev set và khóa holdout; không dùng 85% như xác suất.
- Nếu không có customer/name thì feature là `null`, **không tự quy thành similarity=100**.
- `ref_digits` phải giữ đủ token, không coi `001` trong hai mã khác nhau là full matching.
- Ngưỡng đúng phụ thuộc dataset; ghi `rule_version`/policy snapshot, làm ablation với/không có name/ref/amount window.

## L4. Group/Subset matching bounded

**Để tìm N:1 khi không có explicit multi-ref:**

1. Chọn bank credit chưa fully allocated.
2. Blocking theo currency + khoảng ngày + customer/batch evidence đáng tin + amount upper bound.
3. Chỉ xét `k=2..3` order trong demo, tùy chọn `k=4` cho benchmark nếu block bé.
4. `block_size <= 20` hoặc `<= 30` theo profile; nếu vượt, **không brute force**, route `BLOCK_TOO_LARGE_REVIEW`.
5. Budget số tổ hợp/case (`max_combinations`, ví dụ 2.000) và timeout/candidate ceiling; phép toán trên integer minor units.
6. Nếu có **một** subset vừa tổng tiền nhưng **không có bằng chứng independent** → vẫn chỉ `PROPOSED`.
7. Nếu có hai subsets hoặc dùng cùng order/bank cạnh tranh ⇒ `AMBIGUOUS_GROUP`, không auto.
8. Tất cả candidates đều phải qua global conflict resolver / allocation invariants.

**Để tìm 1:N:** tìm nhiều bank credits của cùng order qua full ref, batch signal hoặc bounded subset theo amounts/time/customer. Chỉ một tổng tiền bằng nhau **không** là lý do auto. Không để split nhặt lại bank đã được xác nhận cho order khác.

### Độ phức tạp

`itertools.combinations` không có blocker dẫn tới số tổ hợp tăng như `C(n,k)`; ví dụ `C(1.000,3)` quá lớn. Dù `C(20,3)=1.140` vẫn phải đo overhead khi có nhiều blocks. DuckDB hỗ trợ lọc/join, nhưng global allocation resolver mới chịu trách nhiệm bảo toàn tiền.

## 12.5. Conflict resolver và commit policy

- Tạo **proposal graph**: order nodes, bank nodes, edges/group hyperedges + evidence weight.
- Chia connected components; những component **độc lập, không xung đột và có hard evidence** có thể auto-confirm theo policy.
- Trong component có cạnh/nhóm cùng tranh cash budget, **không lựa chọn bằng greedy highest score thuần túy** nếu có thể sai; route review hoặc giải quyết deterministic constraint chỉ khi chính sách chứng minh uniqueness.
- Commit order: validate proposed group participants → amount/currency/status → availability of residual cash → uniqueness / overlap → transactional write into effective allocations → recompute residual and KPIs.
- Bất kỳ conflict chưa giải phải giữ reason codes + top alternatives. Không được dùng row-level `matched=True` làm mô hình duy nhất.

---

# 13. CHÊNH LỆCH, PSP FEE, GROSS/NET VÀ REVERSALS

## 13.1. Phân loại amount exception

| Case | Ví dụ | Xử lý |
|---|---|---|
| Exact full | O=500, B=500 | Cash edge 500, R=0, U=0 |
| Underpay | O=500, B=490, ref mạnh | Cash edge 490, R=10, review/partial |
| Overpay | O=500, B=520, ref mạnh | Cash edge 500, U=20; cảnh báo excess |
| PSP gross/net | Orders gross=100, bank net=98, policy fee=2 | Cash edge 98 + verified adjustment 2 **khi có bằng chứng** |
| Bank transfer "trừ phí" 2% không chứng minh | O=100, B=98, method transfer | **Không** tạo fee; Partial 2 |
| Currency mismatch | O=VND, B=BRL | Không match trong MVP |
| Refund/debit | Bank B là DEBIT 50 | Phân loại dòng ra; không là incoming credit |
| Chargeback/reversal | Positive trước, negative sau | Review chuyên biệt; không tự trừ ngược các edges đã confirm nếu chưa có policy |

## 13.2. Chứng cứ đủ cho fee settlement

Có thể gồm PSP settlement file có line-item fees/`batch_ref`, bảng biểu phí chính thức versioned + kênh + effective date + điều kiện áp dụng, hoặc operator review được audit. Không đủ bằng chứng khi **chỉ** thấy bank net thiếu 2% trùng khoảng `1.5–2%`.

Gắn `fee_evidence_type`, `fee_policy_version`, `fee_basis`, `fee_minor`, `approved_by`. Nếu chỉ có hai file mà một trong hai file không chứa thông tin phí, engine được phép **đề xuất** giả thuyết phí, không tự hoàn thành nghĩa vụ. Không tính fee adjustment vào **tiền bank đã ghi có**.

## 13.3. Cutoff và thời gian

Phân biệt `ordered_at`, `txn_date`, `value_date`, `imported_at`, timezone. Ví dụ đơn vào cuối ngày T và bank post ở T+1 không đủ để kết luận thất lạc; UI nên có `lag_bucket` và warning `CROSS_PERIOD_OR_LATE_SETTLEMENT`. Date matching window không làm thay đổi ID/cash truth.

---

# 14. HUMAN-IN-THE-LOOP, REVIEW, UNDO VÀ AUDIT

## 14.1. Mức review

- Review một candidate `1:1`.
- Review **MatchGroup N:1/1:N** cùng tất cả **AllocationEdges** và residuals.
- Review fee adjustment (nếu có) tách khỏi xác nhận link.
- Review manual link mới, reject proposal, leave unresolved/escalate.
- Review suspicious duplicate và excluded data; raw vẫn bất biến.

## 14.2. Giao diện review nên hiển thị

`Group ID`, `group_type`, order IDs, order amounts, bank refs, bank amounts, money basis, proposed cash allocations, residuals, evidence/ref source, rule IDs, alternatives, flags, actor, note. Bấm group mở panel **side-by-side source rows** và các cạnh phân bổ.

**Duyệt gộp là hành động nghiệp vụ có hậu quả:** phải hiển thị phép tính và trạng thái sau duyệt, không chỉ checkbox từng dòng.

## 14.3. Review command model

```json
{
  "run_id": "run_demo_001",
  "expected_revision": 4,
  "action": "APPROVE_GROUP",
  "proposal_id": "prop_018",
  "allocations": [
    {"order_id": "O001", "bank_txn_id": "B001", "cash_minor": 300000},
    {"order_id": "O002", "bank_txn_id": "B001", "cash_minor": 200000}
  ],
  "note": "Đã kiểm tra mã đơn trong nội dung chuyển khoản",
  "actor_label": "demo_reviewer",
  "idempotency_key": "unique-client-generated-token"
}
```

### Xử lý transaction

1. Kiểm tra input DTO, quyền thao tác mức demo/local, `expected_revision`.
2. Mở transaction SQLite; lock/serialize **relevant run review** (SQLite writer policy phù hợp).
3. Kiểm tra proposal vẫn còn hiệu lực; xác định conflict hiện tại.
4. Validate sum cash, currency, eligible status, adjustment evidence, order and bank residuals.
5. Ghi immutable `ReviewAction`, group status, allocations/revision, recompute KPI/caches trong cùng logical transaction (artifact updated via atomic manifest switch).
6. Commit rồi trả `new_revision`, `changed_groups`, `summary`; nếu conflict trả HTTP 409 và dữ liệu cần refresh.
7. Nếu failure giữa update DB và artifact: ưu tiên transaction/outbox + immutable artifact snapshots; recover job/rollback để không hiển thị revision nửa chừng. MVP có thể giữ effective decisions + KPI nhỏ trong SQLite transaction, artifact source immutable.

**Undo:** tạo `UNDO_ACTION` trỏ action cũ, áp lại invariant để phát hiện dependency/conflict. Không xóa audit history. Nếu action đã tác động các review tiếp theo, undo cần chặn hoặc rollback các dependency theo policy; không hứa `undo` lúc nào cũng thành công.

## 14.4. Khi một nhóm bị reject

`REJECTED` là quyết định **về đề xuất nhóm đó**, không tự động biến tất cả order/bank participants thành `UNMATCHED` vĩnh viễn; có thể còn đề xuất khác. Hệ thống trả participants về pool eligible/proposal khác, recompute exceptions. Nếu analyst đã confirm partial payment, không thay đổi phần đã xác nhận không liên quan.

---
# 15. KPI, DASHBOARD VÀ CÔNG THỨC KHÔNG DOUBLE COUNT

## 15.1. Ba mẫu số khác nhau

- **Đơn (`orders`)**: đếm số `order_id` đủ điều kiện.
- **Giao dịch ngân hàng (`bank rows`)**: đếm số `bank_txn_id` đủ điều kiện sau phân loại direction/dedup.
- **Tiền (`amount`)**: lấy tổng amount trực tiếp ở order/bank **hoặc** tổng cash allocation edges đã confirmed tùy công thức; không cộng chồng các bảng.

Một bank được phân bổ cho ba orders **chỉ** được tính **một bank row** và tổng cash đúng giá trị bank một lần.

## 15.2. Định nghĩa KPI API được chốt

| KPI | Công thức/định nghĩa | Hiển thị |
|---|---|---|
| `eligible_orders_count` | COUNT distinct eligible order IDs | Tổng khoản phải thu |
| `bank_eligible_credit_count` | COUNT distinct eligible CREDIT bank IDs | Tổng giao dịch thu |
| `confirmed_link_orders_count` | COUNT orders có >=1 confirmed cash edge | Đơn có bằng chứng thu |
| `fully_settled_orders_count` | COUNT eligible orders `R(o)=0` & evidence confirmed | Đơn đã đủ tiền |
| `partially_settled_orders_count` | COUNT eligible orders có cash/adjustment >0 nhưng `R(o)>0` | Đơn còn thiếu |
| `no_confirmed_receipt_orders_count` | COUNT eligible orders tổng confirmed cash = 0 (tách exception) | Đơn chưa xác định tiền về |
| `confirmed_bank_rows_count` | COUNT distinct bank rows có cash allocated >0 | Bank đã được phân bổ ít nhất một phần |
| `unallocated_bank_rows_count` | COUNT eligible bank rows có `U(b)>0` | Bank còn tiền chưa phân bổ |
| `expected_receivable_minor` | SUM `E(o)` trên eligible orders | Tổng phải thu |
| `confirmed_cash_allocated_minor` | SUM `A(o,b)` trên **effective confirmed edges** | Tiền bank đã đối soát vào đơn |
| `verified_adjustments_minor` | SUM `F(o)` được duyệt | Phí/điều chỉnh được chấp nhận |
| `outstanding_receivable_minor` | SUM `R(o)` | Phải thu còn lại |
| `unapplied_bank_credit_minor` | SUM `U(b)` | Tiền nhận chưa phân bổ |
| `grouped_n1_count` | COUNT confirmed groups `MANY_ORDERS_ONE_BANK` | Số khoản gộp |
| `split_1n_count` | COUNT confirmed groups `ONE_ORDER_MANY_BANKS` | Số đơn trả nhiều lần |
| `proposed_groups_count` | COUNT currently reviewable proposals | Nhóm cần duyệt |
| `unresolved_exceptions_count` | COUNT open exception cases, **không phải số rows** | Cases cần xử lý |

**KPI `fully_settled_orders_count` chỉ đo mức giải quyết khoản phải thu; `OVERPAY`/`unapplied_bank_credit_minor` vẫn phải được hiển thị độc lập và bật cờ review cho bank liên quan, kể cả order tương ứng đã FULL.**

**Lưu ý `fully_settled` có thể gồm verified fee adjustment**, vì đây là nghĩa vụ đã giải quyết theo policy, không có nghĩa tiền ngân hàng nhận = gross phải thu. Vì vậy báo cáo phải tách cash và adjustment.

### Reconciliation identities cấp tổng

```text
SUM(eligible bank CREDIT) = confirmed_cash_allocated + unapplied_bank_credit
SUM(eligible order receivable) = confirmed_cash_allocated + verified_adjustments + outstanding_receivable
```

Đây là identity theo thiết kế simplified MVP sau khi loại trừ transaction/status không đủ điều kiện và xử lý adjustment được quy định. Nếu một số khoản chênh thuộc nghiệp vụ chưa hỗ trợ, để `UNKNOWN/UNRESOLVED` với residual, không ép các tổng “bằng nhau” bằng write-off giả.

## 15.3. Các tỷ lệ và chart phải khai báo mẫu số

- `auto_confirm_order_coverage = auto_confirmed_order_count / eligible_orders_count` (không phải “accuracy”).
- `fully_settled_order_rate = fully_settled_orders_count / eligible_orders_count`.
- `bank_allocation_coverage_by_value = confirmed_cash_allocated_minor / SUM(eligible bank credits)`.
- `review_case_rate = review_cases / all classified cases` (không cùng mẫu số orders).
- `amount_in_review` được tính qua **unique impacted order/bank scope** hoặc defined risk policy, không cộng tổng gross mỗi proposal vì chồng ứng viên.
- Funnel chart ghi **số mới confirmed ở từng layer** và **còn lại**, không lấy `PROPOSED` làm đã giải quyết; N:1/1:N có thể đếm cả group counts và order counts riêng.
- Pie xanh/vàng/đỏ trên **eligible orders** nếu là chart theo đơn. Orphan bank vẽ chart riêng theo bank rows.

## 15.4. Dashboard tối thiểu

**Hàng KPI**: Tổng phải thu, confirmed cash, còn phải thu, tiền bank chưa phân bổ, fully settled orders, review cases. Hiển thị currency và đơn vị (`VND`, `BRL`) nhất quán.

**Biểu đồ**: waterfall matched by layer; bar/donut `FULL/PARTIAL/NO_CONFIRMED_RECEIPT`; stacked bar `1:1/N:1/1:N/proposed`; scatter/histogram lag `T+N`; top exception reasons; amount residual distribution; trend theo ngày.

**Bảng chi tiết**: `Orders`, `Bank`, `Groups`, `Allocations`, `Exceptions`; mỗi bảng có filter, search, export, drill-down provenance. Không hiển thị Precision/F1 ở dữ liệu production user thiếu truth.

---

# 16. PERSISTENCE, STATE MANAGEMENT VÀ RUN LIFECYCLE

## 16.1. Run lifecycle

```text
UPLOADED → INSPECTED → MAPPING_CONFIRMED
          ↓
      HEALTH_BLOCKED  ──(fix/re-inspect)──► HEALTH_READY
                                             ↓
                                         RUNNING
                                       /    |    \
                                COMPLETED FAILED CANCELED
                                    ↓
                          REVIEWED (revisions 1..N)
                                    ↓
                               EXPORTED / ARCHIVED
```

Run có `run_id` không thay đổi; mỗi review tạo `run_revision`. `policy_hash`/`mapping_hash` gắn vào run và bất biến. Nếu đổi file, mapping, currency/rounding hay rules ⇒ **run mới**, không âm thầm tái tính run cũ.

## 16.2. Schema lưu trữ gợi ý (SQLite)

```text
upload_sessions(
  session_id PK, created_at, expires_at, source_manifests_json,
  mapping_draft_json, mapping_confirmed_json, health_status
)
runs(
  run_id PK, upload_session_id, created_at, completed_at, status,
  dataset_profile, config_json, config_hash, rule_version,
  artifact_manifest_path, current_revision
)
review_actions(
  action_id PK, run_id, revision_before, revision_after,
  action_type, target_proposal_id, actor_label, note,
  command_hash, idempotency_key UNIQUE, created_at, undo_of_action_id
)
group_decisions(
  run_id, revision_id, group_id, group_type, link_status,
  resolution_type, PRIMARY KEY(run_id, revision_id, group_id)
)
allocation_edges(
  run_id, revision_id, edge_id, group_id, order_id, bank_txn_id,
  cash_minor, currency, created_by_action_id
)
verified_adjustments(
  run_id, revision_id, adjustment_id, order_id, adjustment_type,
  amount_minor, approved_action_id, evidence_json
)
run_revision_meta(
  run_id, revision_id, parent_revision, effective_checksum,
  created_at, actor_label, summary_json
)
```

Đây là **logical schema**; implementation thực tế có thể chọn event-sourced revisions + materialized effective state để tránh duplicate toàn bộ edges theo mỗi lần review. Cần index `(run_id,revision)`, `(bank_txn_id)`, `(order_id)`; kiểm tra DB migration bằng Alembic. Các định danh nguồn phải namespace theo `run_id`.

## 16.3. Artifact store

```text
storage/
  uploads/<session_id>/                  # temporary, TTL, private
  runs/<run_id>/
    source_manifest.json
    canonical_orders.parquet
    canonical_bank.parquet
    proposals.parquet
    base_confirmed_allocations.parquet
    exceptions.parquet
    quality_report.json
    run_manifest.json
    revisions/                            # optional snapshots/checksums
    exports/                              # cache reports by revision
```

Raw bytes có thể tồn tại riêng dưới retention policy; `app.db` chứa operational state/audit, **không trộn** vào DuckDB file cho mỗi request. `storage/` và `.db` nằm trong `.gitignore`. Dùng atomic file writes để giảm corruption; CI test restart/resume.

## 16.4. Chính sách bảo quản và xóa dữ liệu

**Mặc định demo local đề xuất**: upload sessions tạm có TTL ví dụ 24 giờ (cấu hình), completed demo runs được giữ đến khi người dùng xóa/clear workspace; công bố rõ retention/cleanup. Nếu muốn đảm bảo reopen with source context, cần lưu artifact/row view có chính sách bảo mật phù hợp. Không ghi thông tin nhạy cảm đầy đủ vào log. Trong MVP một người máy local không yêu cầu hệ thống login doanh nghiệp; deployment công khai bắt buộc bổ sung auth/permission trước khi mở cho người dùng khác.

---

# 17. THIẾT KẾ FASTAPI — CONTRACT VÀ LỖI

## 17.1. Endpoints chuẩn có version

| Method | Endpoint | Chức năng | Kết quả chính |
|---|---|---|---|
| `GET` | `/healthz` | Health đơn giản của BE | readiness/liveness |
| `POST` | `/api/v1/demo/datasets` | Sinh/chọn dataset **chỉ dev/demo** | profile ID, files/manifest |
| `POST` | `/api/v1/uploads/inspect` | 2 file, hoặc 1 workbook với chọn 2 sheets | session ID, preview, suggested mapping |
| `POST` | `/api/v1/uploads/{session_id}/mapping` | Xác nhận mapping, date/amount profile | quality report, gate status |
| `GET` | `/api/v1/uploads/{session_id}/health` | Blocking/warnings/samples | issues + counts |
| `POST` | `/api/v1/uploads/{session_id}/resolutions` | Exclude/repair/acknowledge, re-run health | updated health gate |
| `POST` | `/api/v1/runs` | Start với upload session + policy | run ID/status |
| `GET` | `/api/v1/runs/{run_id}` | Run status, config/revision snapshot | summary metadata |
| `GET` | `/api/v1/runs/{run_id}/dashboard` | Aggregate chart DTO + KPIs | chart data |
| `GET` | `/api/v1/runs/{run_id}/groups` | Filter/sort/pagination | groups/candidates |
| `GET` | `/api/v1/runs/{run_id}/groups/{group_id}` | Evidence, source rows, allocations | group detail |
| `GET` | `/api/v1/runs/{run_id}/orders` | Search/filter orders | paged orders |
| `GET` | `/api/v1/runs/{run_id}/bank-transactions` | Search/filter bank | paged bank rows |
| `GET` | `/api/v1/runs/{run_id}/exceptions` | Open exceptions, risk labels | paged exceptions |
| `POST` | `/api/v1/runs/{run_id}/reviews` | Approve/reject/manual adjustment | new revision + KPIs |
| `POST` | `/api/v1/runs/{run_id}/reviews/{action_id}/undo` | Undo với dependency check | new revision |
| `GET` | `/api/v1/runs/{run_id}/review-log` | Audit log | paged actions |
| `GET` | `/api/v1/runs/{run_id}/exports?format=xlsx` | Report, files served safely | downloadable file |
| `POST` | `/api/v1/dev/evaluations` | Đánh giá truth (dev only) | eval job/metrics |

**Không nhận ground truth ở API người dùng bình thường.** `POST /api/v1/demo/datasets`/`dev/evaluations` không được bật vô điều kiện trong public deployment.

## 17.2. Upload contract

- Multipart `orders_file` + `bank_file`; hoặc `workbook_file` + sheet names. Không đồng thời chấp nhận cả hai form ở cùng một request nếu gây ambiguity.
- Có `upload_session_id`, `file_sha256`, `suggested_mapping` kèm confidence **của mapping heuristic** không phải quality matching, `sample_rows`, `source_profile`, `warnings`.
- File được giới hạn theo size/sheet/rows; FastAPI `UploadFile` dùng spooled file (có thể chuyển ra disk), nên **không** được khẳng định “luôn in-memory” hoặc “không chạm disk” nếu chưa cấu hình/kiểm tra.

## 17.3. Ví dụ run config/request (minh họa)

```json
{
  "upload_session_id": "sess_123",
  "mapping_revision": 2,
  "mode": "PAYMENT_2WAY",
  "policy": {
    "max_days_diff": 3,
    "currency": "VND",
    "auto_confirm_mode": "STRICT",
    "max_group_orders": 3,
    "max_split_bank_rows": 3,
    "max_group_block_size": 20,
    "max_combinations_per_bank": 2000,
    "fuzzy_candidate_threshold": 85,
    "fee_policy_id": null
  }
}
```

**Không** cho client tự truyền `rule_version` giả; BE lấy version từ engine release. `fee_policy_id=null` có nghĩa chưa chứng minh phí.

## 17.4. Ví dụ group detail response (rút gọn)

```json
{
  "run_id": "run_123",
  "revision": 3,
  "group_id": "G-101",
  "group_type": "MANY_ORDERS_ONE_BANK",
  "link_status": "CONFIRMED",
  "payment_status": "FULL",
  "review_status": "NOT_REQUIRED",
  "orders": [
    {"order_id": "O-001", "expected_amount_minor": 300000},
    {"order_id": "O-002", "expected_amount_minor": 200000}
  ],
  "bank_transactions": [
    {"bank_txn_id": "B-001", "posted_amount_minor": 500000}
  ],
  "allocations": [
    {"order_id": "O-001", "bank_txn_id": "B-001", "cash_minor": 300000},
    {"order_id": "O-002", "bank_txn_id": "B-001", "cash_minor": 200000}
  ],
  "reason_codes": ["MULTI_FULL_REFERENCE", "EXACT_TOTAL", "NO_CONFLICT"],
  "explanation_vi": "Giao dịch ghi rõ hai mã đơn và tổng tiền khớp."
}
```

Trong minh họa, `review_status=NOT_REQUIRED` cho biết group đã auto-confirm và không có review manual; `OPEN` chỉ dùng cho proposal đang chờ người duyệt. DTO chính thức: `review_status=NOT_REQUIRED | OPEN | APPROVED | REJECTED | UNDONE | NEEDS_MORE_INFO`.

## 17.5. Mã lỗi API

| HTTP | Trường hợp | Hành động frontend |
|---|---|---|
| 400 | Format upload, sheet chọn không hợp lệ | Hiện thông báo sửa |
| 413 | File quá giới hạn | Hiện size limit |
| 422 | JSON/schema/mapping field validation sai | Hiện từng field |
| 409 | Health Gate chưa sẵn sàng; stale review revision; allocation conflict | Hiện nguyên nhân cụ thể và reload nếu cần |
| 404 | Run/session đã mất/hết TTL | Thông báo upload lại/không tồn tại |
| 500 | Internal unexpected failure | `request_id` + UI retry phù hợp, log không lộ raw |

`error_code` là ổn định, ví dụ `HEALTH_BLOCKED`, `ALLOCATION_CONFLICT`, `STALE_REVISION`, `UPLOAD_EXPIRED`, `CURRENCY_MISMATCH`, `INVALID_MAPPING`. API trả timestamps timezone ISO 8601, số tiền dùng integer minor units + currency, Pydantic DTO, cursor/page pagination, filter whitelist, size limits, CORS localhost theo môi trường.

---

# 18. FRONTEND REACT — SƠ ĐỒ MÀN HÌNH VÀ UX

## 18.1. Navigation

```text
Dashboard / Lịch sử phiên
  ├─ Tạo phiên mới
  │   1 Upload / Data sample
  │   2 Mapping / Data preview
  │   3 Data Quality / Resolve
  │   4 Cấu hình / Run
  │   5 Dashboard / Review
  │   6 Export / Reopen
  └─ Research metrics (chỉ dev/benchmark)
```

**UI tiếng Việt** là mặc định, dùng thuật ngữ tiếng Anh chính xác trong tooltip. Mỗi trường tiền hiển thị `VND`/`BRL`, date format, nguồn, currency scale. Không hiển thị điểm heuristic kiểu "95% khả năng đúng" khi chưa calibrate.

## 18.2. Màn hình 1 — Tạo run / upload

- Chọn `Sử dụng dữ liệu demo` hoặc `Tải dữ liệu của tôi`.
- Hai dropzones: **Đơn hàng/Khoản phải thu** và **Ngân hàng/PSP**; tùy chọn một XLSX 2 sheets.
- Hiển thị giới hạn file, trạng thái upload, số rows/sheets, import preview.
- Chọn source profile `BANK_TRANSFER` hoặc `PSP_SETTLEMENT` đúng nguồn; profile gợi ý cần người dùng xác nhận.
- Nút `Tiếp tục ánh xạ cột` disabled nếu upload chưa hợp lệ.

## 18.3. Màn hình 2 — Mapping/Preview

- Bảng mapping `required canonical field` → `source column`; đánh dấu required/optional/suggestion.
- Preview 20 rows input + canonical output cạnh nhau, highlight parse mismatches.
- Chọn parse date/currency/thousand separators/sheet/timezone.
- Cảnh báo `order_ref` string leading zeros, ambiguous date formats, column absent.
- Có saved mapping profiles cho demo local, nhưng không auto-apply mapping cũ khi schema khác mà không thông báo.

## 18.4. Màn hình 3 — Data Health

- Ba nhóm: blocking, warning, info; danh sách issue có affected rows, sample, nguyên nhân.
- Action: remap, exclude có lý do, sửa định dạng, confirm defaults hoặc acknowledge warning.
- Health Gate luôn có trạng thái; nếu blocking còn tồn tại ⇒ không cho Run.
- Có `download health report` JSON/HTML ở dạng tùy chọn.

## 18.5. Màn hình 4 — Cấu hình & chạy

- Profile `Strict (an toàn, mặc định)` hoặc `Review-friendly` (tăng ứng viên, **không tự tăng auto-confirm**).
- Sliders max lag 0–7 ngày, candidate score 70–95, group size ≤ 3 (có thể config advanced 4), policy fee gắn chứng cứ.
- Mỗi slider có tooltip **tác động**; thay đổi sau run là **run mới**, không đổi âm thầm history.
- Button `CHẠY ĐỐI SOÁT`; hiển thị trạng thái `Queued / Running / Completed / Failed`, lỗi dễ hiểu và retry theo logic.

## 18.6. Màn hình 5 — Dashboard + Review

**Tab A Tổng quan**: 6 KPI money/order/bank; funnel/chart; distribution; top unresolved; breakdown 1:1 / N:1 / 1:N.

**Tab B Cần xác minh**: table proposals/cases, grouping column, order/bank participants, expected vs posted vs allocated vs residual, reasons/evidence, competing proposals. Chọn group mở side panel; **Approve/Reject/Undo** có confirm dialog trước commit.

**Tab C Đối soát chi tiết**: filters `confirmed link`, `fully paid`, `partial`, `unmatched`, `orphan`, `duplicated`; click source row mở provenance.

**Tab D Lịch sử và xuất**: run metadata/config/rule version/input hashes, review log, báo cáo XLSX/CSV, download report snapshots theo revision.

**Tab E Evaluation chỉ dev**: precision/recall/F1, allocation accuracy, scenario metrics, confusion matrix với holdout; không hiển thị cho dữ liệu user bình thường không có truth.

## 18.7. Hợp đồng màu và tương tác

- Xanh = đã xác minh/settled đủ theo policy, không phải "độ chính xác xác suất 100%".
- Vàng = cần con người xem/đang có chênh tiền/đề xuất chưa chốt.
- Đỏ = chưa xác định nguồn đối ứng, lỗi dữ liệu, ngoại lệ chưa xử lý.
- Dùng **text + icon + status**, không chỉ màu, để hỗ trợ accessibility.
- Review button disabled nếu `proposal_state=CONFLICTED` hoặc revision cũ; cho refresh.
- `Approve` không tự điền allocation thiếu; người dùng có thể chỉnh phân bổ trong giới hạn với validation real-time.
- Mọi kết quả chỉ dựa API, frontend **không chứa** logic matching hoặc phép tính cash business mới.

---

# 19. NOTEBOOK NGHIÊN CỨU — KHÔNG LÀ ENGINE THỨ HAI

**Tên file:** `notebooks/reconciliation_research.ipynb` (plus notebooks nhỏ tùy chọn). Chạy sạch từ kernel mới `Restart & Run All` thành công bằng `uv run jupyter lab`/VS Code kernel.

### Các phần bắt buộc theo thứ tự

1. **Mục tiêu và research questions**: Vì sao bank/orders không khớp 1:1? Các giả thuyết tham khảo.
2. **Dataset provenance**: Olist observed vs synthetic bank, license/limitations, manifest/checksums.
3. **Raw data overview**: schema/counts/null/duplicates/currency/time, EDA Olist payment granularity.
4. **Before vs After normalize**: cột ref, ngày, amount, ngân hàng vs nội bộ.
5. **Health Gate**: các issue có mẫu, cases bị exclude và lý do.
6. **L1 strong/exact**: SQL DuckDB join, link evidence, output không bị double-use.
7. **L2 constrained**: ngày T+N, amount/PSP fee hypotheses, policy variations.
8. **L3 fuzzy**: RapidFuzz, unique candidate, false positives, guardrails.
9. **L4 bounded group/split**: đồ thị nhóm, subset, allocated edges; bài toán conflict.
10. **Post-process**: partial/over, orphan, duplicate, exceptions, cash conservation.
11. **Evaluation**: edge precision/recall/F1, group accuracy, amount metrics, review/coverage.
12. **Ablation**: A0 exact; A1 + constrained; A2 + fuzzy; A3 + group/split; A4 policy/feature changes (ghi rõ thay đổi thứ tự so với conceptual waterfall nếu cần).
13. **Error analysis**: false auto accept, false proposals, mismatch của Olist raw vs synthetic.
14. **Performance**: 100, 1k, 10k, >=50k/100k orders nếu máy chịu được; runtime, memory, candidates generated.
15. **Reproducibility/report**: manifest, code SHA, parameter table, conclusion, limitations, generated figures/tables.

**Yêu cầu kỹ thuật:** Notebook import `from smartrecon.engine import run_reconciliation` và gọi cùng function backend. Các `SELECT` phục vụ minh họa được phép thực thi trực tiếp DuckDB, nhưng *không có một code path thứ hai* quyết định matched/unmatched; mọi thử nghiệm thuật toán gọi public core với flags/config để so sánh.

**Không đánh giá matching chỉ bằng so `ground_truth_case` với tên lớp dự đoán**: cần so từng cặp `(order_id,bank_txn_id)`, group memberships và lượng cash. Confusion matrix case-level là phụ, không thay thế link-level precision.

---

# 20. EVALUATION PROTOCOL VÀ TIÊU CHÍ KỸ THUẬT

## 20.1. Ground truth unit

- `truth edge`: cặp ID thực sự có quan hệ thanh toán, với `cash_minor`.
- `truth group`: tập orders/banks tạo thành một nhóm liên kết thực sự; group ID của generator là metadata để eval, không dùng matching.
- `truth case`: missing/orphan/ambiguous/fee/overpay/duplicate khi không có edge hoặc có nhiều nhãn.

`predicted` trong metric auto-confirm là **confirmed by engine before human review**. Khi muốn đo end-to-end sau analyst review, báo **metric khác**, không trộn.

## 20.2. Formulas bắt buộc

Ký hiệu `TP`, `FP`, `FN` so sánh **tập cặp** đã auto-confirm với tập cặp truth:

```text
edge_precision = TP / (TP + FP)
edge_recall    = TP / (TP + FN)
edge_F1        = 2 * precision * recall / (precision + recall)
```

Khi mẫu số bằng 0, định nghĩa `N/A` rõ thay vì tự coi 1.0. Trong các bộ hard-case có truth edges, precision là chỉ tiêu rủi ro **false auto-confirm** quan trọng.

**Group exact-match rate:** một nhóm predicted được coi đúng nếu **tập order IDs và tập bank IDs** trùng truth group hoàn toàn. Báo group precision và recall trên tập group nếu cách đếm phù hợp; tránh accuracy "mọi group" khi no-group cases làm loãng kết quả.

**Allocation accuracy:** `MAE_cash_minor` trên truth/predicted edges cùng matched pair, cộng thêm **total misallocated cash**/signed deltas cho missing/extra edges; `allocation_exact_group_rate` khi toàn bộ edge amounts bằng truth; `cash_conservation_violations` phải **0** trên valid fixtures.

**Exception precision/recall**: measured separate by reason class (under/over/orphan/duplicate/ambiguous), không gộp làm edge precision.

**Coverage/ops:** số orders/bank rows fully confirmed, fraction pending review, value review, p50/p95 runtime và memory. Phân biệt `unresolved due to missing evidence` vs `truth genuinely missing`.

## 20.3. Holdout và ablation

- Chia dataset theo **original order/customer/source group** trước khi synthetic augmentation; không để case variants cùng nguồn vào dev và test.
- Bộ `development` dùng tune `max_days`, fuzzy threshold, scoring and group policy; `holdout` khóa sau khi freeze config.
- Tạo ablation để đo riêng gain và false-positive trade-off từ `amount/date`, text fuzzy, grouped/split.
- Báo per scenario + confusion analysis, không chỉ accuracy aggregate.
- Bảo đảm mỗi test run ghi data profile, hashes, seed, rule version, code commit, policy JSON; artifact kết quả nằm trong `reports/benchmark_runs/<run_id>`.
- Có `benchmark` so với **simple exact baseline trong chính repo mới**; không dùng số README ReconEngine như baseline thực nghiệm của dự án.

## 20.4. Quality gates đề xuất (cần benchmark để hiệu chỉnh)

**Release blockers tuyệt đối:**

- 100% tests kiểm tra **cash/order invariants** pass trên valid fixtures.
- 0 confirmed allocation lặp dùng vượt bank cash.
- 0 input truth field được đọc bởi engine khi chạy benchmark.
- 0 auto-confirm ở **fixtures được thiết kế purposely ambiguous**.
- 100% scenario N:1, 1:N, partial/over, orphan, duplicate có thể biểu diễn/report đúng trên fixtures.
- API và Notebook cùng result checksums khi cùng inputs/config/engine version.
- Không silently override raw/mapping; mọi review action có audit + đúng revision conflict behavior.

**Targets nghiên cứu (không cam kết số liệu chưa đo):** trên holdout hard set, chọn chính sách tối ưu **precision auto-confirm cao**, kèm recall/coverage/review rate; không đặt mục tiêu Precision=100% universally. Hiệu năng đo bằng cùng phần cứng & batch size, không khẳng định DuckDB luôn nhanh hơn SQLite tỷ lệ cố định.

---
# 21. SOURCE TREE VÀ HỢP ĐỒNG ENGINE DÙNG CHUNG

## 21.1. Cấu trúc chuẩn cho repository mới

```text
smart-financial-reconciliation/
├── README.md
├── LICENSE                           # Chọn license code độc lập sau khi xét quyền dữ liệu
├── pyproject.toml                    # Python package, dev extras, tooling
├── uv.lock                           # Lock dependency
├── .python-version
├── .env.example                      # KHÔNG có secrets
├── .gitignore
├── .github/
│   └── workflows/
│       ├── python-ci.yml
│       └── frontend-ci.yml
├── docs/
│   ├── 00_PROJECT_SCOPE.md
│   ├── 01_ARCHITECTURE_ADR.md
│   ├── 02_DATA_CONTRACT.md
│   ├── 03_MATCHING_POLICY.md
│   ├── 04_MONEY_INVARIANTS.md
│   ├── 05_GROUND_TRUTH_AND_GENERATOR.md
│   ├── 06_EVALUATION_PROTOCOL.md
│   ├── 07_API_CONTRACT.md
│   ├── 08_UI_UX_SPEC.md
│   ├── 09_TEST_PLAN.md
│   ├── 10_SECURITY_AND_RETENTION.md
│   ├── 11_DATA_ATTRIBUTION_LICENSE.md
│   ├── 12_SETUP_WINDOWS.md
│   └── 13_DEMO_GUIDE.md
├── configs/
│   ├── demo_brl.yaml
│   ├── demo_vnd.yaml
│   └── matching_strict.yaml
├── src/
│   └── smartrecon/                  # Core hoàn toàn mới, framework-agnostic
│       ├── __init__.py
│       ├── engine.py                 # Public API DUY NHẤT
│       ├── config.py                 # Typed run policy/config
│       ├── domain/
│       │   ├── models.py             # Order, Bank, Group, Edge, Evidence, Adjustment
│       │   ├── statuses.py
│       │   ├── money.py              # Decimal → minor units
│       │   └── invariants.py
│       ├── ingestion/
│       │   ├── readers.py            # CSV/XLSX, raw metadata
│       │   ├── mapping.py            # suggestions and explicit confirmation
│       │   ├── normalize.py
│       │   ├── references.py         # Multi-token regex and safe boundaries
│       │   └── lineage.py
│       ├── quality/
│       │   ├── checks.py
│       │   ├── gate.py
│       │   └── resolutions.py
│       ├── matching/
│       │   ├── blocking.py
│       │   ├── strong_ref.py          # L1
│       │   ├── constrained.py         # L2
│       │   ├── fuzzy.py               # L3
│       │   ├── grouping.py            # L4 N:1
│       │   ├── splitting.py           # L4 1:N
│       │   └── conflict_resolver.py
│       ├── allocation/
│       │   ├── calculator.py
│       │   ├── adjustments.py
│       │   └── conservation.py
│       ├── exceptions/
│       │   ├── classifier.py
│       │   └── codes.py
│       ├── analytics/
│       │   ├── duckdb_queries.py
│       │   ├── kpis.py
│       │   └── chart_datasets.py
│       ├── evaluation/
│       │   ├── truth_loader.py
│       │   ├── edge_metrics.py
│       │   ├── group_metrics.py
│       │   └── amount_metrics.py
│       └── reporting/
│           ├── export_model.py
│           ├── excel_export.py
│           └── csv_export.py
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── routes_uploads.py
│   │   ├── routes_runs.py
│   │   ├── routes_results.py
│   │   ├── routes_reviews.py
│   │   ├── routes_exports.py
│   │   └── routes_demo.py
│   ├── schemas/                      # Pydantic request/response
│   ├── services/                     # Orchestration; không duplicate logic matching
│   └── persistence/
│       ├── database.py
│       ├── models.py
│       ├── repositories.py
│       └── migrations/
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── app/
│       ├── api/                     # Generated/manual typed client
│       ├── components/
│       ├── features/
│       │   ├── upload/
│       │   ├── data-health/
│       │   ├── run-config/
│       │   ├── dashboard/
│       │   ├── review/
│       │   ├── explorer/
│       │   └── exports/
│       ├── charts/
│       └── types/
├── scripts/
│   ├── prepare_olist.py
│   ├── generate_demo.py
│   ├── generate_hard_eval.py
│   ├── generate_vn_demo.py
│   ├── verify_generated_data.py
│   └── benchmark.py
├── notebooks/
│   └── reconciliation_research.ipynb
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── property/
│   ├── api/
│   ├── e2e/
│   └── fixtures/
├── data/
│   ├── raw/                      # .gitignore, theo nguồn/license
│   ├── demo/                     # có thể generated bằng scripts
│   └── benchmark/                # .gitignore large files
├── storage/                      # .gitignore
└── reports/
    └── benchmark_runs/          # artifacts generated
```

**Không bắt buộc sinh ngay mọi file rỗng**. Cấu trúc này là **đích kiến trúc**; milestones tạo file khi có domain contract và test tương ứng. Tránh một file `reconcile_engine.py` chứa hết mọi module và tăng khó bảo trì.

## 21.2. Engine public API

```python
from smartrecon.engine import inspect_inputs, run_reconciliation

# Data adapters trả nguồn dữ liệu + mapping info; notebook và BE gọi cùng core.
health = inspect_inputs(inputs=source_bundle, mapping=confirmed_mapping, policy=policy)
result = run_reconciliation(
    inputs=source_bundle,
    mapping=confirmed_mapping,
    policy=policy,
    run_context=run_context,  # chứa rule version, source hashes, deterministic IDs
)
# result.groups / .allocations / .proposals / .exceptions / .kpis / .manifest
```

Đây là **API mục tiêu**, chưa phải mã hiện tồn tại. Các type `SourceBundle`, `ConfirmedMapping`, `ReconciliationPolicy`, `ReconciliationResult` cần được khai báo với typing/static schema. Nếu API trả Arrow/Parquet references cho kết quả lớn, có contract để notebook và backend cùng đọc hiệu quả.

## 21.3. Dependency rules

- `smartrecon.domain` không import FastAPI/React/SQLAlchemy.
- `smartrecon.matching` không import truth/evaluation hay backend storage.
- `backend` có thể import `smartrecon`, không reverse import.
- `evaluation` có thể import public engine + truth, không cho matching sử dụng truth.
- `frontend` chỉ gọi backend JSON; không tự khẳng định rules/status.
- `scripts/generator` độc lập với run matching, có thể dùng shared models/config schema nhưng không làm source of truth cho actual matching.

---

# 22. KIỂM THỬ — TỪ UNIT ĐẾN END-TO-END

## 22.1. Unit tests

- Money conversion BRL/VND; Decimal rounding, separators, negative amount/direction.
- Date parsing UTC/local timezone, `03/04` ambiguity, T+1/T+3, missing value_date.
- Reference normalization and multi-token extraction; exact token boundary; digit guard not standalone.
- Health missing columns, invalid mapping, unsupported statuses, duplicates and exclusions.
- Strong ref match, constrained review, fuzzy candidate score, missing features, tie/ambiguous.
- N:1 / 1:N allocation, partial, excess, fee adjustment, refund/debit exclusion.
- Candidate graph conflict resolver; no bank cash double use.
- KPI distinct counts; matching stats denominator tests; TSV/CSV/XLSX parity.

## 22.2. Property/invariant tests

Dùng pytest parametrize hoặc Hypothesis (nếu cài) để tạo tổ hợp ngẫu nhiên hợp lệ:

- `sum(A)+U=C` cho mọi bank credit.
- `sum(A)+F+R=E` cho mọi order eligible.
- `PROPOSED` không làm tăng confirmed allocation.
- Không có cross-currency confirmed edge trong MVP.
- Order/bank input permutation không thay đổi kết quả semantic (stable normalized sort) trừ deterministic surrogate row IDs gắn source position — xác minh expected identity boundaries.
- Generator seed + input version cho output byte-identical hoặc semantic-identical đã khai báo rõ (JSON/CSV ordering). Không random ID ngẫu nhiên ngoài seed.
- Rerun cùng source/config/rule version cho semantic checksum trùng; timestamp metadata có thể khác nhưng không nằm trong checksum nghiệp vụ.

## 22.3. Integration and API tests

1. Upload hai file CSV, xác nhận mapping, health gate open, run.
2. Upload workbook XLSX hai sheet, kết quả bằng bộ CSV tương ứng.
3. Blocking health ngăn run; exclusion có log và ảnh hưởng đúng KPIs.
4. Review APPROVE group N:1, cập nhật `U(b)`/`R(o)`/KPI đúng.
5. Hai request approve cùng bank và stale revision: một request phải bị 409/conflict.
6. REJECT proposal mở lại candidates đúng, không ép mọi participant đỏ.
7. UNDO action tạo revision mới và audit đầy đủ, chặn undo nếu có dependency phá invariant.
8. Export XLSX/CSV sau review phản ánh **revision được yêu cầu**, không nhầm kết quả base.
9. Restart server và mở run đã hoàn thành, dữ liệu từ SQLite + artifacts vẫn dùng được.
10. API/Notebook semantic result checksum giống nhau.

## 22.4. Frontend E2E tests

- Tạo dữ liệu mẫu → upload/preview → mapping → health → run → dashboard → review group → export Excel.
- Upload lỗi hiện thông báo tiếng Việt rõ; field invalid được highlight.
- Ứng viên mơ hồ không có nút auto match tất cả.
- `Approve` group có confirmation và preview các allocations; UI cập nhật sau success.
- Export sau review trả đúng các sheet; nhập Excel có leading-zero ID vẫn chuẩn.

## 22.5. Security-related tests

- Formula-injection Excel/CSV: chuỗi bắt đầu `=`, `+`, `-`, `@` từ user data được escape/force text **trong ô output dạng text**, không phá số tiền thật; trường hợp dấu trừ là số âm phải xử lý theo kiểu dữ liệu trước khi export.
- Path traversal trong filenames, malicious/invalid zip XLSX, zip bomb qua limits, không execute macros.
- Upload content-type mismatch; file quá lớn/sheet quá nhiều/row count over limit.
- Safe file downloads, no file path leakage, no SQL injection qua filter/sort (parameterized queries/whitelists).
- Logs không ghi toàn bộ tên khách/statement hoặc raw file content.

## 22.6. Release-blocking checklist (đóng P0)

- [ ] Tất cả fixture nghiệp vụ ở §6.4 pass.
- [ ] 0 conservation violations.
- [ ] 0 false auto-confirm trên các fixture purposely ambiguous.
- [ ] 0 data truth leakage.
- [ ] 0 unreviewed automatic fee write-off.
- [ ] 0 behavior phụ thuộc thứ tự dòng nhập ngoài định danh source metadata.
- [ ] API contract + Notebook integration tests pass.
- [ ] Windows setup từ clone sạch hoạt động.
- [ ] Có bản demo video/script và giải thích chính xác giới hạn.

---

# 23. PERFORMANCE, OPERABILITY VÀ BẢO MẬT

## 23.1. Performance test matrix

| Dataset | Quy mô | Phép đo |
|---|---:|---|
| Small fixture | 20–100 orders | correctness & explanations |
| Demo story | 80–120 | responsiveness website |
| Hard eval | 1.000–3.000 | precision/recall/false match; time |
| Medium | 10.000 | ingestion, candidate counts, memory, export |
| Large | 50.000–100.000+ nếu máy phù hợp | p50/p95 runtime, peak memory, scale behavior |

Không nên hứa các con số tính bằng giây khi chưa đo. Ghi CPU/RAM/Python/DuckDB version, format, OS, source profile, candidate limits, config, warm/cold run cho mọi kết quả benchmark. Các benchmark 99.441 order trong README repo tham khảo **không** thay thế kết quả đo engine mới.

## 23.2. Các giới hạn hợp lý ở MVP

- `max_files_per_upload=2` logic sources hoặc 1 workbook 2 sheets.
- `max_upload_mb_per_file=25` default thử nghiệm; có cấu hình.
- `max_rows_per_feed=100000` default demo, benchmark CLI có thể hơn.
- `max_group_orders=3` default, `max_split_bank_rows=3` default; research mode có thể 4.
- `max_block_size=20`, `max_combinations_per_case=2000`, `max_candidates_per_item=5` hiển thị.
- `processing_timeout`/memory budget và thông báo `PARTIAL_SEARCH_EXHAUSTED` (nếu search không đủ, không auto-confirm bằng kết quả một phần).
- Single backend instance cho local demo; nếu triển khai multi-worker, review storage/concurrency và job queue cần thiết kế lại phù hợp.

## 23.3. Quyền riêng tư và bảo mật

- Dữ liệu ngân hàng chứa thông tin nhạy cảm; dùng synthetic demo mặc định.
- Không bật public deployment nếu chưa có login/auth, access control theo run, rate limit, HTTPS và isolation.
- `.env`/secrets không commit; `.gitignore` raw datasets/DB/storage; redact logs.
- Kiểm soát nguồn open-source/code/license/data license, dependency scanning, lock versions, reproducible builds.
- Data retention, backup, cleanup và quyền xóa run được ghi `10_SECURITY_AND_RETENTION.md`.
- Review decisions không được hiển thị như giao dịch ngân hàng được hoàn tiền/hạch toán thật: hệ thống demo **chỉ đánh dấu đối soát**, không gọi external payment APIs.

## 23.4. Observability

Cần `request_id`, `run_id`, `run_revision`, `policy_hash`, `rule_version`; counters `rows_read`, `rows_excluded`, `strong_candidates`, `fuzzy_candidates`, `group_candidates`, `conflicts`, `confirmed_edges`, `review_required`, `invariant_errors`, `elapsed_ms_by_step`. Log metadata tổng hợp, không dump statement records.

---

# 24. ROADMAP M0–M8 VÀ ĐIỀU KIỆN NGHIỆM THU

**Quy tắc điều hành:** Không triển khai kiểu "tạo toàn bộ codebase trong một prompt" mà chưa test. Mỗi milestone kết thúc bằng **code + test + demo evidence + tài liệu cập nhật**. Trình tự chủ đạo là `M0 → M1 → M2 → M3 → M4`, sau đó có thể làm API/UI sớm từng phần nếu contract đã freeze.

## M0 — Project Foundation & Architecture

**Mục tiêu:** có repo mới sạch và một nguồn sự thật về schema/nghiệp vụ.

**Công việc:**
- Tạo GitHub repository **mới**, branch `main`, `.gitignore`, `pyproject.toml`, `uv.lock`/tooling, frontend skeleton.
- Viết `00_PROJECT_SCOPE`, `01_ARCHITECTURE_ADR`, `02_DATA_CONTRACT`, `04_MONEY_INVARIANTS`.
- Chốt `internal_receivables` vs bank/PSP profile, strict auto policy, một currency/run.
- Thiết lập Ruff/pytest/GitHub Actions CI, pre-commit nếu muốn.
- Viết data models/domain types + 3–5 test bất biến cơ bản, chưa làm UI business.

**Output:** repo mới chạy import package, tests skeleton green, ADR chốt FE React, DuckDB analytics, SQLite app state.

**Gate:** Không còn dependency nhập từ repo ReconEngine; nhóm hiểu nghĩa `cash_allocation` vs `fee_adjustment`.

## M1 — Data Contract, Olist & Scenario Generator

**Mục tiêu:** có dữ liệu chạy được và truth đáng tin trước khi viết matcher lớn.

**Công việc:**
- Adapter đọc Olist gốc; xác minh source provenance/license.
- Tạo `demo_story` BRL, `vn_synthetic_demo` VND và `evaluation_hard` generator.
- Xuất two-feed CSV + XLSX 2 sheets, `truth_edges`, `truth_cases`, `manifest`.
- Implement 20 fixture nghiệp vụ, seed reproducibility.
- Test không leakage, không orphan/labeled-pair lỗi và conservation truth.

**Gate:** Cùng seed/config generator tái lập; tất cả case có truth đúng; no generated bank memo leak ngoài scenario intended.

## M2 — Ingestion, Mapping, Normalization & Health

**Mục tiêu:** hai file input được chuyển thành canonical sạch/an toàn.

**Công việc:**
- CSV/XLSX readers, sheet selector, encoding/profile parse.
- Mapping suggestion + explicit confirm; IDs string, currency/minor units, ref extractor list.
- Blocking/warning/info Health Gate, data exclusions với lineage.
- Implement `inspect_inputs` và unit/integration tests.

**Gate:** cùng dữ liệu CSV và XLSX ra canonical semantic-equal; invalid/duplicate/currency issue không bị silently bỏ qua.

## M3 — Matching L1/L2 + Cash Allocation Base

**Mục tiêu:** exact 1:1 hoạt động và cash conservation không sai.

**Công việc:**
- Strong reference matcher và policy T+N; no-conflict commit.
- Monetary model cash edges/residual; partial/over.
- No ref => proposed; conflict candidate graph base.
- Tests money, strong refs, missing bank, orphan bank, amount mismatch.

**Gate:** 1:1 exact, T+N, partial/over, orphans pass; no double use; KPIs consistent.

## M4 — Matching N:1, 1:N, Fuzzy, Review Candidates

**Mục tiêu:** đầy đủ bài toán cốt lõi và waterfall 4 lớp.

**Công việc:**
- Discover multi-refs, group N:1, split 1:N, conflict-aware approach.
- DuckDB blocking/group SQL, bounded combinations and resource budgets.
- RapidFuzz candidates + guardrails; ambiguity and duplicate classifications.
- Group/edge evidence, reason codes, explanation_vi; fee hypotheses only review.
- Update all invariants and hard adversarial tests.

**Gate:** 20 fixtures nghiệp vụ pass; 0 false auto-confirm trên ambiguous tests; groups represent correct allocations; all reason codes traceable.

## M5 — Notebook & Evaluation Benchmark

**Mục tiêu:** chứng minh engine mới hoạt động chính xác, nêu rõ giới hạn.

**Công việc:**
- Notebook 15 phần, EDA, từng matching layer, SQL queries explanations.
- Edge/group/amount metrics, confusion matrices riêng, per-scenario breakdown.
- Dev/holdout protocol, ablation, false-positive analysis.
- Runtime/memory runs 100/1k/10k/+; baseline exact trong repo mới.

**Gate:** Notebook Restart & Run All pass, metric artifacts/versioned, truth không import vào core, kết luận chỉ dựa số đã đo.

## M6 — FastAPI + SQLite Persistence

**Mục tiêu:** website gọi được engine mới qua REST và có lịch sử/duyệt.

**Công việc:**
- Implement endpoint upload/health/run/results/groups/exceptions.
- SQLite data models/migrations + effective revision/audit.
- Review approve/reject/undo transaction + idempotency/revision conflict.
- XLSX/CSV export service; restart/reopen runs.
- Tests upload MIME/security, API DTO, concurrency, review transaction, export.

**Gate:** Curl/Postman qua toàn luồng, Swagger/OpenAPI stable, 409 stale revision, report đúng các bảng và revision.

## M7 — React Website + Dashboard & Export

**Mục tiêu:** người dùng không biết Python có thể thao tác mọi thứ trên web.

**Công việc:**
- UI multi-step upload/mapping/health/config.
- Dashboard Plotly, tables filtering/pagination, drilldown group/edge/source rows.
- Review workspace approve/reject/undo và real-time API refresh.
- Run history, export buttons, error/accessibility states.
- Playwright E2E/UX smoke tests.

**Gate:** demo end-to-end không mở notebook, biên bản P0 UI errors, số tiền charts khớp API.

## M8 — QA, Release & Handoff

**Mục tiêu:** deliverable nhất quán và trình diễn có kiểm chứng.

**Công việc:**
- Full integration regression, security/performance basic, cleanup data/license check.
- README Windows PowerShell, `.env.example`, setup scripts, demo profiles.
- Demo walkthrough 7–10 cases, video/screenshots/report artifacts.
- Release tag v1.0.0-demo, known limitations, issue backlog Phase 2.

**Gate:** clone sạch trên máy Windows khác có thể chạy theo README; 0 P0 correctness bugs, full test suite & E2E pass.

### Milestone dependency graph

```text
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5 ──┐
              │               │            │
              └── API schema draft ──────► M6 ──► M7 ──► M8
                        (FE wireframe có thể tiến hành song song)
```

**Đừng dùng mốc số để suy đoán bắt buộc làm mọi backend sau Notebook:** FastAPI upload/health có thể xây sớm ngay sau M2 khi contract đã ổn, nhưng **không merge business logic copy** vào backend. Kế hoạch này dùng milestone để kiểm soát nghiệm thu, không phải cấm mọi song song.

---

# 25. PHÂN CÔNG, GIT, CI VÀ LÀM VIỆC VỚI CODING AGENT

## 25.1. Phân vai cho nhóm hai người (nếu hợp tác)

**Người A — Data & Core Owner:** Olist adapter, generator/truth, ingestion/health, reference grammar, L1–L4 matcher, allocator, conflict resolver, core invariant tests.

**Người B — API, Analytics & UX Owner:** evaluation notebook, benchmarking (cùng A validate truth), FastAPI/Pydantic, SQLite/run history/review persistence, React UI, Plotly/dashboard, export, E2E tests.

**Cùng duyệt:** data dictionary, `amount_basis`, policy fee, group/edge invariants, ground truth format, metric definitions, HTTP DTOs. Không có ràng buộc phải làm trên repo `dpduc/ReconEngine`; repo mới có owner/branch hoàn toàn độc lập.

## 25.2. Git workflow

- `main` protected/stable nếu có thể.
- Một issue một nhánh: `feature/data-contract`, `feature/ingest-health`, `feature/group-split`, `feature/review-api`, `feature/dashboard`.
- PR ngắn, có title, scope, behavior tests, files affected, screenshots/API sample nếu phù hợp, migration notes, data/license impacts.
- CI trước merge: Ruff, pytest unit/integration, typecheck mức phù hợp, frontend build/lint, selected E2E.
- Không force-push/delete dữ liệu chung nếu chưa có xác nhận. Không push raw data và `.env`.
- Pin `uv.lock` và `package-lock.json`/`pnpm-lock.yaml`; versioned config and migrations.

## 25.3. Quy trình agent-assisted development

Không nên đưa một master prompt lớn yêu cầu AI "viết tất cả hoàn chỉnh ngay" vì dễ tạo code giả, tests trống, thiếu invariants và FE/BE dùng schema khác nhau. Dùng **spec-driven** theo từng milestone:

1. Đọc chính tài liệu V3 này và các file `docs/` đang có; xác nhận scope milestone.
2. Liệt kê design decisions/changing files, affected contracts, test acceptance **trước khi code**.
3. Viết tests quan trọng (đặc biệt conservation/ambiguous) rồi code nhỏ theo module.
4. Chạy command và báo **kết quả thực**, không tự tuyên bố pass/benchmark nếu chưa chạy.
5. Code review secret/license/no truth leakage; commit và push vào branch phù hợp.
6. Nêu file thay đổi, test command/output, rủi ro còn lại, bước tiếp theo.

### Hợp đồng giao việc chuẩn cho agent

```text
Đọc SMART_RECON_MASTER_PLAN_V3_FINAL.md.
Dự án này xây mới 100%, không import/copy code ReconEngine.
Chỉ thực hiện [MILESTONE/ISSUE] trong phạm vi đã định.
Không viết thuật toán matching vào FE hoặc FastAPI service: chỉ gọi public smartrecon.engine.
Tiền dùng Decimal/minor units, không float; raw input bất biến; ground truth tách khỏi matching.
Mọi xác nhận group phải thỏa conservation và conflict checks.
Trước khi sửa mã: trình bày files, API/type contracts, tests acceptance; sau đó mới implement.
Sau khi code: chạy Ruff + pytest liên quan + regression; không báo pass nếu chưa có log.
Không thay đổi dữ liệu thật, không push secrets, không force-push.
Trả summary gồm changes, commands/tests, known risks và PR/commit (nếu có quyền).
```

### Đề xuất 12 GitHub Issues đầu tiên

1. `SPEC: canonical orders/bank contracts + money policy`
2. `SPEC: allocation invariants + group/review state machine`
3. `DATA: Olist source adapter and attribution`
4. `DATA: 20 seeded fixtures + ground truth edges/cases`
5. `CORE: mapping/normalization/reference extractor`
6. `CORE: health checks and provenance`
7. `CORE: strong-ref and constrained 1:1 matching`
8. `CORE: grouped N:1 and split 1:N conservation`
9. `CORE: fuzzy proposals/conflict resolver/exception codes`
10. `EVAL: notebook, metrics, ablation and holdout benchmark`
11. `API: runs, review revisions/undo, Excel export`
12. `FE/QA: React wizard, dashboard, review E2E`

---

# 26. CHECKLIST TRIỂN KHAI, KỊCH BẢN DEMO VÀ DEFINITION OF DONE

## 26.1. Checklist trước khi **bắt đầu coding**

- [ ] Repo mới, tên/chủ sở hữu, cấu hình branch protection được chốt.
- [ ] Phạm vi hai nguồn: **đơn hàng/khoản phải thu + giao dịch credit**, không nhận nhầm là full general ledger.
- [ ] Quyết định `source_profile` BANK vs PSP và chính sách `amount_basis`.
- [ ] Chốt tiền BRL/VND và rounding; single currency/run cho MVP.
- [ ] Chốt enums cho `link_status`, `payment_status`, `review_status`, `ui_bucket`.
- [ ] Chốt `MatchGroup`, `AllocationEdge`, `Adjustment`, `ExceptionCase`, `ReviewAction`.
- [ ] Chốt 20 fixture nhỏ, đặc biệt fee/over/group/split/duplicate/ambiguous.
- [ ] Chốt `truth_edges`/`truth_cases` không có trong input.
- [ ] Quyết định frontend React, backend FastAPI, DuckDB analytics và SQLite state.
- [ ] Chốt API DTO/response money in minor units, pagination/409 conflict semantics.
- [ ] Ghi rõ Olist citation/license, dataset provenance và chính sách không commit raw.
- [ ] Viết 3 tài liệu tối thiểu: `02_DATA_CONTRACT.md`, `03_MATCHING_POLICY.md`, `04_MONEY_INVARIANTS.md`.

## 26.2. Ngay sau khi code có môi trường dev

**Các lệnh dưới đây là quy trình mục tiêu sau M0/M1; tại thời điểm soạn tài liệu, chưa tồn tại dự án mới để thực thi các lệnh.**

```powershell
# Tại thư mục repository mới, có Python 3.12 và Node.js LTS
uv sync --all-extras
uv run python scripts/generate_demo.py --profile vn_synthetic_demo --seed 42
uv run pytest -q
uv run ruff check .

# Terminal A — backend
uv run uvicorn backend.main:app --reload --port 8000

# Terminal B — frontend
cd frontend
npm install
npm run dev

# Notebook (cửa sổ terminal khác)
uv run jupyter lab
```

**Lưu ý:** Nếu đặt `cd frontend` rồi muốn chạy notebook, quay lại root repo. Sau khi có `uv.lock`, ưu tiên `npm ci`/lockfile cho CI và `uv sync --frozen` khi release; `npm install` lần đầu dùng khi khởi tạo package.

## 26.3. Script demo 10 case

1. Click `Dữ liệu demo VND`; mở hai bảng nguồn và nêu **synthetic**.
2. Mapping/health hiển thị `orders` và `bank`, sample rows.
3. Exact O001↔B001 khớp.
4. T+2 có ID đúng, tiền đúng, vẫn có giải thích `time lag`.
5. Memo sai case/hyphen normalize đúng; memo typo fuzzy **review**.
6. N:1 O002+O003↔B002; group detail hiện **hai edges** sum=bank.
7. 1:N O004↔B003+B004; amount split đúng.
8. Partial/over: phần thiếu vào outstanding; tiền thừa vào unapplied.
9. Ambiguous/PSP fee: cạnh tranh proposals; bank transfer thiếu không bị hạch toán phí tự động; thao tác manual approve hợp lệ.
10. Review undo, dashboard cập nhật, export workbook, mở lại run history và so metrics với truth trong notebook **chỉ demo research**.

**Chỉ trình diễn ca expected đúng sau khi fixture tests và integration tests pass**, không dựng demo output hardcode trong UI.

## 26.4. Excel export contract (khuyến nghị 9 sheets)

| Sheet | Nội dung |
|---|---|
| `01_TongQuan_KPI` | KPI theo orders/bank/money, policy, revision, input hashes |
| `02_Orders` | Từng khoản phải thu + eligibility, cash received, residual/status |
| `03_BankTransactions` | Từng bank row + allocated cash/unapplied + direction |
| `04_ConfirmedGroups` | Nhóm đã xác nhận, group type/evidence |
| `05_AllocationEdges` | Cạnh phân bổ tiền, bảng dài, no double count |
| `06_ReviewQueue` | Proposed groups/candidates và explanations |
| `07_Exceptions_Orphans` | Missing/orphan/duplicate/fee/ambiguous/partial/over |
| `08_ReviewAudit` | Duyệt/từ chối/undo, revision/timestamp/actor/note |
| `09_RunManifest` | Metadata, config/mapping hashes, version, source provenance |

Sheet `05_AllocationEdges` là **bằng chứng quan trọng nhất** cho N:1/1:N. Không chỉ xuất 4 sheet xanh/vàng/đỏ như đề xuất ban đầu vì sẽ mất nhóm và tiền phân bổ. CSV export là ZIP gồm các CSV tương đương (không đòi browser tải 9 lần), hoặc cho phép tải từng bảng.

### Excel formatting

- Header, filter, freeze panes, money/date formatting, conditional fill trên **trạng thái**.
- Sanitize formula injection cho user-origin strings.
- Ghi `report_revision` trên Summary/Manifest, timestamp xuất riêng; không dùng formula spreadsheet để tính thay cho backend.
- Nếu số rows vượt Excel sheet limit, phân sheet/ZIP CSV và thông báo, không tự cắt dữ liệu.

## 26.5. Definition of Done của một issue

Một issue chỉ được đánh dấu xong khi **(a)** behavior đúng spec, **(b)** tests có assertions ý nghĩa, **(c)** lệnh tests/CI chạy thực và ghi kết quả, **(d)** docs/API contract cập nhật, **(e)** không leak truth/secrets/license, **(f)** không phá conservation/revisions, **(g)** có PR được review khi làm nhóm.

---

# 27. RỦI RO, GIẢ ĐỊNH, GIỚI HẠN VÀ HƯỚNG NÂNG CẤP

| Rủi ro | Tác động | Phòng ngừa |
|---|---|---|
| Dùng Olist payment làm bank statement thật | Kết luận nghiên cứu sai | Gắn observed/derived/synthetic; truth sinh riêng |
| Memo generator luôn ghi đầy đủ order ID | Precision/coverage ảo | Hard cases missing/typo/conflict/holdout |
| Truth case nằm trong feed | Data leakage | Assert schema + code boundary tests |
| Amount/date-only auto-match | False financial link | Review default nếu thiếu independent evidence |
| `float`/rounding sai | Mất cân tiền | Decimal/minor units + invariant tests |
| Group bị exact 1:1 chiếm bank trước | Sai N:1/1:N | Pre-discovery multi-refs + global conflict resolver |
| Subset-sum phình tổ hợp | Timeouts | Blocking, budgets, no partial auto-confirm |
| Nhầm PSP net với gross receivable | Auto-accept thiếu tiền giả | Separate cash allocation/approved adjustment |
| Trùng bank import vs giao dịch thật | Double count hoặc drop sai | Stable IDs, fingerprint và review |
| Analyst đồng thời duyệt xung đột | Cùng cash phân bổ hai lần | SQLite atomic transaction, expected_revision, 409 |
| Dùng DuckDB như transaction DB đa process | Lock/state errors | SQLite app state, DuckDB analytics |
| Các chart dùng mẫu số khác | KPI đẹp nhưng sai | Contract explicit denominator, tests |
| FE/BE/Notebook mỗi nơi một engine | Drift | Single public Python API |
| Dữ liệu nhạy cảm bị đẩy lên Git/log | Privacy/security | `.gitignore`, demo synthetic, retention, redact |
| License của Olist/Repo tham khảo | Rủi ro chia sẻ/công bố | Attribution và xem xét điều kiện trước publish |
| Scope creep với FX, AI, 3PL, Docker | Chậm hoặc thiếu chất lượng lõi | Phase 2 sau khi MVP gates pass |

### Những giới hạn phải nói rõ trong README/report

- Hệ thống đối soát **bằng chứng và phân bổ dòng tiền**, không khẳng định đã thực hiện nghiệp vụ kế toán/kiểm toán độc lập.
- Missing bank **không** chứng minh khách chưa trả; trễ settlement hoặc thiếu feed có thể là nguyên nhân.
- Confidence/rule score **không** tự động là xác suất.
- Fuzzy group không phải bằng chứng tài chính mạnh.
- PSP fee hypotheses chỉ được tự động hóa khi có biểu phí/chứng từ hợp lệ và policy rõ.
- Olist-based bank feed là synthetic; kết quả đánh giá hard benchmark chưa chứng minh độ chính xác trên sao kê ngân hàng thật chưa được thử nghiệm.
- MVP local single-instance không phải hệ thống production banking multi-tenant.

### Backlog Phase 2 (chưa triển khai)

- Tích hợp 3PL/COD và chính sách thanh toán vận chuyển.
- Multi-currency/FX với rate source, quy tắc giá và audit treasury.
- Many-to-many general netting và intercompany transfers.
- PSP detailed settlement files, chargebacks/refunds/balances đầy đủ.
- Multi-user auth/RBAC, PostgreSQL, job queue, Docker/CI deployment, real bank connectors.
- Offline benchmarking trên dữ liệu đã được phép dùng và anonymized, nâng precision/coverage dựa on holdout.

---

# 28. TÀI LIỆU NGUỒN, GHI CÔNG VÀ QUYẾT ĐỊNH CUỐI CÙNG

## 28.1. Nguồn tham khảo có phân loại

**Ba tài liệu nội bộ làm cơ sở V2:**

1. `KE_HOACH_DU_AN_DOI_SOAT_MOI_DOC_LAP.md` — kế hoạch dự án độc lập V1.0.
2. Đề xuất mới do người dùng gửi ngày 14/10/2026 về DuckDB, RapidFuzz, Waterfall và Streamlit.
3. `ReconEngine_Ke_Hoach_Hop_Nhat_Chi_Tiet(1).md` và báo cáo audit cũ — **chỉ khai thác thông tin về dataset, business lessons, hạn chế matching**; *không áp quyết định hợp nhất source code từ những tài liệu này*.

**Nguồn công khai đã tham khảo/kiểm tra:**

- Repo tham khảo: https://github.com/dpduc/ReconEngine
- Olist dataset: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- DuckDB Concurrency: https://duckdb.org/docs/current/connect/concurrency
- DuckDB Excel Import: https://duckdb.org/docs/current/guides/file_formats/excel_import
- FastAPI File Upload: https://fastapi.tiangolo.com/tutorial/request-files/
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

Các chỉ số benchmark được ghi ở repo tham khảo là **số tác giả báo cáo**, không phải kết quả chạy lại của SmartRecon. Các nhận định về stack là quyết định thiết kế, **không phải số hiệu năng đã được kiểm chứng**. Ngày kiểm tra ghi đầu tài liệu; thư viện/cơ chế hỗ trợ cần khóa version và kiểm tra lại lúc coding.

## 28.2. Quyết định cuối cùng (ADR summary)

| ID | Quyết định | Trạng thái |
|---|---|---|
| ADR-001 | Project mới, Git repo độc lập; không fork/reuse code ReconEngine | CHỐT |
| ADR-002 | Nghiệp vụ hai nguồn internal receivables ↔ bank/PSP | CHỐT |
| ADR-003 | Group + cash allocation + separate adjustment là domain core | CHỐT |
| ADR-004 | Waterfall bốn lớp + exception post-process; global conflict guard | CHỐT |
| ADR-005 | Strict evidence default; fuzzy/amount-only chỉ proposed | CHỐT |
| ADR-006 | Decimal/minor units, 1 currency/run ở MVP, conservation bắt buộc | CHỐT |
| ADR-007 | DuckDB analytics + SQLite review persistence | CHỐT |
| ADR-008 | FastAPI + React là product stack; Notebook gọi same engine | CHỐT |
| ADR-009 | Olist observed + bank synthetic; truth & manifest tách khỏi input | CHỐT |
| ADR-010 | Review action transactional, auditable, undo versioned | CHỐT |
| ADR-011 | KPI orders/bank/money dùng mẫu số khác nhau, không double-count | CHỐT |
| ADR-012 | M0–M8 với acceptance tests trước full UI | CHỐT |
| ADR-013 | Ngưỡng fuzzy, group budgets, file limits là **initial configs** | CẦN BENCHMARK/HIỆU CHỈNH |
| ADR-014 | Olist attribution/redistribution compliance trước publish | CẦN XÁC NHẬN KHI PHÂN PHỐI |
| ADR-015 | Không dùng Streamlit làm FE sản phẩm; chỉ optional spike | CHỐT |

## 28.3. Bước bắt đầu hợp lý nhất

**Không code frontend trước.** Hành động mở đầu là tạo repo mới, chốt các `docs/` về source semantics, money invariants, statuses và truth schema; viết fixture **N:1, 1:N, partial, over, ambiguous, duplicate, fee**; sau đó mới làm data generator và matching core. UI/API contracts có thể được lên bản nháp song song, nhưng không dẫn dắt sai logic đối soát.

**Định nghĩa hoàn thành dự án Demo v1.0:** người dùng mở website, upload hai nguồn hoặc sample, mapping/health rõ ràng, chạy rule engine duy nhất, xem groups+allocation+explanations, duyệt/undo có audit, xem dashboard đúng mẫu số, export Excel có phân bổ và log, notebook đo metrics trên truth riêng, test/benchmark có artifacts, và clone trên Windows máy khác chạy lại được.

---

> **KẾT LUẬN:** Bản V3 là đặc tả thống nhất để xây một hệ thống Smart Financial Reconciliation & Analytics **mới hoàn toàn**, có nội dung vừa đủ sâu về dữ liệu, tiền, thuật toán, rủi ro false match, audit, API, dashboard, notebook và quy trình kiểm thử. Không sao chép khung code cũ hoặc một prompt ép agent sinh mọi thứ cùng lúc. Mọi quyết định chưa được thực nghiệm (như thresholds/throughput) được giữ là **giả định có thể đo và điều chỉnh**, không trình bày thành sự thật đã kiểm chứng.


---

# 29. PHỤ LỤC A — CÁC QUY TẮC KHÓA CHẶT TRIỂN KHAI

Phụ lục này bổ sung **hợp đồng bắt buộc** để khi giao lập trình không còn các cách diễn giải khác nhau giữa Python core, REST API, notebook và React. Nếu có khác biệt giữa ví dụ minh họa trong các chương trước và quy tắc ở đây, **ưu tiên phụ lục A**.

## A.1. Phân loại nghiệp vụ nhất quán

**Bắt buộc lưu độc lập:**

1. `link_status`: `CONFIRMED | PROPOSED | UNMATCHED | REJECTED` — độ chắc chắn của mối liên hệ nguồn.
2. `payment_status` **theo từng order**: `FULL | PARTIAL | OVERPAID | NO_CONFIRMED_RECEIPT | UNKNOWN | NOT_ELIGIBLE`. `OVERPAID` ở cấp order chỉ được dùng như **cờ có bank dư tiền liên quan**; về số học order vẫn `R(o)=0`, không được phân bổ vượt `E(o)`.
3. `review_status` **theo proposal/decision**: `NOT_REQUIRED | OPEN | APPROVED | REJECTED | NEEDS_MORE_INFO | UNDONE`.
4. `exception_reason_codes`: một bản ghi/group được phép có **nhiều** reason codes, ví dụ `CONFIRMED_LINK`, `PARTIAL_PAYMENT`, `LATE_SETTLEMENT`.
5. `ui_bucket` là **projection của các trường trên**, không được viết trực tiếp bởi engine matching. Phải có một hàm xác định duy nhất trong backend/core và test snapshot.

**Màu sắc:**
- Xanh khi **khoản phải thu đã đầy đủ** và không còn cờ review bắt buộc ở mối quan hệ liên quan. Một order đã full nhưng bank còn tiền dư vẫn có cờ ngoại lệ ngân hàng và review, không giấu dư trong trạng thái xanh.
- Vàng khi có **proposal chưa duyệt**, liên kết đã xác nhận nhưng **thiếu tiền**, **dư tiền chưa phân bổ**, phí chưa có đủ bằng chứng, hoặc exception đòi analyst quyết định.
- Đỏ khi **không có bằng chứng đối ứng đã xác nhận** hoặc nguồn **bị loại/block** (gắn nguyên nhân chi tiết, không hàm ý có gian lận).

## A.2. Tính toán theo một snapshot

- Kết quả engine thuần tính toán từ `(canonical inputs, mapping, policy, rule_version)` phải **deterministic**, không phụ thuộc thời gian hệ thống, ID ngẫu nhiên không seed, thứ tự đọc DataFrame hay locale máy.
- `run_id`, `created_at` và `review_action_id` có thể không deterministic; chúng phải **bị loại khỏi** semantic result checksum. `reported_at` trong Excel khác `effective_revision`.
- KPI, edges, proposals, exceptions, export lấy cùng một cặp `(run_id, effective_revision)`; backend không trả lẫn dữ liệu từ hai revisions khác nhau.
- Mọi số tiền cấp API là **integer minor units + currency**. FE không gửi amount float và không tự tính tiền điều chỉnh khi duyệt.
- Một row có `CREDIT` hoặc `DEBIT` rõ ràng; `CREDIT` hợp lệ vào cash pool, `DEBIT` chỉ phân loại ngoài matching MVP. **Không dùng số âm ngầm định nghĩa direction** mà không qua source profile.
- Nghiệp vụ `currency=VND` hoặc `BRL` được chốt cho **mỗi run**; input lẫn tiền tệ bị giữ ở health/block hoặc tạo run khác, không silent FX.

## A.3. Ngày và cửa sổ đối soát

- `ordered_at`: ngày phát sinh order; `txn_date`: ngày giao dịch theo sao kê; `value_date`: ngày hiệu lực nếu có.
- Mỗi `source_profile` nêu **một chính sách date anchor rõ** cho feature `date_gap`: ưu tiên `value_date` nếu chính sách settlement dùng nó; nếu không dùng `txn_date`. Cần giữ cả raw fields để audit.
- `max_days_diff=3` là **tham số mặc định demo**, không suy ra từ luật nghiệp vụ chung. Có thể tạo candidate ngoài cửa sổ với reason `OUT_OF_WINDOW` nếu full ID khớp, không âm thầm bỏ trường hợp rõ ID.
- `timezone=Asia/Ho_Chi_Minh` đối với dữ liệu VN synthetic; Olist dùng convention của profile BRL ghi trong manifest. Các ngày order (date-only) không bị nội suy giờ 00:00 rồi suy ra sai T+N.

## A.4. Phí và gross/net, nguyên tắc cấm tự hạch toán

- Một `PSP_SETTLEMENT` phải có định nghĩa `posted_net_cash`, `gross_order_value`, `fee_evidence` (nếu có), và **settlement policy** rõ trước khi xác nhận fee adjustment.
- `verified_adjustment_minor` chỉ dành cho khoản điều chỉnh nghĩa vụ **hợp lệ theo chính sách/tài liệu đã duyệt**; **không** phải chi phí kế toán tự động hoặc bút toán Nợ/Có. Nếu không có bằng chứng, `fee_hypothesis_minor` chỉ là thông tin của proposal.
- Không tự tạo adjustment vì `net = gross × (1 - 0.02)`; phần chênh ngân hàng chuyển khoản thông thường là thiếu tiền/chưa rõ nguyên nhân.
- Nếu nguồn PSP gộp nhiều đơn nhưng không có breakdown phí theo từng đơn, chỉ được review phân bổ adjustment với tổng phí nguồn và basis hợp lệ; nếu không đủ, route `INSUFFICIENT_FEE_EVIDENCE`.

## A.5. Khóa phạm vi thực sự của MVP

- Hỗ trợ **2 logical feeds**, dù chúng nằm trong 2 CSV, 2 XLSX hoặc 1 XLSX/2 sheets.
- **N:1** và **1:N** cần support cash edges và partial residual ngay từ đầu. **M:N** tổng quát **không auto**.
- React là **FE cần nghiệm thu**. Streamlit không phải deliverable bắt buộc. Lõi đối soát chạy độc lập và chỉ có một implementation.
- `DuckDB` xử lý analytics và joins; `SQLite` chỉ là app persistence cho single-instance local. Trong production nhiều nhân sự cần xem lại RBAC/PostgreSQL/queue.
- Không đề nghị đổi sang framework/DB thứ ba khi chưa có benchmark hoặc nhu cầu mới được xác minh.

---

# 30. PHỤ LỤC B — GOLDEN FIXTURES, ORACLE VÀ CONSERVATION

Đây là **ca kiểm thử định nghĩa trước**, không phải dữ liệu đã chạy. Mỗi fixture có feed đầu vào, oracle edges/trạng thái, dự kiến proposal/exception và bất biến tiền. Dùng integer VND cho ví dụ; kiểm tra BRL làm tròn riêng.

| Case | Orders (minor) | Bank (minor) | Kết quả oracle chính | Điều cấm |
|---|---|---|---|---|
| F01 EXACT | O01=300000 | B01=300000, memo `O01` | CONFIRMED 1:1, A=300000, R=U=0 | No phantom fee |
| F02 T+2 | O02=200000 | B02=200000, `O02`, +2 ngày | CONFIRMED theo strict ref policy, warning lag | Không suy T+N là lỗi tiền |
| F03 NORMALIZED | O03=100000 | B03=100000, ref có biến thể spacing | CONFIRMED nếu grammar được cấu hình và ref unique | Không cắt token thành ID khác |
| F04 FUZZY | O04=100000 | B04=100000, `0O4` | PROPOSED/REVIEW | Không auto chỉ vì điểm fuzzy |
| F05 AMBIGUOUS | O05=100000, O06=100000 | B05=100000, memo trống | Các proposal cạnh tranh; không edge confirmed | Không match amount-only |
| F06 N:1 STRONG | O07=300000, O08=200000 | B06=500000, memo `O07 O08` | 2 edges cùng B06; A=(300000,200000), U=0 | Không cộng B06 hai lần |
| F07 N:1 WEAK | O09=300000, O10=200000 | B07=500000, memo trống | PROPOSED group; approval mới tạo edges | Không auto từ sum exact |
| F08 1:N STRONG | O11=600000 | B08=200000, B09=400000, cùng full ref O11 | 2 edges, R=0 | Không ép bank thành một dòng |
| F09 PARTIAL | O12=500000 | B10=490000, full ref | CONFIRMED link, A=490000, R=10000, UI review | Không gọi FULL, không tự fee |
| F10 OVERPAY | O13=500000 | B11=520000, full ref | A=500000, U=20000, review bank residual | Không giấu 20000 dư |
| F11 MISSING | O14=150000 | Không có bank | Chưa có confirmed receipt, R=150000 | Không khẳng định chắc người mua chưa chuyển |
| F12 ORPHAN BANK | Không có order | B12=85000 | U=85000; orphan review | Không hạch toán vào order khác |
| F13 DUPLICATE IMPORT | O15=120000 | B13 ghi nhập hai lần cùng stable bank ID | Chặn/route review bản nhập trùng; đúng cash count | Không nhân đôi dòng tiền |
| F14 REAL SAME AMOUNT | O16=120000, O17=120000 | B14=120000, B15=120000, IDs khác | Chỉ confirm theo full unique refs | Không gộp nhầm do amount/date |
| F15 VERIFIED PSP | O18=100000 | B16=98000, fee chứng minh 2000 | A=98000, F=2000, R=0 theo settlement policy | Cash A không thành 100000 |
| F16 UNVERIFIED FEE | O19=100000 | B17=98000, `BANK_TRANSFER` | A<=98000 nếu full ref; R>=2000 | Không tạo F=2000 |
| F17 DEBIT | O20=90000 | Bank debit 90000 | Không đưa debit vào credit pool | Không auto thu tiền |
| F18 REF BOUNDARY | O21=90000 `DH01`, O22=80000 `DH010` | B18=90000 `DH01` | Chỉ xét đúng full ref `DH01` | Không substring `DH010` |
| F19 APPROVE CONFLICT | O23=300000, O24=300000 | B19=300000 | Hai proposal dùng B19; chỉ một có thể được approve | Transaction thứ hai phải 409 |
| F20 UNDO DEPENDENCY | O25=300000 | B20=300000 | Undo phải tạo revision, bảo vệ xung đột downstream | Không xóa audit history |
| F21 WRONG CURRENCY | O26=10000 BRL | B21=10000 VND | BLOCKED/UNRESOLVED theo policy | Không so tiền trực tiếp |
| F22 EXCEL ID | O27=`00017` | B22 có `00017` | Preserve string và parse đúng nếu nguồn hợp lệ | Không chuyển ID thành 17/1.7E1 |
| F23 CSV INJECTION | O28 có description bắt đầu `=HYPERLINK(...)` | B23 tùy case | Export thành text an toàn | Không tạo công thức thực thi |
| F24 MANY-TO-MANY | O29,O30 | B24,B25 có multi-ref chồng nhau | `COMPLEX_MANY_TO_MANY_REVIEW` | Không auto trong MVP |

**Quy tắc oracle:**

1. `truth_edges.csv` chỉ chứa các cạnh **có thật theo generator**, không chứa proposed edges; null order/bank có trong `truth_cases.csv`.
2. Riêng cases dữ liệu ambiguous có khả năng tồn tại truth nhưng thiếu chứng cứ: oracle matching **cấm auto-confirm** dù evaluator biết truth.
3. `F15` chỉ được dùng làm `FULL` theo chính sách settlement cụ thể trong fixture, không mặc định cho mọi PSP.
4. Với mỗi fixture, tạo tests ở 3 cấp: core semantic results; public API mapping/review; notebook evaluation (nếu có truth).
5. Ví dụ `F19` cần **hai request duyệt khác revision** và xác minh HTTP 409/snapshot không bị ghi đè. `F20` cần test undo/revision khi có review tiếp theo.

## B.1. Các bất biến kiểm thử tự động

Đối với mỗi run và mỗi revision hiệu lực:

```text
0 <= allocated_cash_by_bank(b) <= posted_eligible_cash(b)
unapplied_bank_cash(b) = posted_eligible_cash(b) - allocated_cash_by_bank(b)

0 <= allocated_cash_by_order(o) + verified_adjustment(o) <= expected_receivable(o)
outstanding_receivable(o) = expected_receivable(o) - allocated_cash_by_order(o) - verified_adjustment(o)

SUM(bank_cash_eligible) = SUM(cash_allocated_effective) + SUM(bank_unapplied)
SUM(order_receivable_eligible) = SUM(cash_allocated_effective) + SUM(verified_adjustments) + SUM(outstanding_receivable)
```

Không được kiểm các identity này **bằng cách lặp lại chính công thức business trong cùng một helper rồi coi như test độc lập**. Tạo oracle hand-calculated cho fixtures, randomized/property-based tests (Hypothesis tùy chọn) và SQL cross-check để phát hiện logic bug.

## B.2. Định dạng canonical/research files tối thiểu

```text
required input A fields (logical): order_id, ordered_at, expected_amount, currency
required input B fields (logical): bank_txn_id_or_surrogate, txn_date,
                                    posted_amount, direction, currency, amount_basis
optional both: description, external_ref, sender/customer, payment_channel,
               value_date, batch_ref, source-profile-dependent fee fields
research only: truth_edges.csv, truth_cases.csv, manifest.json
```

Một workbook 2 sheets là **hai nguồn logic**, không phải hai loại hình kết quả. Những field raw như `amount`, `net_amount`, `tx_date` được mapping explicit sang schema này; không đổi tên file gốc rồi gọi là canonical.

---

# 31. PHỤ LỤC C — MA TRẬN YÊU CẦU → TRIỂN KHAI → KIỂM THỬ

| Yêu cầu được chốt | Milestone | Chứng cứ nghiệm thu tối thiểu |
|---|---|---|
| Dự án mới, không kế thừa ReconEngine | M0 | Repo riêng, dependency/import grep, license/docs |
| 2 file CSV/XLSX hoặc workbook 2 sheets | M1–M2, M6–M7 | Upload API + React E2E |
| Dữ liệu Olist nhưng bank là synthetic | M1 | Provenance manifest + attribution + semantic source QA |
| 1.000 anchor orders, số bank rows biến động | M1 | Seed/manifest/quota count reproducible |
| Truth không lọt vào engine | M1, M5 | Denylist tests; monkeypatch evaluator not importable from matching |
| IDs/dates/money đúng cả VND/BRL | M2 | Parsing fixture, string ID + Decimal/integer tests |
| Quality Gate lỗi chặn/warning | M2, M6–M7 | Duplicate/missing/currency health fixtures |
| Exact 1:1 + T+N | M3 | F01–F03 + time-window policy cases |
| N:1 và 1:N phân bổ bảo toàn | M4 | F06–F08, edge tests + invariants |
| Fuzzy/top-K/guardrails | M4 | F04/F05/F18, zero unsafe auto |
| Thiếu, thừa, phí hợp lệ/chưa hợp lệ | M3–M4 | F09/F10/F15/F16, residual test |
| Orphans, duplicate, debit direction | M2–M4 | F11–F14/F17, exception tests |
| M:N ngoài MVP và review an toàn | M4 | F24 + bounded-combination budget tests |
| Đánh giá precision/recall/F1 đúng link | M5 | Eval fixtures known TP/FP/FN, compare baseline/ablation |
| API cho upload/run/status/group/review/export | M6 | OpenAPI DTO snapshot, pytest API integration |
| Duyệt có undo, audit và tránh race | M6–M7 | F19/F20, two-client stale-revision 409 |
| Dashboard đúng mẫu số | M6–M7 | Edge-sum cross-check, Chart DTO vs backend KPI |
| Export Excel/CSV có traceability | M6–M7 | Đọc lại workbook/ZIP, compare revision and money sums |
| Xử lý Excel/CSV upload an toàn | M2, M6 | F22/F23 + size/sheet/type limits |
| Notebook dùng chung engine | M5–M8 | Notebook restart/run-all + result semantic checksum |
| Windows setup chạy lại được | M8 | Clean-clone smoke test PowerShell |

**Cần lưu evidence thực tế** (`pytest` logs, coverage/runs, screenshots, exports, seed/commit/config) trong CI artifacts hoặc thư mục `reports/`. Không thay thế bằng khẳng định của coding agent.

---

# 32. PHỤ LỤC D — QUY TRÌNH GIAO VIỆC CODING AGENT

## D.1. Cách giao việc an toàn

Giả định agent được cấp quyền làm việc trên repo mới của bạn. **Không gửi toàn bộ tài liệu rồi yêu cầu hoàn thành mọi thứ trong một lần**. Chia theo M0→M8, mỗi lần chỉ một hoặc vài issue có test oracle.

**Prompt khởi động M0 (có thể copy vào Codex):**

```text
Bạn là kỹ sư phần mềm phụ trách khởi tạo dự án độc lập Smart Financial
Reconciliation & Analytics. Đọc toàn bộ file SMART_RECON_MASTER_PLAN_V3_FINAL.md.
Không clone/fork/copy code từ dpduc/ReconEngine: chỉ tham khảo domain/dataset
nếu được phép và có attribution.

CHỈ THỰC HIỆN M0:
1. Khảo sát thư mục làm việc, xác nhận đây là repo mới; không xoá file hiện có.
2. Tạo Python package smartrecon, pyproject.toml/uv.lock và pytest/Ruff.
3. Tạo docs cho scope, data contract, money invariants, ADRs/decision log.
4. Tạo domain models/type enums, fixture mẫu F01/F06/F08/F09/F10 với oracle,
   chưa implement business matching giả và không hardcode kết quả để qua test.
5. Tạo cấu trúc FastAPI/React tối thiểu chỉ khi phục vụ scaffold; chưa viết
   giao diện kinh doanh và không mở rộng scope.
6. Chạy test/lint thực tế, ghi command, exit codes và các hạn chế.
7. Nếu repo có remote GitHub phù hợp và bạn có quyền: branch + commit + push
   theo workflow, không force-push, không push dữ liệu thật/.env.

Tiêu chí xong: có codebase sạch, domain hợp đồng ổn định, bất biến bằng test,
không sao chép code tham khảo, tài liệu đủ để M1 triển khai.
Trả lại changed files, test results, commit SHA/PR (nếu được), những việc chưa làm.
```

**Prompt M1 sau khi M0 nghiệm thu:**

```text
Đọc SMART_RECON_MASTER_PLAN_V3_FINAL.md, nhất là chương 5–8, 20, phụ lục B/C.
CHỈ THỰC HIỆN M1. Viết data adapters và synthetic generator có seed,
2 input feeds + truth_edges/truth_cases/manifest tách biệt, profile VN synthetic
và Olist-derived theo quyền dữ liệu. Không dùng truth cho matching. Đảm bảo
seed same => semantic hashes stable, case quotas được ghi rõ mẫu số và actual.
Triển khai F01–F24 như golden fixture tests; không phải mọi case đều xuất hiện
trong bộ demo ngẫu nhiên, tạo case manifest đảm bảo coverage khi demo.
Chạy pytest/data validation, báo kết quả thật; không tiến sang M2 nếu data
contract/ground truth chưa pass hoặc có leakage.
```

## D.2. Quy ước giao tiếp kết quả của agent

Mỗi PR/milestone bắt buộc mô tả:

```text
A. Scope và files thay đổi
B. Behavior hoàn thành và danh sách còn thiếu
C. API/schema migrations hoặc ADR mới
D. Commands đã chạy, test passed/failed, logs/commit
E. Deterministic seed + input/output examples (nếu là data/core)
F. Invariants, false auto-match và threat checks đã kiểm
G. Rủi ro còn lại; acceptance items chưa hoàn tất
```

Mọi kết quả **đã chạy** phải có evidence. Không tự viết trong báo cáo rằng "benchmark đạt 100%" khi không có đầu ra thật. Nếu agent đề nghị thay toàn bộ stack hoặc giản lược group/edge để demo nhanh, từ chối trừ khi có ADR nêu rõ trade-off và test giữ correctness.

---

# 33. PHỤ LỤC E — CHECKLIST BÀN GIAO & THỨ TỰ THỰC HIỆN

## E.1. Hành động đầu tiên (trước khi viết core)

- [ ] Lưu chính file này tại `docs/MASTER_PLAN.md` (hoặc root với đường dẫn đã chốt).
- [ ] Tạo repo GitHub **mới** và chọn license **cho code** độc lập với license dữ liệu Olist.
- [ ] Dùng duy nhất tên module/package/domain từ chương 21; tránh tách `recon` và `reconcile_engine` song song.
- [ ] Khóa source profile `BANK_CREDIT` và `PSP_NET_SETTLEMENT`; ghi nghĩa amount/date cho từng loại.
- [ ] Khóa enums/trạng thái, money invariants và deterministic semantic checksum.
- [ ] Chốt 24 golden fixtures trong phụ lục B; test oracle dùng manual expected numbers.
- [ ] Quyết định dataset demo: `vn_synthetic_demo` (không ràng buộc Olist) và `olist_derived_demo` (tuân giấy phép).
- [ ] Chốt dự án chạy single-instance local trong MVP; không công khai endpoint review khi chưa có auth.
- [ ] Thiết kế OpenAPI JSON DTO trước khi FE kết nối; UI không tự suy luận trạng thái.

## E.2. Điều kiện kết luận bản kế hoạch đã sẵn sàng triển khai

- **Đã chốt:** scope, source semantics, tech stack, data/ground truth, canonical contracts, waterfall, N:1/1:N, conservation, review, KPI, storage, API, frontend, notebook, test cases, milestones và phân chia công việc.
- **Cần kiểm tra trong quá trình code:** phiên bản package có tương thích môi trường Windows không; DuckDB/SQLite chạy nhanh tới đâu; chính sách auto-confirm đạt precision/coverage gì trên holdout; tải Excel lớn có đáp ứng giới hạn máy không.
- **Cần quyết định nếu sản phẩm chuyển khỏi demo local:** giấy phép/phân phối dữ liệu Olist, xác thực và phân quyền, lưu giữ/xóa dữ liệu tài chính, backend concurrency nhiều người và migration sang PostgreSQL/queue nếu cần.

## E.3. Bàn giao chính thức theo thứ tự

1. **M0:** foundation + ADR/domain + test oracle.
2. **M1:** reproducible data + truth + manifest + fixtures.
3. **M2:** ingestion/mapping/health.
4. **M3:** core 1:1 + cash conservation.
5. **M4:** N:1, 1:N, fuzzy proposals, conflicts, exceptions.
6. **M5:** notebook/evaluation/holdout.
7. **M6:** FastAPI/persistence/review/export.
8. **M7:** React/dashboard/review UI/E2E.
9. **M8:** clean install, regression, performance/security baseline, demo + docs.

**Đây là văn bản kế hoạch hoàn chỉnh, không phải sản phẩm phần mềm.** Tên file, API và các đoạn command thể hiện **đặc tả mục tiêu**; chưa có cam kết tính năng nào đã được implement hoặc test trên repo mới. Chỉ đánh dấu v1.0-demo đạt nghiệm thu khi các bài test/dữ liệu/báo cáo quy định ở trên có kết quả thực tế.
