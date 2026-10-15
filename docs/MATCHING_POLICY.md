# Chính sách matching và phân bổ

## Nguyên tắc xác nhận

Engine dựng toàn bộ graph full-reference trước khi reserve cash. Việc này ngăn một cặp 1:1 lấy mất bank/order thuộc N:1, 1:N hoặc M:N. Một component chỉ được auto-confirm khi:

- reference là full token theo grammar và không collision;
- shape là 1:1, N:1 hoặc 1:N, không phải M:N tổng quát;
- currency đúng policy của run;
- bank là `CREDIT` với `POSTED_CASH` hoặc `NET_SETTLEMENT`;
- date gap nằm trong cửa sổ policy và không có participant đã reserve.

Ngay cả khi link confirmed, amount có thể `PARTIAL` hoặc `OVERPAID`; allocator không tạo edge vượt cash bank hoặc nghĩa vụ order.

## Waterfall

- L1: full/normalized reference, token boundary nghiêm ngặt; graph xác định 1:1, N:1, 1:N.
- L2: strong reference có T+N trong policy có thể confirmed. Amount+date không có identity chỉ là proposal.
- L3: RapidFuzz xếp hạng trong block currency/date/amount; score không phải xác suất và không bao giờ tự confirmed.
- L4: exact subset sum có giới hạn cho N:1/1:N chưa có ref; luôn proposal. Mỗi block có giới hạn size, tổ hợp và group size; search cạn budget tạo `PARTIAL_SEARCH_EXHAUSTED`.

M:N tạo `COMPLEX_MANY_TO_MANY_REVIEW`. Fuzzy, amount/date và subset candidates có thể cạnh tranh cùng participant nhưng chưa làm thay đổi cash/KPI.

## Heuristic chưa được chứng minh phổ quát

Default `max_days_diff=3`, fuzzy threshold 85, top-K 5, group/split size 3, block size 20 và tối đa 2.000 combinations/case là guardrail demo. Chúng không phải quy luật ngành hoặc kết quả benchmark. Mỗi run lưu policy snapshot; thay policy tạo run mới.

## Fee

PSP fee chỉ tạo `VerifiedAdjustment` khi bank là `NET_SETTLEMENT`, channel là PSP, source có `declared_fee_minor`, policy cho phép, và fee đúng residual của order. Bank transfer thiếu 1–2% vẫn là partial. Adjustment không được cộng vào cash bank.

