# SMARTRECON — KẾ HOẠCH CHỐT V5.0: 2 GIAI ĐOẠN, DOCKER-FIRST, DEPLOY-READY

**Ngày:** 14/10/2026  
**Trạng thái:** Đặc tả đề xuất trước triển khai; chưa có code, benchmark hay deployment nào được xác nhận.  
**Tham chiếu:** `SMART_RECON_MASTER_PLAN_V3_FINAL.md` (nghiệp vụ, invariants, 24 fixtures) và `SMART_RECON_KE_HOACH_TRIEN_KHAI_2_GIAI_DOAN.md` (mục tiêu hai giai đoạn).  
**Điều chỉnh kiến trúc có chủ đích so với V4:** Docker Compose từ giai đoạn 1; PostgreSQL thay SQLite để khỏi phải chuyển transaction store lúc triển khai nhiều người. Các phần còn lại, đặc biệt bảo toàn tiền, không thay đổi.

## 1. Một câu mô tả đúng sản phẩm

Website upload **2 nguồn**: dữ liệu đơn hàng/khoản phải thu và dữ liệu giao dịch ngân hàng/PSP; cho xem dữ liệu thô và chất lượng dữ liệu; mapping và chuẩn hóa; Health Gate; 4 lớp tìm liên kết; kết luận số tiền và ngoại lệ; người dùng duyệt trường hợp thiếu chứng cứ; xem dashboard; tải Excel; notebook đánh giá thuật toán trên dữ liệu có ground truth riêng. **Đây là payment reconciliation, không phải một hệ sổ cái kế toán hoàn chỉnh hoặc đối chiếu số dư ngân hàng.**

Dự án **viết mới độc lập 100%**. Repo `dpduc/ReconEngine` chỉ tham khảo ý tưởng và sử dụng dữ liệu trong phạm vi giấy phép cho phép; không sao chép engine/codebase.

## 2. Quyết định nền tảng (chốt làm baseline)

| Thành phần | Chọn | Vai trò và điều cần tránh |
|---|---|---|
| Container runtime | Docker Desktop/Engine + Docker Compose | Đồng bộ môi trường; không phải database |
| Frontend | React, TypeScript, Vite, Plotly | Không xử lý logic tiền/matching trong FE |
| Backend | FastAPI, Pydantic, SQLAlchemy, Alembic | API, orchestration, validation; xử lý tiền qua cùng một core |
| Python core | Python 3.12, Pandas, regex, RapidFuzz | Logic đối soát thuần, import được từ API/Notebook |
| Analytical SQL | DuckDB nhúng trong Python backend/core | Profiling, join, blocking, analytics; **không** dùng để lưu hành động review đa tiến trình |
| Transactional DB | PostgreSQL (container riêng) | Runs, review, effective allocations/revisions, audit, metadata |
| File/artifact | Docker volume hoặc host mount | Original uploads bất biến, normalized Parquet, reports, manifest; sau này thay bằng object storage dễ dàng |
| Research | Jupyter Notebook (local/container tùy chọn) | Gọi chính engine, ground truth chỉ trong evaluation |
| QA | pytest, Ruff, frontend build, Playwright, migrations/integration | Không gọi thành công nếu chưa chạy thực tế |

**Không cần:** Redis, Celery, Kubernetes, microservices, ML/LLM, FX, 3PL, OCR/PDF, login enterprise, external bank API hoặc object storage service riêng ở bản demo local.

**Chỉ một đơn vị tiền cho mỗi run:** VND hoặc BRL; chuẩn hóa qua `Decimal` rồi chuyển integer minor units; không cộng tiền khác currency.

## 3. Docker quản lý cái gì?

- `frontend` container: phát triển chạy Vite; khi deploy build static bundle được Nginx hoặc reverse proxy phục vụ.
- `backend` container: FastAPI + module engine + DuckDB nhúng; 1 worker ở local demo để đơn giản concurrency.
- `db` container: PostgreSQL; dùng `pg_data` named volume. Không mở cổng DB ra Internet.
- `artifacts` volume: raw uploads (nếu chính sách retention cho phép), normalized snapshots, Parquet, generated Excel, manifests; không lưu vào layer tạm của container.
- Compose network: giao tiếp nội bộ bằng hostname `db`, `backend`; host/browser qua HTTP public endpoint, không dùng `db` hostname từ browser.

