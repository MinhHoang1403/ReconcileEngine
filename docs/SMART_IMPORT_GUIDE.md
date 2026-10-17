# Smart Data Import

## Luồng sử dụng

1. Chọn hai file CSV/XLSX riêng hoặc một workbook chứa hai sheet. Nếu workbook có tên sheet khó phân biệt, nhập rõ sheet đơn hàng và sheet giao dịch.
2. Đọc khối **Đã phân tích và chuẩn bị dữ liệu**: loại nguồn, file/sheet, dòng tiêu đề và số trường bắt buộc đã xác định.
3. Tập trung vào các mục màu cảnh báo. Mỗi đề xuất có mức tin cậy, lý do và giá trị mẫu; đây là gợi ý deterministic, không phải xác suất.
4. Chọn format ngày riêng cho từng feed nếu dữ liệu ngày/tháng mơ hồ. Chỉ cấu hình separator tiền đúng với file; VND có phần thập phân khác 0 luôn bị chặn.
5. So dữ liệu gốc với **Xem trước dữ liệu sau chuẩn hóa**. Preview cập nhật khi mapping đổi và không tạo run.
6. Nếu cấu trúc được đánh dấu cần xem xét, xác nhận sheet/header sau khi kiểm tra. Nhấn **Xác nhận và chuẩn hóa dữ liệu** để tạo Health snapshot.
7. Khi Health Gate `READY`, có thể tải hai CSV canonical hoặc bắt đầu đối soát.

## Import profile

Tùy chọn lưu profile xuất hiện khi chưa có profile phù hợp. Profile lưu toàn bộ mapping, transformations, date/money parse settings và xác nhận, nhưng không lưu dữ liệu dòng. Fingerprint bao gồm schema của cả hai feed. Lần upload sau chỉ áp dụng profile khi fingerprint và schema version khớp chính xác; đổi tên/thứ tự cột, delimiter hoặc độ sâu header sẽ yêu cầu phân tích/xác nhận lại.

API quản lý profile hỗ trợ list/create/update/delete. Xóa profile không xóa raw upload, Health snapshot, run hay artifacts. Một schema chỉ có một profile để tránh hai cấu hình cùng tự nhận là ưu tiên.

## Những điều hệ thống cố ý không tự làm

- Không chọn ngẫu nhiên giữa hai cột amount/date có bằng chứng ngang nhau.
- Không suy ngày/tháng cho giá trị như `01/02/2026`.
- Không suy chiều từ dấu âm nếu chưa có transformation/profile xác nhận.
- Không đổi gross thành posted cash, không tạo ID giao dịch tùy tiện và không làm tròn VND phân số.
- Không tổng hợp file Shopee theo đợt thành khoản phải thu khi chưa có chính sách về batch, phí, hoàn tiền và khấu trừ.
- Không đưa proposal từ amount/date/fuzzy vào confirmed allocation.
