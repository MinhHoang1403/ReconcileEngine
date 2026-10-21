# Triển khai và khôi phục

Tài liệu này áp dụng cho một máy chủ chạy Docker Compose. SmartRecon có ba dịch vụ chạy dài hạn (`frontend`, `backend`, `db`) và một job `migrate` chạy một lần rồi thoát thành công. PostgreSQL không publish cổng ra host; frontend và backend mặc định chỉ bind `127.0.0.1`.

## Chuẩn bị cấu hình

Yêu cầu Docker Engine/Desktop có Compose. Trên Windows dùng Docker Desktop với Linux containers; trên Linux VPS cài Docker Engine và Compose plugin, đồng thời chỉ cấp quyền Docker cho tài khoản vận hành tin cậy.

Tạo `.env` từ `.env.example` nhưng thay toàn bộ giá trị ví dụ:

```dotenv
POSTGRES_DB=smartrecon
POSTGRES_USER=smartrecon
POSTGRES_PASSWORD=<mat-khau-ngau-nhien-dai>
DATABASE_URL=postgresql+psycopg://smartrecon:<mat-khau-da-url-encode>@db:5432/smartrecon
CORS_ORIGINS=https://reconcile.example.com
DEMO_MODE=false
BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_IMAGE=smartrecon-backend:release
FRONTEND_IMAGE=smartrecon-frontend:release
```

Không commit `.env`. Trên Linux đặt quyền đọc tối thiểu bằng `chmod 600 .env`. Nếu mật khẩu chứa ký tự đặc biệt trong URL, phải percent-encode phần mật khẩu của `DATABASE_URL`. Compose production từ chối khởi động khi thiếu password, database URL, CORS origin hoặc tên image. Giá trị `change-this-local-password` trong file mẫu chỉ để local và phải được người vận hành thay; Compose không thể tự đánh giá độ mạnh của secret.

## Windows Docker Desktop

```powershell
Copy-Item .env.example .env
# Sửa .env trước khi tiếp tục
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml build
docker compose -f compose.yaml -f compose.production.yaml up -d
docker compose -f compose.yaml -f compose.production.yaml ps -a
```

Job `migrate` phải có trạng thái `Exited (0)`; `db`, `backend`, `frontend` phải `healthy`. Kiểm tra thêm:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
docker compose -f compose.yaml -f compose.production.yaml run --rm migrate uv run alembic current
```

## Linux VPS, reverse proxy và HTTPS

Clone đúng commit/tag đã nghiệm thu, tạo `.env`, rồi chạy cùng hai file Compose:

```bash
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml build
docker compose -f compose.yaml -f compose.production.yaml up -d
docker compose -f compose.yaml -f compose.production.yaml ps -a
curl --fail http://127.0.0.1:8000/healthz
```

Đặt reverse proxy đã được quản trị trên host trước `127.0.0.1:5173`; không đổi backend hoặc PostgreSQL thành cổng public. Ví dụ tối thiểu cho Nginx host:

```nginx
server {
    listen 443 ssl;
    server_name reconcile.example.com;
    ssl_certificate /etc/letsencrypt/live/reconcile.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/reconcile.example.com/privkey.pem;

    client_max_body_size 25m;
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:5173;
    }
}
```

Cấp và gia hạn certificate bằng quy trình chuẩn của tổ chức. Redirect HTTP sang HTTPS và firewall chỉ mở cổng cần thiết. Container frontend đã reverse proxy `/api` và `/healthz` tới backend trong Docker network.

## Migration có kiểm soát

`migrate` là consumer duy nhất chạy `alembic upgrade head`; backend chỉ khởi động sau khi job hoàn tất. Không scale hoặc chạy đồng thời nhiều job migration. Trước khi cập nhật schema:

1. Tạo backup và chạy restore drill.
2. Đọc migration mới, kiểm tra hướng nâng cấp và tương thích rollback ứng dụng.
3. Chạy `docker compose ... run --rm migrate` trong maintenance window nếu không dùng luồng `up` thông thường.
4. Xác nhận `uv run alembic current` là head rồi mới phục vụ traffic.

Không dùng `alembic stamp` để bỏ qua migration trên dữ liệu đang vận hành.

## Backup và restore drill

Backup phải bao gồm cả PostgreSQL lẫn artifact volume. Lệnh sau tạo custom-format `postgres.dump`, bản sao raw/canonical/result/export artifacts và `manifest.json` có SHA-256 cùng snapshot kiểm tra:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
uv run python scripts/backup_restore.py backup "reports/backups/$stamp" --project smartrecon_lab --pause-lab-writes --base-url http://127.0.0.1:8002 --run-id <run-id-da-luu>
uv run python scripts/backup_restore.py restore-drill "reports/backups/$stamp"
```