**Tại sao PostgreSQL thay SQLite:** chi phí thêm 1 container nhỏ nhưng giữ một cơ chế transaction, audit, khóa review xung đột, migrate schema và deployment multi-user nhất quán. Đây là lựa chọn cho mục tiêu deploy của dự án, **không phải vì SQLite sai hoặc Docker bắt buộc cần PostgreSQL**.

**Vì sao không Docker hóa DuckDB thành server:** DuckDB là thư viện phân tích nhúng; giữ truy vấn trong một tiến trình/job, có thể dùng dữ liệu Parquet như input. Tránh nhiều tiến trình ghi cùng một file DuckDB khi chưa có thiết kế cụ thể.

## 4. Workflow người dùng và dữ liệu

```text
[CSV/XLSX Orders]    [CSV/XLSX Bank/PSP]
       \                    /
      Upload + file-size/extension/content validation
                         |
            Raw preview + preliminary EDA
                         |
      Mapping (user confirmation) + Normalization
                         |
             Standardized EDA + Health Gate
                     |           \
                     |            +--> Blocking: fix/re-upload
                     v
          4-layer matching waterfall
    L1 reference  -> L2 constraints -> L3 fuzzy proposals
                        -> L4 bounded group/split candidates
                         |
             Conflict / allocation resolver
                         |
        Invariants + payment status + exceptions
                         |
           Dashboard (run snapshot/revision)
                         |
             Review / Reject / Undo
                  (Phase 2; atomic)
                         |
         Metrics update + Excel/CSV Export
```

**Raw EDA** chỉ mô tả và phát hiện lỗi thô; **standardized EDA** mới tính các thống kê tiền/ngày sau mapping. Không ghi đè file gốc; lưu hashes, rule version, policy snapshot và lineage. Mỗi bảng export/chart đọc cùng `run_id` + effective `revision`.

## 5. Mô hình nghiệp vụ chuẩn

- `Order` / `Receivable`: số phải thu, currency, ngày, external refs, source row lineage.
- `BankTransaction`: số tiền ghi sổ, direction, amount basis (bank credit/gross vs PSP settlement net), refs, description, source lineage.
- `MatchGroup`: một nhóm liên kết 1:1, N:1, 1:N; có `evidence`, `link_status`.
- `AllocationEdge`: `(order_id, bank_txn_id, allocated_cash_minor)`, bằng chứng và trạng thái.
- `Adjustment`: khoản fee/write-off **chỉ khi có bằng chứng/chính sách đã xác minh**; không tự coi chênh lệch là phí.
- `Candidate`, `Exception`, `ReviewAction`, `RunRevision`, `RunManifest`.
- Ba trục trạng thái: `link_status` độc lập `payment_status` độc lập `review_status`; nhãn xanh/vàng/đỏ là UI, không phải business schema.

### Bất biến tiền P0

```text
0 <= allocated_bank(b) <= eligible_credit(b)
unapplied_bank(b) = eligible_credit(b) - allocated_bank(b)
0 <= cash_to_order(o) + verified_adjustments(o) <= expected(o)
outstanding(o) = expected(o) - cash_to_order(o) - verified_adjustments(o)
SUM(bank_eligible) = SUM(confirmed_allocations) + SUM(bank_unapplied)
SUM(order_eligible) = SUM(confirmed_allocations) + SUM(verified_adjustments) + SUM(order_outstanding)
```

Proposals không tham gia KPI confirmed; bank N:1 được phân bổ thành nhiều edges nhưng số tiền bank chỉ tính **một lần**. Review cạnh tranh phải kiểm tra lại trong **một PostgreSQL transaction** (lock các record liên quan hoặc cơ chế tương đương, kiểm tra `expected_revision`), stale update trả `409 Conflict`.

## 6. Hai giai đoạn — không chia lại thành 9 milestone

### GIAI ĐOẠN 1 — DỰNG NỀN DOCKER + ENGINE ĐÚNG + WEB CHẠY ĐƯỢC

**Đầu ra nhìn thấy:** `docker compose up --build -d`, mở trang web, chọn demo data/CSV/XLSX, preview dữ liệu thô, mapping, standardized EDA, Health, bấm Reconcile, có dashboard/bảng groups/exceptions và tải Excel thật.

