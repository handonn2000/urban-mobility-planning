# Quy tắc triển khai

- Phạm vi chính cho phí/khuyến mãi/dự báo là 01/2024, 01/2025, 02/2025. Người dùng đã đồng ý mở rộng riêng phần mưa: rà thời tiết 2024 và chọn cửa sổ liên tục 3-6 tháng trước khi xem kết quả chuyến. Cửa sổ được chọn là 06-08/2024. Không thêm machine learning.
- File raw bất biến; đọc chuyến lớn bằng DuckDB, không nạp toàn bộ vào pandas.
- Mỗi module có mô tả phương pháp, đầu ra, kiểm tra hoàn thành và nhật ký.
- Không thay số thật bằng số minh họa. Kết quả khác kỳ vọng vẫn phải báo cáo.
- Chỉ tiêu chính là chuyến hoàn thành, đại diện cho nhu cầu được phục vụ.
- Ước tính phí/khuyến mãi có giả định; không diễn giải thành bằng chứng nhân quả chắc chắn.
- Lyft cấp credit tương lai, không phải hoàn tiền mặt; kinh tế khuyến mãi là mô hình kịch bản.
- Dự báo giả lập chỉ sử dụng thông tin tới 16/02/2025, kể cả các bước tạo tham số.
- Báo cáo hồi cứu tách khỏi memo kế hoạch tại 16/02; không đưa kết quả tương lai vào memo tại ngày cắt.
- Không đánh dấu module hoàn thành trước khi kiểm tra đầu ra thực tế.
- Không đăng GitHub hay xuất bản khi chưa được yêu cầu.

- Notebook phải tự chứa và chạy được khi chỉ upload notebook lên Google Colab: cài thư viện, tạo thư mục, tải dữ liệu, phân tích và kiểm tra. Không đọc script/file trong repo làm điều kiện tiên quyết.
- Đặt tên file theo nội dung nghiệp vụ, không dùng m0/m1/m2.
- Không nhắc module hoặc G1/G2/G3 và trạng thái gate trong code/notebook. Tiêu chí chỉ nằm trong tài liệu kế hoạch nội bộ.

- Ưu tiên SQL cơ bản, chia thành bước ngắn; dùng CASE WHEN và tên cột trong GROUP BY. Giải thích đặt trong Markdown notebook thay vì comment dài trong code. Giữ nguyên quy tắc xử lý và kiểm tra kết quả khi đơn giản hóa.