Trên Linux thay biến PowerShell bằng đường dẫn timestamp tương đương. Restore drill:

- xác minh checksum dump và SHA-256 của từng artifact trước khi restore;
- tạo Compose project, database volume, artifact volume và cổng ngẫu nhiên riêng;
- restore bằng `pg_restore --clean --if-exists` chỉ vào database thử độc lập;
- kiểm tra lại run/revision, audit history, allocation count/tổng tiền, KPI, conservation và tạo lại XLSX;
- dừng project thử có tên `smartrecon_restore_<random>` sau khi đạt và giữ volumes để kiểm tra lại.

Mọi lệnh Compose cần project rõ ràng. Script mặc định chỉ dừng writer Lab/restore. Project chính `reconcileengine` phải có phê duyệt chủ dự án và cờ riêng `--approve-main-maintenance`; `--leave-writer-stopped` giữ đóng ghi trong lúc cutover. Script xác minh URL, volume thuộc project và sole writer, drain trước pg_dump/copy; DB client khác làm backup thất bại. Không tuyên bố backup online là nguyên tử. Frontend đã dừng vẫn được nhận diện image bằng `ps --all`.

Mỗi backup giữ image tags/IDs, SHA từng file và frozen DB table hashes. Restore kiểm tra IDs rồi `--no-build --pull never`. `--keep` giữ project drill chạy; mặc định dừng, không xóa volumes/images. Dữ liệu backup có thể nhạy cảm: giữ ngoài Git, hạn chế truy cập, chuyển storage mã hóa theo chính sách chủ dự án. Backup chính chỉ trong maintenance đã phê duyệt.

## Cutover đã được chủ dự án phê duyệt ngày 2026-10-21

Chỉ sau gates A–F và rehearsal G. Runtime release `4328cf4`: backend `smartrecon-backend:release-4328cf4` / image `sha256:decd29e02e96d3f5f69b2fa772b08c99000a5597426dd920db0c0b746e8b09b2`, frontend `smartrecon-frontend:release-4328cf4` / `sha256:ec663c0eebe0836825208229f1bcae66a0967acc6b4a517e06176c4fe875f09e`. Host scripts/runbook có commit riêng; không nằm trong runtime image. Dependencies root giữ uv.lock/package-lock; nghiên cứu giữ research/uv.lock, không thêm dependencies nghiên cứu vào production. Migration mới: **không**, head `20261017_04`; ORM đã khớp schema hiện hữu theo phê duyệt.

1. Công bố maintenance, đóng frontend chính và drain backend. Backup `--project reconcileengine --approve-main-maintenance --leave-writer-stopped` từ trạng thái hiện tại, không dùng snapshot Lab hoặc snapshot cũ.
2. Verify checksum dump/từng artifact, restore-drill riêng; kiểm tra run mới nhất, revisions, audit, cash/conservation và Excel.
3. `scripts/deploy_release.py` cần `--approve-main-cutover`, đúng workspace `C:\Work\ReconcileEngine`, chỉ nhận backup chính đã phê duyệt, writer dừng và DB hashes vẫn khớp. Sinh **hai volume mới** với tên ngẫu nhiên; từ chối volume đã tồn tại. Restore không `--clean` vào DB cũ. Copy artifacts trước khi mở writer; check DB/files/snapshot và Alembic rồi mở frontend 5173/API 8000. Không đưa dữ liệu thí nghiệm vào chính.
4. Sau xác minh, lưu trong `.env` bị ignore: image tags, `POSTGRES_VOLUME`, `ARTIFACTS_VOLUME`, `COMPOSE_FILE=compose.yaml;compose.storage.yaml` (Windows; Linux dùng `:`). `compose.storage.yaml` chỉ chọn storage generation, không đổi kiến trúc. Giữ `.env` cũ và old volume names trong bản sao lưu local ngoài Git.
5. Smoke upload→Health→run→dashboard→Excel và review/history trên chính chỉ sau phê duyệt; test synthetic được ghi rõ. Kiểm tra lại toàn bộ dữ liệu cũ, restart, health và source/GitHub CI.

Rollback A (chưa có ghi mới): dừng app, dùng image `rollback-4dfd62e` và đúng DB/artifact volumes cũ, giữ nguyên candidate volumes. Rollback B (đã có ghi): đóng ghi, backup **mới**; chỉ rollback application trên storage mới khi schema tương thích đã được rehearsal chứng minh. Không bật DB snapshot cũ rồi coi run mới còn. Rehearsal đã thêm một run+approval revision 1 và xác minh toàn bộ bảng/files cùng snapshot khi quay về old app, sau đó trở lại candidate. Nếu schema không tương thích hoặc checksum lệch: NO-GO, giữ mọi storage và xin quyết định, không xóa/ghi đè dữ liệu để rollback.