**Checklist công việc, theo thứ tự:**

1. Khởi tạo repo độc lập: `pyproject.toml` + `uv.lock`, frontend React TS, `.env.example`, `.dockerignore`, `docs/`, lint/test/CI. Docker Desktop + WSL2 trên Windows; Compose, 2 Dockerfiles, healthchecks, named volumes, network và một hướng dẫn khởi động rõ ràng.
2. Thêm PostgreSQL + SQLAlchemy + Alembic **ngay từ đầu**; các bảng `runs`, `run_revisions`, `review_actions` (chưa cần UI review), `match_groups`, `allocation_edges` hoặc effective state tương đương, `artifact_manifest`, upload sessions; DB cấu hình qua env, không hardcode secrets.
3. Thiết kế data contract/currency semantics và sinh `vn_synthetic_demo` 80–120 đơn cùng Olist-derived sample BRL (được phép tái sử dụng); chỉ 2 input feeds, truth riêng; seed, provenance, SHA256 và các case exact, T+N, N:1, 1:N, under/over, ambiguous, orphan, duplicate, fees.
4. Ingest CSV/XLSX; preview/raw EDA; mapping; tiền `Decimal→minor units`; normalize refs/ngày; standardized EDA; Health Gate blocking/warning/info; limits/safe Excel handling.
5. Core 4 lớp: (L1) strong ref 1:1/N:1/1:N; (L2) policy constrained; (L3) RapidFuzz **PROPOSED**; (L4) bounded N:1/1:N candidates; conflict resolver, allocations, exceptions, metrics. Không auto accept chỉ do amount/date/text score; hạn chế combinatorial search, tính chưa rõ → review.
6. FastAPI (health, demo-dataset dev-only, upload-inspect, mapping, runs, dashboard, groups, exceptions, xlsx export). React 4 luồng: Upload/EDA; Mapping/Health; Run; Dashboard/Explorer/Export.
7. Tests: 22 golden fixtures theo V3 (không gồm 2 case undo/concurrency), invariants, no-double-count, no-truth-leakage, CSV/XLSX equivalent, API smoke, frontend build + browser smoke. **Thêm Docker-specific tests**: clean build, Postgres health/migrations, persistence sau `compose down/up` (không `-v`), volume artifacts và export, logs/health endpoint.

**Gate Phase 1:** một người mới chỉ cần Docker + Git để theo README và chạy demo từ trình duyệt; cùng input/config cho cùng semantic output; bắt buộc 0 violation bất biến tiền; không falsely auto-match cases mơ hồ; không mất dữ liệu qua stop/start; tests có log thật. Nếu gate fail không bắt đầu Phase 2.

### GIAI ĐOẠN 2 — REVIEW + ANALYTICS + NOTEBOOK + DEPLOY-READY RELEASE

1. Review Queue: APPROVE/REJECT/UNDO, transactional validations, optimistic revision, audit, idempotency, conflict handling 409. Một bank không thể cấp vượt số tiền hợp lệ qua hai approvals.
2. Dashboard hoàn chỉnh: order KPIs, bank KPIs, allocated/unapplied/outstanding, waterfall by layer, lag, exception causes, grouped/split, review changes. Snapshot consistency.
3. Export workbook 9 sheet của V3, CSV tùy chọn; filter và lineage; formula-injection protection; time/currency display rõ ràng.
4. Research notebook: cùng `smartrecon.engine`, EDA, normalization, four layers, ablation, feature analysis, Precision/Recall/F1 edge-level, group exact match, allocation error, holdout và benchmark; không leakage; notebook Restart & Run All.
5. QA: đủ 24 golden fixtures bao gồm concurrent/review undo, property/integration/E2E; review collision 409; security upload limits; restart/resume; benchmark có logs, không tuyên bố precision = 100% chưa đo.
6. Docker release: multi-stage frontend production image, backend non-root/minimal image, lock versions, health checks, reverse proxy/HTTPS trên môi trường triển khai, `compose.production.yaml` override; CI build/lint/test/images; DB migrations chạy **một lần**; backup/restore được thử thật cả PostgreSQL lẫn artifacts; README Windows và VPS Linux.
7. Chốt release `v1.0.0-demo` chỉ khi all gates pass; known limitations. **Chưa triển khai Internet công khai có dữ liệu thật** nếu không có auth, authorization theo run, HTTPS, rate limiting, và chính sách bảo vệ dữ liệu.

