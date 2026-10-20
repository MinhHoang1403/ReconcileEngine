# Báo cáo nghiệm thu hệ thống

## Đợt nghiên cứu trên môi trường độc lập — 2026-10-20

Yêu cầu mới được triển khai trên nhánh `research/import-reconciliation`, worktree `C:\Work\ReconcileEngine-Lab`, lấy baseline `4dfd62e3bf8289477e291463f5afa4b41c0505d4`. Kết luận nghiệm thu cũ bên dưới chỉ áp dụng cho baseline, không chứng nhận các cải tiến đang nghiên cứu.

| Checkpoint của đợt nghiên cứu | Trạng thái |
|---|---|
| A — Lab độc lập và backup/restore | Đã có bằng chứng cách ly, restore và baseline; xem QA_REPORT |
| B — Auto mapping, Valentine/COMA và validation | Đạt trên fixture độc lập và Lab; 192 Python/20 frontend tests, xem QA/EVALUATION_REPORT |
| C — Matching, Splink/CP-SAT và đối chứng | Đạt trên bộ công bố/Lab; 204 Python/20 frontend tests, không tích hợp dependencies nghiên cứu vào runtime |
| D — Classification và residual theo cấp nghiệp vụ | Chưa nghiệm thu |
| E — Workflow gần một nút và usability | Chưa nghiệm thu |
| F — Đối chứng tổng hợp/regression | Chưa nghiệm thu |
| G — Diễn tập cutover/rollback và quyết định GO/NO-GO | Chưa đủ điều kiện đề xuất |

Hệ thống chính giữ nguyên source/branch, container/image IDs, DB table hashes, artifact fingerprint và các sample run/KPI. Lab ở 5174/8002 với storage/network riêng; cổng 8001 thuộc project khác. Dữ liệu dùng cho backup/drill là synthetic. Script từ chối tự dừng writer của project chính; cutover và maintenance chính vẫn cần phê duyệt riêng. Không push `main`.

Nguồn bằng chứng thực thi nằm trong `reports/lab/` và `reports/backups/lab-consistent-20261020/` ở worktree nghiên cứu; chúng bị Git ignore. Chi tiết lệnh, kết quả, sự cố image tag đã tái hiện và cách sửa nằm tại `QA_REPORT.md`/`DEPLOYMENT.md`.

Ngày nghiệm thu: 2026-10-16

Commit ứng dụng được nghiệm thu clean-clone: `454cad3e3bc7d66685879ca5830fa610bb891e38`

Nhánh: `main`

## Kết luận

Toàn bộ phạm vi Giai đoạn 2 đã hoàn tất theo Checkpoint A–F và các gate kỹ thuật đã đạt. Workflow từ dữ liệu nguồn đến Health Gate, reconciliation, review có revision, dashboard, tra cứu và Excel export chạy trên PostgreSQL/artifact volume thật. Không phát hiện P0/P1 chưa xử lý và không thay đổi thuật toán matching/allocation ngoài phạm vi đã duyệt.

Kết luận này là nghiệm thu cho phạm vi single-host Docker Compose đã đặc tả, không phải chứng nhận cho public banking SaaS. Authentication/RBAC, tenant isolation, rate limiting, malware scanning, secret manager, HA và dữ liệu thật nằm ngoài phạm vi; hệ thống không được public trực tiếp khi chưa có các lớp kiểm soát đó.

## Phạm vi đã giao

| Checkpoint | Kết quả chính | Trạng thái |
|---|---|---|
| A | PostgreSQL review foundation, immutable revisions, optimistic concurrency, idempotency và rollback | PASS |
| B | Review queue/history, approve/reject/undo, conflict/dependency protection và UI human-in-the-loop | PASS |
| C | Analytics theo effective revision, explorer nhất quán và Excel audit/reporting | PASS |
| D | Notebook kernel sạch, truth evaluator tách biệt, metrics/ablation và benchmark 1.000 orders | PASS |
| E | Concurrency QA, browser E2E bốn viewport, security regression và scenario benchmark | PASS |
| F | Production Compose, one-shot migration, non-root images, backup/restore, CI container build và clean-clone | PASS |

