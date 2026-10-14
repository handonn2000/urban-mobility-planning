# Cách phân tích credit Lyft và hòa vốn

## Phạm vi và đầu vào

Dùng `daily_segment.csv` do phần làm sạch trong notebook tạo ra. Thị phần chỉ tính trên chuyến hoàn thành Uber + Lyft, không phải toàn bộ thị trường vận tải. Nhãn chạm vùng dựa trên endpoint; không nhận biết đầy đủ chuyến xuyên vùng. Không đọc raw bằng pandas.

Phân tích hồi cứu so 06-26/01/2025 với 03-23/02/2025: mỗi kỳ ba tuần, đủ bảy thứ và một lễ thứ Hai. Credit phát 05-31/01, có hiệu lực một tuần cho chuyến tương lai hoặc Citi Bike. Ngoài vùng có thể nhận lợi ích; đầu tháng 02 có thể có carryover. Kết quả tới 23/02 không được đưa vào memo giả lập tại 16/02.

## Thị phần và uplift quy đổi

1. Gộp volume theo tuần × nhãn vùng × hãng. Thị phần Lyft = Lyft / (Uber + Lyft). Hai tuần biên chỉ có năm ngày được đánh dấu `full_week=False`; không coi là tuần đầy đủ khi diễn giải biểu đồ.
2. Đối chiếu đủ khóa ngày × hãng × nhãn vùng trước khi tổng hợp hai cửa sổ. Tính share từ tổng chuyến mỗi kỳ, không lấy trung bình share ngày hoặc tuần.
3. Chênh lệch share = (trong vùng tháng 01 - tháng 02) - (ngoài vùng tháng 01 - tháng 02), đổi sang điểm phần trăm bằng nhân 100.
4. Uplift xấp xỉ = chênh lệch share / share trong vùng tháng 02. Đây là quy đổi theo thiết kế tham chiếu, không phải uplift đo từ thử nghiệm.
5. Một proxy khác giữ quy mô thị trường tháng 01 cố định: share phản thực = share trong vùng tháng 02 + share ngoài vùng tháng 01 - share ngoài vùng tháng 02. Extra-trip proxy = chênh lệch share × tổng chuyến trong vùng tháng 01; uplift chia cho chuyến Lyft phản thực. Không cộng hoặc trộn hai uplift khác mẫu số.
6. Xem volume Lyft/Uber/tổng cùng lúc. Share giảm không chứng minh volume giảm; chuyển hãng và nhu cầu mới chưa thể phân biệt chắc chắn bằng so sánh này.

Sensitivity bỏ 03-09/02 để giảm carryover, nhưng còn 14 ngày so 21 ngày và thành phần lễ khác. Chỉ dùng để đọc độ vững tham khảo. Không khẳng định causal DiD hoặc ROI thực tế.

## Kinh tế theo kịch bản

| Biến | Ý nghĩa |
|---|---|
| N | Chuyến nền, mặc định chuẩn hóa 100 |
| u | Uplift trên toàn bộ N |
| s | Phần chuyến nền nhận credit, không phải phần người dùng |
| a | Phần chuyến tăng thêm nhận credit |
| c | Mệnh giá credit $1,50 |
| r | Tỷ lệ sử dụng credit, chưa có trong TLC |
| m | Contribution margin mỗi chuyến tăng thêm, mặc định $6 giả định |

Chi phí kỳ vọng = N × (s + a × u) × c × r. Contribution thêm = N × u × m. Net contribution là hiệu hai khoản này. Chi phí/chuyến thêm chia chi phí cho N × u; khi u=0 giữ unavailable.

Hòa vốn toàn mẫu = s × c × r / (m - a × c × r), nếu mẫu số dương. Hòa vốn trên chuyến nền eligible chia tiếp cho s, nếu toàn bộ incrementals thuộc population eligible. Mẫu số không dương được báo không có hòa vốn, ngoại trừ trường hợp chi phí và margin đều bằng 0.

Tỷ lệ chuyến nền eligible không tự xác định tỷ lệ người dùng eligible. Khi dùng KPI chuyến/khách trong thử nghiệm, cần cùng population, thời gian và baseline exposure để liên hệ với mô hình kinh tế; nên quyết định bằng net contribution/người được phân nhóm.

24 kịch bản kết hợp m=$3/$6/$9, r=25%/50%/75%/100%, s=100%/30%. Giữ uplift quan sát để minh họa cơ học chi phí; targeting thật phải ước tính lại uplift. Cước trừ driver pay chỉ là proxy, không dùng làm contribution margin thật.

## Đầu ra và cách chạy

- `lyft_share_weekly.csv`: volume, share và coverage tuần.
- `lyft_credit_period_comparison.csv`: volume/share hai cửa sổ.
- `lyft_credit_share_sensitivity.csv`: cửa sổ chính và bỏ tuần đầu tháng 02.
- `credit_breakeven_scenarios.csv`, `credit_economics_hand_examples.csv`: kịch bản và ví dụ tính tay.
- `lyft_credit_analysis.json`, `lyft_credit_validation.json`: số liệu và kết quả đối chiếu.
- `reports/lyft_share_weekly.png`, `docs/lyft_credit_report.md`: biểu đồ và diễn giải.
- `docs/targeted_credit_experiment_brief.md`: brief do notebook tạo; bản trình bày một trang ở `reports/targeted_credit_experiment_brief.pdf`.
- `excel/lyft_credit_breakeven.xlsx`: workbook trình bày riêng, có input chỉnh được và công thức. Không cần workbook để chạy notebook.

Upload **chỉ notebook** lên Colab và chọn Run all: notebook cài thư viện, tạo thư mục, tải nguồn, tổng hợp và chạy các phép tính trên. CSV đầu vào cho credit được tạo trong cùng lần chạy. Notebook tạo báo cáo/brief Markdown và các bảng; không yêu cầu Excel hoặc bộ tạo PDF.

CLI sau khi đã tạo bảng ngày: `.venv/bin/python scripts/analyze_lyft_credit.py`.

## Kiểm tra kết quả

Kiểm tra share tuần từ tổng chuyến ngày, coverage đầy đủ hai kỳ, chênh lệch/uplift tính từ counts, 24 chi phí kịch bản và ví dụ 100 chuyến. Với u=3%, s=a=r=100%, c=$1,50, m=$6: 103 credit, chi phí $154,50, $51,50/chuyến tăng thêm, hòa vốn 33,33%. Với s=30%, u=10% toàn mẫu: net contribution bằng 0 và ngưỡng eligible 33,33%.

Kiểm tra riêng redemption=0, uplift=0 và margin không đủ. Hồ sơ notebook ghi điều kiện chạy thật và phân biệt Jupyter độc lập với dịch vụ Colab; không khẳng định đã kiểm thử Colab nếu chưa truy cập runtime đó.