**Gate Phase 2:** 24 fixtures pass; upload→health→run→review→undo→dashboard→export→reopen được test trên browser; Docker image chạy trên máy/server khác; backup + restore phục hồi cả DB lẫn artifacts; Notebook/API cùng core; không có P0.

## 7. Cấu trúc repository đề xuất

```text
smartrecon/
├── compose.yaml                    # dev/minimal, 3 services
├── compose.production.yaml         # production override, không dùng dev source mounts
├── .env.example  .gitignore  .dockerignore  README.md
├── pyproject.toml  uv.lock
├── backend/
│   ├── Dockerfile
│   └── smartrecon_api/{main.py,routers/,schemas/,services/,db/}
├── src/smartrecon/
│   ├── domain/{models.py,allocations.py,invariants.py}
│   ├── ingest/{readers.py,mapping.py,normalization.py,health.py}
│   ├── matching/{reference.py,constrained.py,fuzzy.py,grouping.py,resolver.py}
│   ├── analytics/{duckdb_queries.py,metrics.py}
│   ├── evaluation/{metrics.py,ground_truth.py}
│   └── engine.py                    # API công khai cho backend & notebook
├── frontend/
│   ├── Dockerfile
│   └── src/{pages/,components/,api/,types/}
├── migrations/                      # Alembic PostgreSQL migrations
├── data_generators/                 # deterministic datasets, truth riêng
├── notebooks/reconciliation_research.ipynb
├── tests/{unit/,integration/,api/,golden/,e2e/}
├── docs/{SCOPE,ARCHITECTURE,DATA_CONTRACT,MONEY_INVARIANTS,API_CONTRACT,EVALUATION,DEPLOYMENT}.md
└── storage/                         # .gitignore; mount vào container nếu dùng bind dev
```

**Các thư mục chính là định hướng, không bắt buộc tạo file rỗng hay mô phỏng tính năng chưa triển khai.** Migrations có thể nằm trong backend tùy layout SQLAlchemy, nhưng phải được version control.

## 8. Quy tắc về lưu trữ, bảo mật và khôi phục

| Dữ liệu | Nơi lưu | Lưu ý |
|---|---|---|
| Orders / Bank input gốc | Artifacts volume (hoặc xóa sau TTL) | Bất biến; file hashes; không commit Git; chính sách xóa |
| Normalized snapshot / Parquet | Artifacts volume | Lưu config + mapping + engine version để reproduce |
| Run config, status, decisions, revisions, audit | PostgreSQL named volume | DB transaction, migrations, checksums/revision |
| MatchGroup/edges effective | PostgreSQL và/hoặc immutable snapshot | Source of truth thống nhất, không tạo hai trạng thái trái nhau |
| DuckDB temporary tables | Python job / temp ephemeral | Có thể tái tạo từ normalized snapshot |
| Truth labels | `data/evaluation/` tách riêng | Không đi qua production engine hay normal upload API |
| Secrets | `.env` local không commit; production secret management | Không hardcode trong image/Git; khóa port DB |

**Backup cần cả database và artifacts.** Named volumes sống qua `docker compose down`, nhưng `docker compose down -v` xóa chúng: không chạy lệnh này khi có dữ liệu cần giữ. Chỉ dùng volume không có nghĩa là đã có backup. Dùng `pg_dump/pg_restore` hoặc giải pháp PostgreSQL backup phù hợp, cộng với backup artifacts tương ứng cùng một snapshot logic; cần thử restore.

## 9. Docker Compose — hợp đồng vận hành, không phải code đã triển khai

`compose.yaml` cần mô tả ba service `frontend`, `backend`, `db` và hai volumes `pg_data`, `artifacts_data`; backend có `DATABASE_URL` hướng tới hostname `db`; backend chờ DB healthy; frontend gọi API qua service/proxy phù hợp browser; Dockerfiles phải tương thích cả Windows WSL2 và Linux. Không publish cổng PostgreSQL ra bên ngoài, kể cả staging. Local development có thể dùng Vite hot reload và bind code trong `compose.override.yaml`; production dùng static build/reverse proxy không mount source code.