## Bằng chứng kiểm thử tự động

| Gate | Kết quả thực tế |
|---|---|
| Ruff lint | PASS |
| Ruff format check | 96 files formatted đúng |
| Python regression | 103 passed |
| Golden | 28 passed; catalog có đủ 24 fixtures F01–F24 |
| Property/invariants | 4 passed |
| Frontend lint | PASS |
| Frontend tests | 19 passed trong 6 files |
| Frontend production build | PASS; warning chunk Plotly đã công bố |
| npm audit | 0 vulnerabilities |
| Compose local/production config | PASS |
| Docker release image build | PASS |
| GitHub Actions | Run `38847228208`: backend, frontend, containers đều success |

Python test còn hai warning môi trường không làm thay đổi kết quả: deprecation của FastAPI/Starlette TestClient và selector-thread fallback của Jupyter ZMQ trên Windows. GitHub-hosted runner cảnh báo các action cũ đang được ép chạy Node 24; workflow vẫn success và đây là maintenance warning, không phải lỗi ứng dụng.

## Độ đúng matching và bảo toàn tiền

Holdout độc lập có edge precision `1,0000`, recall `0,9149`, F1 `0,9556`; group exact precision `1,0000`, recall `0,9348`; candidate recall `1,0000`; false auto-confirm bằng `0`. Allocation MAE `14.893,62 VND`, tổng absolute error `700.000 VND` là các truth edges review-only được dự đoán bằng 0, không phải phân bổ confirmed sai số tiền.

Evaluation hard-profile 1.000 orders/998 bank rows, seed `20261016`, chạy lại ở gate cuối trong `3,112` giây trên máy nghiệm thu; edge F1 `0,9961`, false auto-confirm count `0`. Metrics synthetic không được diễn giải thành accuracy trên sao kê thật.

Mọi revision 0–3 trong concurrency QA đều qua oracle độc lập cho hai phương trình receivable/bank. Một bank row không bị cấp vượt; proposal không đi vào confirmed KPI trước approve; reject không tạo allocation; undo không xóa audit history. Quy tắc VND từ chối phần thập phân khác 0 tại Health Gate tiếp tục được bao phủ bởi unit/API/CSV/XLSX regression, còn BRL không đổi.

## PostgreSQL concurrency và review

Run QA `deff0a5b-690e-4f24-9857-e53448e7afae` nhận hai approve request barrier-synchronized cùng revision 0: đúng một request HTTP 200 và một request 409 `STALE_REVISION`. Retry cùng idempotency key/payload trả action cũ; tái dùng key với payload khác bị từ chối. Approve M:N không được hỗ trợ rollback với `COMPLEX_GROUP_NOT_APPROVABLE`; undo có downstream action bị chặn bằng `UNDO_DEPENDENCY_CONFLICT`.

Revision cuối là 3 với ba audit actions, 92 allocation edges và confirmed cash `66.531.000 VND`. Dashboard conservation hợp lệ; workbook có 9 sheets, không có formula cell từ dữ liệu nguồn và tổng allocation khớp KPI.

## Backup và restore độc lập

Backup thực tế gồm:

- PostgreSQL custom dump 570.875 bytes, SHA-256 `480ea869d36632564584cad94ca6e1559cce87a1febda7fab6a873e4ad726dd1`;
- 482 files từ artifact volume, tổng 32.680.774 bytes;
- manifest chứa run/revision/checksum, KPI, audit total và allocation total.

Restore drill dùng project `smartrecon_restore_1fa8c95d82`, database/artifact volumes và cổng riêng. Kết quả phục hồi đúng run revision 3, ba audit actions, 92 allocation edges tổng `66.531.000 VND`, conservation `true` và tạo lại XLSX 55.062 bytes. Project/volumes thử đã được xóa có kiểm soát; stack chính không bị ghi đè.