RPO dự kiến **0 với ghi đã commit trong maintenance được drain**; không hứa khôi phục thao tác người dùng chưa gửi/commit. Downtime gồm backup+restore-drill+restore+health, không có HA/zero-downtime. Dọn sau nghiệm thu chỉ container Lab/restore và container ứng dụng cũ đã xác định; không volume prune/image prune, không chạm dự án khác. Giữ backup, rollback images và old volumes để quay lại.

## Môi trường nghiên cứu độc lập

Mã thử nghiệm nằm trong `C:\Work\ReconcileEngine-Lab`, nhánh `research/import-reconciliation`; workspace và project chính `reconcileengine` giữ nguyên. Khởi tạo từ worktree riêng:

```powershell
uv run python scripts/lab_environment.py initialize
docker compose --project-name smartrecon_lab -f compose.yaml -f compose.lab.yaml config --quiet
docker compose --project-name smartrecon_lab -f compose.yaml -f compose.lab.yaml build backend frontend
docker compose --project-name smartrecon_lab -f compose.yaml -f compose.lab.yaml up --no-build -d
```

`initialize` tạo `.env` bị ignore, mật khẩu ngẫu nhiên riêng và image tags lab; từ chối ghi đè file đã có hoặc chạy trên `main`. Website lab ở `127.0.0.1:5174`, API ở `127.0.0.1:8002` (8001 đã được ShopQuery sử dụng). PostgreSQL không publish. Backend dùng `/artifacts/lab` trên `smartrecon_lab_artifacts_data`; database ở `smartrecon_lab_pg_data`; network `smartrecon_lab_default`. Không dùng external volume, bind mount source hoặc container_name.

`lab_environment.py inventory --project ... --directory ... --api-url ... --output ...` chỉ đọc trạng thái. Nó lưu container/image/mount/network/port, hash từng bảng DB, fingerprint toàn bộ artifact files và ba run mẫu. `compare_inventories` đối chiếu trước/sau để phát hiện thay đổi ở hệ thống chính và volume/network dùng chung. JSON chi tiết nằm trong `reports/lab/`, không commit. Chỉ mở website chính và các endpoint GET không phát sinh export trong quá trình kiểm tra chính; mọi upload/run/review/browser smoke chạy ở lab.

## Restart, cập nhật và rollback ứng dụng

Restart an toàn, không xóa volume:

```bash
docker compose -f compose.yaml -f compose.production.yaml down
docker compose -f compose.yaml -f compose.production.yaml up -d
```

Tuyệt đối không thêm `--volumes`/`-v` cho stack thật. Khi cập nhật:

1. backup + restore drill;
2. fetch commit/tag đã duyệt;
3. build hoặc pull image có tag bất biến;
4. kiểm tra `config --quiet`;
5. chạy migration một lần;
6. recreate backend/frontend và kiểm tra health, run đã lưu, dashboard, export.

Rollback code chỉ an toàn nếu schema mới còn tương thích. Nếu migration không tương thích ngược, phục hồi cả database và artifacts từ cùng một backup vào môi trường riêng, xác minh rồi mới thực hiện cutover theo quy trình thay đổi của tổ chức.

## Logs và health

```bash
docker compose -f compose.yaml -f compose.production.yaml ps -a
docker compose -f compose.yaml -f compose.production.yaml logs --since 30m db migrate backend frontend
docker compose -f compose.yaml -f compose.production.yaml exec -T backend uv run alembic current
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:5173/
```

Không bật debug dump environment hoặc log payload tài chính. Cấu hình log rotation ở Docker daemon/host theo chính sách vận hành; ứng dụng hiện không cung cấp log aggregation riêng.

## Giới hạn bảo mật khi public deploy

Ứng dụng hiện chưa có authentication/RBAC, tenant isolation, rate limiting, malware scanning, secret manager, audit identity đã xác thực hoặc HA database. `actor_label` là nhãn tự khai, không phải danh tính. Vì vậy không được public trực tiếp cho người dùng không tin cậy; phải đặt sau HTTPS, access control của hạ tầng và mạng riêng phù hợp. File `.env` vẫn là secret ở cấp host và biến môi trường có thể lộ qua quyền quản trị Docker; môi trường yêu cầu assurance cao phải tích hợp secret management bên ngoài trong một thay đổi kiến trúc được phê duyệt.

## Nguồn chính thức

- [Docker: dùng Compose trong production](https://docs.docker.com/compose/how-tos/production/)
- [Docker: startup order và `service_completed_successfully`](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker: named volumes](https://docs.docker.com/engine/storage/volumes/)
- [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/17/app-pgdump.html) và [`pg_restore`](https://www.postgresql.org/docs/17/app-pgrestore.html)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Nginx HTTPS](https://nginx.org/en/docs/http/configuring_https_servers.html) và [HTTP proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