Lệnh dự kiến sau khi Codex đã tạo Dockerfiles và Compose hợp lệ:

```powershell
docker compose config                  # kiểm tra cấu hình
docker compose up --build -d          # build + chạy ứng dụng
docker compose ps                     # tình trạng service
docker compose logs -f backend        # xem backend logs
docker compose exec backend alembic upgrade head  # chỉ khi migration setup chính xác
docker compose down                   # dừng, giữ named volumes
```

**Tránh:** `docker compose down -v` khi muốn giữ database/outputs, commit `.env`/raw finance files, mở 5432 public, dùng DuckDB file làm shared writable transaction store của nhiều worker.

## 10. Đường phát triển sau demo

- **V1 — local demo (Giai đoạn 1):** 3 Compose services, PostgreSQL+volumes, engine trong backend, single worker, đủ để học và kiểm chứng.
- **V1-demo hoàn chỉnh (Giai đoạn 2):** review, benchmark, E2E, backup/restore, release images, production override.
- **V1 hosted demo (sau khi qua QA và bổ sung bảo vệ truy cập):** 1 VPS Linux, Docker Compose, reverse proxy HTTPS, secrets, scheduled backup/monitoring; dùng synthetic data nếu public chưa có auth.
- **Nhiều người và dữ liệu lớn (chỉ khi tải đo thực tế đòi hỏi):** auth/RBAC/multi-tenancy, managed PostgreSQL, S3-compatible object storage, queue+worker (Redis/RQ/Celery hoặc giải pháp phù hợp), tách CPU reconciliation job khỏi API, pooling, monitoring. Kubernetes chỉ khi vận hành thật sự cần orchestration đa node; không phải mặc định để trở thành 'scalable'.

**Giữ hợp đồng mở rộng:** `StorageRepository`/`ArtifactStore` abstraction, SQLAlchemy/Alembic, stateless backend HTTP, run_id/idempotency, immutable dataset & result snapshots, API versioning. Không cần xây plugin/microservice sớm.

## 11. Nghiệm thu thao tác end-to-end

1. Clone repo lên máy sạch có Docker Engine/Compose; tạo `.env` từ `.env.example` không lộ secrets.
2. Một lệnh `docker compose up --build -d` tạo Frontend + Backend + PostgreSQL healthy, schema migrated.
3. Vào website, dùng 2 feed CSV/XLSX hoặc dataset demo; thấy raw preview, EDA; mapping và normalized EDA; blocking gate.
4. Chạy waterfall; xem đủ 1:1, N:1, 1:N, partial, ambiguous, orphan; 0 double count; xuất Excel cùng run/revision.
5. `docker compose down` rồi `up -d` lại: run đã hoàn thành vẫn còn, charts và export nhất quán.
6. Sau Phase 2: approve/reject/undo; two-review collision trả 409; KPIs thay đổi chính xác; Playwright E2E và Notebook Run All pass.
7. DB + artifacts backup và phục hồi sang stack khác, truy cập lại run và export; lập report logs, known limitations.

**Không được gọi hệ thống 'production ready' chỉ vì đã containerize.** Khi mở Internet thật còn cần quyền truy cập, HTTPS, audit, retention, backups, security hardening, monitoring và load tests.

## 12. Tham khảo kỹ thuật chính thức

- Docker Compose: https://docs.docker.com/compose/
- Docker Volumes: https://docs.docker.com/reference/compose-file/volumes/
- Docker Compose production: https://docs.docker.com/compose/how-tos/production/
- Docker WSL2 best practices: https://docs.docker.com/desktop/features/wsl/best-practices/
- PostgreSQL backup: https://www.postgresql.org/docs/17/app-pgdump.html
- DuckDB concurrency: https://duckdb.org/docs/current/connect/concurrency
- FastAPI containers: https://fastapi.tiangolo.com/deployment/docker/

---

**Kết luận triển khai:** Giai đoạn 1 dựng Docker Compose+Postgres+core+website với tests; Giai đoạn 2 bổ sung review+evaluation+QA+deploy-ready. Không thêm service mới để trang trí. Luôn ưu tiên **đúng tiền > an toàn auto-match > truy vết > giao diện > tối ưu hiệu năng**.
