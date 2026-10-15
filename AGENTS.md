# Quy tắc làm việc trong repository

- Đây là codebase mới, không clone/fork/copy mã từ `dpduc/ReconEngine`.
- Thứ tự ưu tiên đặc tả: yêu cầu chủ dự án và `CODEX_IMPLEMENTATION_BRIEF.md`; `docs/IMPLEMENTATION_PLAN.md`; Phụ lục A/B của `docs/MASTER_PLAN.md`; phần còn lại của master plan.
- Chỉ có hai feed nghiệp vụ: khoản phải thu và giao dịch ngân hàng/PSP. Ground truth chỉ dành cho generator/evaluation/test.
- Python core trong `src/smartrecon` không phụ thuộc FastAPI, SQLAlchemy hay frontend. Backend gọi core; không sao chép business logic.
- Tiền được parse bằng `Decimal` và tính bằng integer minor units. Mọi allocation phải thỏa các bất biến bảo toàn tiền.
- Không tự xác nhận bằng amount/date/fuzzy đơn thuần; thiếu chứng cứ thì proposal/review hoặc unresolved.
- Không dùng nhãn kế hoạch hoặc phiên bản như `v1`, `phase1`, `final`, `new` trong tên module, class, API hay component.
- Stack cố định: Python 3.12, Pandas, DuckDB, RapidFuzz, FastAPI, SQLAlchemy/Alembic, PostgreSQL, React/TypeScript/Vite/Plotly, Docker Compose.
- Không thêm Redis, Celery, Kubernetes, microservice, auth enterprise, FX, ML/LLM hoặc chức năng review/undo thuộc phạm vi sau.
- Raw input bất biến; giữ hash, lineage, mapping/policy snapshot. Không commit `.env`, secrets, dữ liệu tài chính thật hoặc artifact lớn.
- Sau mỗi checkpoint phải chạy test/lint/build liên quan và chỉ commit khi đạt.

