# Hợp đồng dữ liệu

## Hai nguồn logic

Một phiên chỉ nhận hai nguồn: `internal_receivables` và `bank_transactions`. Hai nguồn có thể là hai CSV/XLSX riêng hoặc hai sheet của một workbook. `truth_edges.csv`, `truth_cases.csv` và `manifest.json` chỉ thuộc generator/evaluation, không được gửi qua upload API hoặc import vào matching runtime.

Raw file là bất biến. Mỗi canonical row phải giữ file SHA-256, số dòng nguồn và row hash. ID luôn là chuỗi để bảo toàn số 0 đầu; ngày được parse bằng format/timezone được người dùng xác nhận; tiền được parse bằng `Decimal` rồi chuyển sang integer minor units. Separator thập phân/hàng nghìn phải theo mapping đã xác nhận. Với VND, phần thập phân sau khi diễn giải separator phải bằng 0; nếu khác 0, dòng bị từ chối bằng lỗi Health Gate `BLOCKING`, không làm tròn và không đi tiếp vào matching. BRL giữ chính sách hai minor digits hiện hành.

## Nhận diện cấu trúc và chuẩn hóa thích ứng

Reader chỉ xét UTF-8/UTF-8-SIG cho CSV và các delimiter cho phép `,`, `;`, tab, `|`. XLSX được đọc theo sheet và vùng tiêu đề đã phát hiện; giới hạn kích thước ZIP, số sheet, dòng và cột vẫn áp dụng. Kết quả inspection lưu sheet, delimiter, dòng/độ sâu header, các phương án cạnh tranh, lý do chọn và chính xác số dòng nguồn. Dòng trống có thể bỏ qua; footer/tổng cộng không được âm thầm bỏ mà phải đi qua chuẩn hóa/Health Gate.

Mapping suggestion là heuristic giải thích được, không phải xác suất. Mỗi đề xuất có cột nguồn hoặc transformation, điểm heuristic, mức tin cậy, lý do, ứng viên cạnh tranh và mẫu trước/sau. Ngày ở chế độ `AUTO` chỉ nhận ISO/năm-trước hoặc ngày-tháng không mơ hồ; trường hợp như `01/02/2026` phải chọn format rõ ràng. Hai feed có thể dùng format ngày riêng.

Transformation chỉ chạy khi nằm trong mapping snapshot:

- `SPLIT_CREDIT_DEBIT` dùng đúng một cột ghi có hoặc ghi nợ khác 0 để dựng amount/direction; cả hai cùng có tiền hoặc cùng bằng 0 là lỗi chặn.
- `SIGNED_AMOUNT` chỉ hợp lệ khi profile/cấu hình nêu rõ chiều của số dương.
- `VALUE_MAP` đổi các enum như `CR/DR` hoặc trạng thái tiếng Việt theo bảng đã xác nhận; giá trị ngoài bảng bị chặn.

Không tự đổi `GROSS_SETTLEMENT` thành cash, không tự tạo ID giao dịch thiếu và không tự tổng hợp Shopee payout theo đợt. Snapshot normalization gồm mapping, transformation version, parse settings, xác nhận của người dùng và profile ID/schema version nếu có.

Import profile đã lưu gắn với fingerprint SHA-256 của schema hai feed, gồm tên/cấu trúc cột theo thứ tự, độ sâu header và delimiter, cùng `schema_version`. Profile chỉ được tái sử dụng khi cả fingerprint và version khớp; structure drift không được áp dụng gần đúng. Profile có thể sửa/xóa qua API, nhưng cập nhật mapping chỉ nhận một upload session có cùng schema.

Fingerprint không chứng minh ngữ nghĩa của giá trị. Trước khi tái áp dụng profile, hệ thống chuẩn hóa **toàn bộ** dòng bằng cấu hình đã lưu; có lỗi `BLOCKING` thì không áp dụng profile, trả `reuse_issue_codes` và dùng phân tích hiện tại. Không sửa/xóa profile cũ. Gợi ý compatibility `suggested_mapping` không được điền lại trường mà `mapping_suggestions.selected_mapping` đã abstain (không tự quyết định). Frontend không coi alias legacy là bằng chứng tự chọn.

Mapping dùng tối đa 100 vị trí trải đều trên bảng làm bằng chứng và tối đa 5 ví dụ hiển thị; đây không phải kiểm tra toàn bộ dữ liệu. Cột tiền/ngày rỗng, có giá trị mẫu không đọc được hoặc cần quy ước dấu không được tự chọn chỉ nhờ tên/profile. Health Gate vẫn kiểm tra mọi dòng, kể cả dòng không được lấy mẫu. Điểm heuristic không phải xác suất đã hiệu chuẩn.

Dòng có nhãn tổng báo cáo được structure detector đánh dấu phải bị chặn khi chuẩn hóa, kể cả có ngày/số tiền hợp lệ và `confirmed_structure=true`. Xác nhận sheet/header không phê duyệt dòng tổng thành giao dịch. Raw row/hash vẫn giữ nguyên; rejection lưu dòng nguồn. Chỉ sửa nguồn hoặc loại trừ tường minh kèm lý do mới giải quyết lỗi này; không tự xóa dòng.

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

`FULL` biểu diễn nghĩa vụ order đã được phân bổ/điều chỉnh hợp lệ đủ; vẫn có thể tồn tại tiền chưa phân bổ ở bank/group. `OVERPAID` cấp order chỉ khi bank dư có confirmed ownership riêng cho order đó. Bank được gắn với nhiều order không làm tất cả order thành `OVERPAID`; residual được báo một lần theo bank. `NO_CONFIRMED_RECEIPT` nghĩa là chưa có tiền được xác minh, không khẳng định khách chưa trả. `UNKNOWN` dùng khi còn proposal cần kiểm tra. Nguồn order không eligible vẫn nằm trong raw/canonical upload và không nằm trong effective matching input/KPI như contract hiện hành; không suy `UNKNOWN`/nợ xấu từ việc bị loại khỏi input. Không materialize thêm order hoặc thay enum/API trong đợt sửa classification này.

Mỗi response phân trang của explorer mang `run_id` và `effective_revision`. Dashboard analytics được dẫn xuất từ đúng effective result: tỷ lệ xác nhận có mẫu số là toàn bộ nhóm quan hệ; độ trễ là số ngày giữa ngày đơn và ngày giao dịch cho từng allocation pair đã xác nhận; phân bố residual giữ riêng `order_outstanding` và `bank_unapplied`. Review audit là chuỗi sự kiện bất biến, còn trạng thái nhóm nằm trong snapshot revision.

## Tái lập và checksum

Semantic checksum bao gồm canonical input, mapping, policy và rule version theo thứ tự ổn định. `run_id`, timestamp hệ thống và đường dẫn artifact không thuộc semantic checksum. Generator cùng seed/config tạo cùng semantic payload; workbook XLSX chỉ cam kết semantic-equivalent vì metadata ZIP có thể khác theo lần ghi.
