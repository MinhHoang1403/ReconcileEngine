# Nguồn dữ liệu và ghi công

## Bộ VND synthetic

`data/demo/vn_synthetic_demo` được sinh hoàn toàn bởi code của dự án, không chứa giao dịch ngân hàng hoặc dữ liệu cá nhân thật. `bank_transactions.csv` là feed synthetic. Generator, seed, currency, timezone, counts và semantic hashes nằm trong `manifest.json`. Truth nằm riêng ở `truth_edges.csv` và `truth_cases.csv`; hai feed nghiệp vụ không chứa nhãn scenario/truth.

Tạo lại:

```powershell
uv run python scripts/generate_demo.py --seed 42 --orders 100
```

## Olist

Dự án không commit, tự tải hoặc giả lập bản ghi Olist. Adapter `smartrecon.generation.olist.prepare_olist_derived_sample` chỉ chạy khi người dùng cung cấp tối thiểu `olist_orders_dataset.csv` và `olist_order_payments_dataset.csv` hợp lệ.

Olist không chứa sao kê ngân hàng. Adapter giữ order/time/payment totals quan sát từ source và sinh feed bank với nhãn `synthetic_not_bank_statement`; provenance lưu SHA-256 nguồn và liệt kê cột observed/synthetic.

Nguồn công bố tham khảo: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Tài liệu kế hoạch ghi nhận trang dataset hiển thị CC BY-NC-SA 4.0 tại thời điểm soạn; phải xác minh lại điều khoản tại thời điểm tải/phân phối và tuân attribution, non-commercial, ShareAlike nếu áp dụng. Không có dữ liệu Olist nào được phân phối trong repository này.

