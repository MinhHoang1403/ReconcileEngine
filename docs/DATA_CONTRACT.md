# Hợp đồng dữ liệu

## Hai nguồn logic

Một phiên chỉ nhận hai nguồn: `internal_receivables` và `bank_transactions`. Hai nguồn có thể là hai CSV/XLSX riêng hoặc hai sheet của một workbook. `truth_edges.csv`, `truth_cases.csv` và `manifest.json` chỉ thuộc generator/evaluation, không được gửi qua upload API hoặc import vào matching runtime.

Raw file là bất biến. Mỗi canonical row phải giữ file SHA-256, số dòng nguồn và row hash. ID luôn là chuỗi để bảo toàn số 0 đầu; ngày được parse bằng format/timezone được người dùng xác nhận; tiền được parse bằng `Decimal` rồi chuyển sang integer minor units.

## Khoản phải thu

Trường bắt buộc:

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `order_id` | string | ID nghĩa vụ, unique trong run |
| `ordered_at` | date/datetime | Ngày phát sinh |
| `expected_amount_minor` | integer | Số phải thu không âm |
| `currency` | `VND` hoặc `BRL` | Một currency/run |
| `order_status` | enum | `ELIGIBLE`, `PENDING`, `CANCELED`, `EXCLUDED` |

Các trường `external_ref`, `customer_id`, `customer_name`, `payment_channel`, `batch_ref`, `description` là tùy chọn và chỉ trở thành evidence theo policy phù hợp.

## Giao dịch ngân hàng/PSP

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `bank_txn_id` | string | ID canonical unique; có thể là surrogate ổn định |
| `txn_date` | date/datetime | Ngày giao dịch/ghi sổ theo profile |
| `posted_amount_minor` | integer | Độ lớn không âm |
| `direction` | enum | `CREDIT` hoặc `DEBIT` |
| `amount_basis` | enum | `POSTED_CASH`, `NET_SETTLEMENT`, `GROSS_SETTLEMENT` |
| `currency` | `VND` hoặc `BRL` | Phải cùng currency của run |

Chỉ `CREDIT` với `POSTED_CASH` hoặc `NET_SETTLEMENT` đã xác nhận mới vào cash pool. `GROSS_SETTLEMENT` không được giả làm tiền đã ghi có. `declared_fee_minor` chỉ là evidence nguồn; adjustment cần policy/chứng cứ riêng.

## Group, edge và ba trạng thái

`MatchGroup` biểu diễn `ONE_TO_ONE`, `MANY_ORDERS_ONE_BANK`, `ONE_ORDER_MANY_BANKS` hoặc `AMBIGUOUS_CANDIDATES`. `AllocationEdge` chỉ chứa confirmed cash thật giữa đúng một order và một bank row. Candidate/proposal không tạo effective edge và không tham gia KPI confirmed.

Ba trạng thái độc lập:

- `link_status`: `CONFIRMED`, `PROPOSED`, `UNMATCHED`, `REJECTED`.
- `payment_status`: `FULL`, `PARTIAL`, `OVERPAID`, `NO_CONFIRMED_RECEIPT`, `UNKNOWN`, `NOT_ELIGIBLE`.
- `review_status`: `NOT_REQUIRED`, `OPEN`, `APPROVED`, `REJECTED`, `NEEDS_MORE_INFO`, `UNDONE`.

Vì vậy strong reference có thể tạo `CONFIRMED + PARTIAL`; tìm đúng quan hệ không đồng nghĩa đã thu đủ tiền.

## Tái lập và checksum

Semantic checksum bao gồm canonical input, mapping, policy và rule version theo thứ tự ổn định. `run_id`, timestamp hệ thống và đường dẫn artifact không thuộc semantic checksum. Generator cùng seed/config tạo cùng semantic payload; workbook XLSX chỉ cam kết semantic-equivalent vì metadata ZIP có thể khác theo lần ghi.

