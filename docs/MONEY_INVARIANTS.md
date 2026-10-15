# Bất biến tiền

## Biểu diễn

BRL dùng 2 chữ số minor unit; VND dùng 0. Parser nhận separator rõ ràng, dùng `Decimal` và `ROUND_HALF_UP`, sau đó core chỉ cộng/trừ integer. `float` không được dùng cho amount; fuzzy score có thể là float vì không phải tiền.

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

## Diễn giải chênh lệch

- Underpayment có strong ref: allocation tối đa bằng cash, residual order giữ nguyên và trạng thái `PARTIAL`.
- Overpayment: allocation tối đa bằng nghĩa vụ, phần dư nằm ở bank `unapplied`; không tạo edge vượt order.
- PSP net 98.000 cho gross 100.000: cash edge tối đa 98.000. Chỉ khi có fee policy/evidence hợp lệ mới tạo adjustment 2.000.
- Bank transfer 98.000 cho nghĩa vụ 100.000 không tự sinh fee 2.000.
- N:1 dùng nhiều edges nhưng tổng theo bank chỉ tính một lần và không vượt cash budget.

Code kiểm tra ở `smartrecon.domain.invariants.check_conservation`. Tests có oracle số học trực tiếp và property cases để tránh chỉ gọi lại cùng helper rồi coi là chứng minh độc lập.

Nguồn kỹ thuật: Python mô tả `decimal` cho số học thập phân chính xác và nhiều chế độ làm tròn; integer minor-unit là quyết định thiết kế của dự án để làm các identity trên kiểm chứng được. Xem `RESEARCH_REFERENCES.md`.