## Production Compose và persistence

Project production-check độc lập có `db`, `backend`, `frontend` healthy; job `migrate` `Exited (0)` và API trả `ok`. Backend chạy user `app`, frontend chạy user `nginx`; PostgreSQL không publish cổng. Migration chỉ do job one-shot chạy, backend chờ `service_completed_successfully`.

Sau `docker compose down` không kèm `-v` và `docker compose up -d`, stack chính giữ 64 runs, 100 run revisions, 479 artifact manifests; run revision 3 vẫn trả confirmed cash `66.531.000 VND` và conservation hợp lệ.

## Clean-clone acceptance

Repository được clone mới từ GitHub tại đúng SHA `454cad3e3bc7d66685879ca5830fa610bb891e38`, worktree sạch và dùng image tags, ports, project, PostgreSQL/artifact volumes riêng. Build không còn thử pull image ứng dụng nội bộ trước khi build.

Trên run clean-clone `9c23f1a7-da5b-44ea-8ecb-d2316968cce2`:

- ba service dài hạn healthy; migration exit 0;
- concurrency trả `[409, 200]`, revision 3, ba audit actions;
- conservation đúng ở revisions 0–3; rollback/dependency/stale/idempotency đều đúng mã lỗi;
- export ban đầu 55.070 bytes;
- sau `down`/`up` không xóa volume, số run giữ `1 → 1`, mở lại đúng revision 3 và cash `66.531.000 VND`;
- frontend trả HTTP 200; export sau restart trả HTTP 200, 55.069 bytes;
- clone vẫn sạch sau toàn bộ workflow.

Project và hai volume clean-clone đã được xóa sau nghiệm thu. Named volumes của stack chính được giữ nguyên.

## Git và CI

| Nhóm | Commit | GitHub Actions |
|---|---|---|
| Checkpoint A | `0c3ac78` | `38837884532` success |
| Checkpoint B | `1a1cefc` | `38839720097` success |
| Checkpoint C | `30c88c7` | `38841306823` success |
| Checkpoint D | `325d4a9` | `38842910890` success |
| Checkpoint E | `20f495b` | `38844642548` success |
| Checkpoint F | `86ad9a9` | `38846375552` success |
| Clean-build fix | `454cad3` | `38847228208` success |

Các commit đã push an toàn lên `origin/main`, không force-push. `.env`, runtime uploads, database và reports/artifacts không được commit.

## Giới hạn còn lại

- Chưa có auth/RBAC và actor identity xác thực; không public trực tiếp.
- Chưa đánh giá accuracy bằng dữ liệu tài chính thật.
- Upload cap 100.000 rows là guardrail, không phải bằng chứng hệ thống đã load-test tới mức đó.
- Plotly bundle còn khoảng 1,54 MB raw/503 KB gzip.
- Backup cần đưa ra storage mã hóa và có retention/monitoring của tổ chức; named volume không tự là backup.
- Reverse proxy/HTTPS/access control là trách nhiệm triển khai theo `docs/DEPLOYMENT.md`.

## Tài liệu bàn giao

- `README.md`: quick start, workflow và lệnh QA.
- `docs/API_CONTRACT.md`: endpoint, DTO và mã lỗi.
- `docs/ARCHITECTURE.md`: boundary core/backend, persistence và migration.
- `docs/DEPLOYMENT.md`: Windows/Linux, production Compose, HTTPS, migration, backup/restore, update và logs.
- `docs/EVALUATION_REPORT.md`: evaluation protocol, metrics, ablation và benchmark.
- `docs/QA_REPORT.md`: bằng chứng chi tiết theo từng đợt kiểm thử.
- `docs/RESEARCH_REFERENCES.md`: nguồn nghiên cứu và tài liệu chính thức.
