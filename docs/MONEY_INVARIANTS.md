# Bất biến tiền

## Biểu diễn

BRL dùng 2 chữ số minor unit; VND dùng 0. Parser nhận separator rõ ràng và dùng `Decimal`, sau đó core chỉ cộng/trừ integer. Với VND, giá trị sau khi diễn giải separator chỉ hợp lệ khi phần thập phân bằng 0 (`100000`, `100000.0` hợp lệ; `100000.5` không hợp lệ). Giá trị VND có phần thập phân khác 0 phải sinh `MoneyParseError` và lỗi Health Gate mức `BLOCKING`; hệ thống không làm tròn. Chính sách `ROUND_HALF_UP` vẫn áp dụng cho BRL và không bị thay đổi. `float` không được dùng cho amount trong core; fuzzy score có thể là float vì không phải tiền.

Lỗi parse tiền phải giữ dòng nguồn và giá trị đầu vào. Health Gate cung cấp tên file, sheet nếu có, số dòng và các giá trị raw để người dùng sửa dữ liệu; dòng lỗi không được đi vào canonical input hay matching.

`cash_allocation_minor` là tiền thực nhận. `verified_adjustment_minor` là khoản điều chỉnh nghĩa vụ có policy/chứng cứ, không phải cash và không được dùng để làm đẹp chênh lệch.

## Bất biến theo dòng và toàn run

Với bank credit hợp lệ `C(b)`, allocation confirmed `A(o,b)`, nghĩa vụ `E(o)`, adjustment được xác minh `F(o)`, tiền bank chưa phân bổ `U(b)` và phải thu còn lại `R(o)`:

```text
0 <= SUM_o A(o,b) <= C(b)
U(b) = C(b) - SUM_o A(o,b)

0 <= SUM_b A(o,b) + F(o) <= E(o)
R(o) = E(o) - SUM_b A(o,b) - F(o)

SUM C(b) = SUM A(o,b) + SUM U(b)
SUM E(o) = SUM A(o,b) + SUM F(o) + SUM R(o)
```

Proposal không nằm trong `A`. Debit và gross-only report không nằm trong `C`. Order không eligible không nằm trong `E`.

Mỗi review revision phải kiểm tra lại toàn bộ các phương trình trên trước khi được công bố. Approve chỉ tạo cash edges trong phần residual còn hợp lệ; reject không thay đổi `A` hoặc `F`; undo khôi phục một snapshot trước đó rồi kiểm tra lại invariant. PostgreSQL `current_revision` chỉ được cập nhật trong cùng transaction với audit và effective-state records. Result artifact của revision được ghi nguyên tử trước commit; nếu commit lỗi, transaction rollback và artifact chưa công bố bị loại bỏ.

## Diễn giải chênh lệch

- Underpayment có strong ref: allocation tối đa bằng cash, residual order giữ nguyên và trạng thái `PARTIAL`.
- Overpayment: allocation tối đa bằng nghĩa vụ, phần dư nằm ở bank `unapplied`; không tạo edge vượt order.
- PSP net 98.000 cho gross 100.000: cash edge tối đa 98.000. Chỉ khi có fee policy/evidence hợp lệ mới tạo adjustment 2.000.
- Bank transfer 98.000 cho nghĩa vụ 100.000 không tự sinh fee 2.000.
- N:1 dùng nhiều edges nhưng tổng theo bank chỉ tính một lần và không vượt cash budget.

Phân loại tiền dư không thay đổi các phương trình trên. Một bank/group có `U(b)>0` không chứng minh mỗi order liên quan đã trả thừa. Khi nghĩa vụ từng order đã được phân bổ đủ nhưng bank có nhiều order owners trong confirmed group, các order là `FULL`; phần dư và `OVERPAY_RESIDUAL` vẫn ở bank/group và không cộng lặp vào mỗi order. `OVERPAID` ở cấp order chỉ dùng khi có tiền dư từ bank đã xác nhận thuộc riêng order đó. Với N:1 100.000 + 200.000 và credit 350.000: edges 100.000/200.000, hai order `FULL`, unapplied 50.000 và một residual exception 50.000. Không đổi enum hoặc tạo allocation giả để biểu diễn tiền dư.

Code kiểm tra ở `smartrecon.domain.invariants.check_conservation`. Tests có oracle số học trực tiếp và property cases để tránh chỉ gọi lại cùng helper rồi coi là chứng minh độc lập.

Nguồn kỹ thuật: Python mô tả `decimal` cho số học thập phân chính xác và nhiều chế độ làm tròn; integer minor-unit là quyết định thiết kế của dự án để làm các identity trên kiểm chứng được. Xem `RESEARCH_REFERENCES.md`.
