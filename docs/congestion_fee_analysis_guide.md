# So sánh chênh lệch quanh phí vùng trung tâm

## Cửa sổ và mẫu

- Kỳ tham chiếu: 08-28/01/2024; kỳ so: 06-26/01/2025. Mỗi kỳ 21 ngày, cùng số từng thứ, một ngày lễ MLK.
- Chỉ dùng tập clean_trips đã tạo trong notebook. Không đưa dữ liệu mùa hè vào phép tính.
- Nhãn vùng từ tỷ lệ phí theo điểm đón: chính 95%, thử 90%/99%. PU hoặc DO thuộc danh sách thì chạm vùng. Nhóm ngoài vùng là đối chứng giả định.
- All/Uber/Lyft; cả chuyến, ngắn 0<dặm<2, giá thấp theo cước dương <=$11,63 cố định từ 01/2024. Nhóm ngắn/giá thấp có thể chồng lấn.

## SQL và Python

SQL gồm ba bước ngắn: chọn cửa sổ, gắn nhãn bằng CASE/LEFT JOIN, đếm theo ngày/hãng/nhãn vùng. COUNT/SUM và GROUP BY ghi tên cột. Python chỉ nhận bảng nhỏ để tính tỷ số và sensitivity. Các hàm nằm trực tiếp trong notebook; không đọc file script/SQL để chạy.

## Phép tính

A=chuyến chạm vùng 2024; B=chạm vùng 2025; C=ngoài vùng 2024; D=ngoài vùng 2025.

- Tăng trưởng chạm vùng=B/A−1; ngoài vùng=D/C−1.
- Phản thực chạm vùng=A×D/C.
- Chênh lệch tương đối=B/(A×D/C)−1.
- Chênh lệch chuyến=B−A×D/C.
- Hiệu tăng trưởng theo điểm phần trăm là 100×[(B/A−1)−(D/C−1)], không bằng chênh lệch tương đối.

All/all_trips: A=4.969.745; B=4.748.865; C=8.855.277; D=9.349.088. Phản thực=5.246.880,85; chênh lệch=−9,4917%, tương đương −498.015,85 chuyến dưới giả định này.

Tổng chuyến thực tế B+D vẫn tăng khoảng 1,97% so A+C. −9,49% không phải toàn thị trường giảm; nó là nhóm chạm vùng so với nhịp tăng đối chứng.

## Độ vững

Ba ngưỡng × hai cửa sổ × ba hãng × ba nhóm =54 dòng sensitivity. Bỏ cặp tuần có tổng rain_mm hai năm lớn nhất, chọn không dùng kết quả chuyến. Hiện bỏ 08-14/01/2024 và 06-12/01/2025, mỗi kỳ còn 14 ngày và một ngày MLK. So sánh vẫn khớp thứ. Không chỉ bỏ tuần ở một năm. Khoảng min/max sensitivity không phải khoảng tin cậy thống kê.

Các ngưỡng 90% và 95% chọn cùng danh sách zone trong dữ liệu này; chúng không phải hai nguồn bằng chứng độc lập. Cùng chiều ở cả sáu lựa chọn không xác nhận parallel trends hay loại hết nhiễu.

## Độ nhạy giá và mẫu số

Cước đại diện lấy bình quân cước dương của đúng nhóm chạm vùng kỳ 2024. Giả định tỷ lệ tăng giá=$1,50/cước đại diện. naive_elasticity_proxy=chênh lệch tương đối/tỷ lệ tăng giả định; chỉ để minh họa công thức, không phải elasticity được nhận diện. Chưa có giá tổng thực trả, mix/giá động có thể đổi, Lyft cấp credit cho tương lai, đối chứng có thể bị ảnh hưởng.

scaled_total_gap chia chênh lệch chuyến cho tổng mẫu phản thực (chạm vùng phản thực + ngoài vùng thực tế), của chính nhóm/hãng trong dòng đó. All/all_trips khoảng −3,41%; không tương đương trực tiếp với tác động nhân quả tổng thị trường trong nghiên cứu. Giá thấp phân nhóm theo cước mỗi kỳ, không theo cùng khách/tuyến; đổi giá cũng làm chuyến rời nhóm.

## Đầu ra

- fee_effect.csv: 9 kết quả chính.
- fee_sensitivity.csv: 54 lựa chọn.
- fee_robustness_summary.csv: chiều và khoảng thay đổi.
- fee_daily_counts_by_zone_rule.csv: bảng đếm và mẫu giá dùng để chạy lại phép tính.
- fee_comparison_dates.csv / fee_comparison_week_weather.csv: ngày, lễ, thời tiết và tuần bỏ.
- fee_effect_spot_check.csv: bốn số đầu vào và phép tính tay.
- fee_raw_count_verification.csv: kiểm tra bốn ô volume trực tiếp từ Parquet độc lập.
- reports/congestion_fee_comparison.png: biểu đồ chênh lệch, không phải tác động đã chứng minh.

Báo cáo: docs/congestion_fee_report.md. Chạy notebook Run all hoặc `.venv/bin/python scripts/analyze_congestion_fee.py` sau chuẩn bị/làm sạch nguồn.

## Cách trình bày

Nói nhóm chạm vùng tăng chậm hơn/nhanh hơn đối chứng trong kỳ so. Giữ cùng con số thật dù khác ví dụ/nội dung nghiên cứu. Chưa kết luận phí làm mất X% chuyến, Lyft credit có ROI tốt hoặc có thể tăng giá theo proxy. Nhóm ngoài vùng có chuyến xuyên vùng chịu phí; cạnh tranh, thay đổi hành vi và thời tiết làm giả định đối chứng chưa chắc đúng.
