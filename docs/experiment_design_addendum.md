# Phụ lục thiết kế thử nghiệm

Bổ sung cho `targeted_credit_experiment_brief.md`. Brief giữ nguyên, phần này thêm cỡ mẫu, phương án switchback và kiểm tra chia nhóm.

## Công thức

Mức tác động tương đối nhỏ nhất phát hiện được (MDE), hai phía α = 5%, power 80%:

MDE ≈ (1,96 + 0,84) × σ × √(DE × (1/n_T + 1/n_C))

σ là độ lệch chuẩn của log chỉ số trên mỗi đơn vị (với khách: hệ số biến thiên số chuyến mỗi khách). DE là hệ số thiết kế. Với switchback, DE = (1+ρ)/(1−ρ), trong đó ρ là tự tương quan giữa hai khung liền kề; đây là xấp xỉ thận trọng. CUPED (dùng số chuyến trước thử nghiệm làm biến kiểm soát) nhân phương sai với (1 − R²).

## Holdout theo khách (credit nhắm nhóm nhạy giá)

TLC không có ID khách nên σ là giả định; trước khi chạy phải thay bằng phương sai thật 28 ngày trước thử nghiệm. Bảng đầy đủ: `data/processed/experiment_power_user_holdout.csv`.

| Khách đủ điều kiện | CV 1,5, không CUPED | CV 1,5, CUPED R²=0,3 | CV 2,5, không CUPED |
|---:|---:|---:|---:|
| 50.000 | 6,3% | 5,2% | 10,4% |
| 200.000 | 3,1% | 2,6% | 5,2% |
| 500.000 | 2,0% | 1,7% | 3,3% |

Ngưỡng hòa vốn trong brief là 33,3% uplift trên nhóm đủ điều kiện (tương đương 10% toàn mẫu khi s = 30%). Cả hai đều lớn hơn MDE ở mọi quy mô trên, nên rủi ro chính không phải thiếu mẫu mà là uplift thật thấp hơn hòa vốn.

## Switchback theo khung giờ (thưởng tài xế giờ mưa)

Khi can thiệp tác động lên cả thị trường (thưởng tài xế, giá), chia khách không còn độc lập. Switchback bật/tắt can thiệp theo khung thời gian ngẫu nhiên, như công cụ thử nghiệm của Grab hỗ trợ. σ và ρ lấy từ `hourly_city` 2025, sau khi trừ trung vị cùng tháng × thứ × giờ, bỏ ngày lễ. Bảng: `data/processed/experiment_power_switchback.csv`.

| Chỉ số | Khung | ρ | 14 ngày, mọi giờ | 14 ngày, chỉ giờ mưa | 56 ngày, chỉ giờ mưa |
|---|---|---:|---:|---:|---:|
| Số chuyến | 1 giờ | 0,78 | 4,0% | 22% | 11% |
| Thời gian chờ trung vị | 1 giờ | 0,79 | 6,9% | 38% | 19% |
| Số chuyến | 2 giờ | 0,68 | 4,3% | 23% | 12% |

Khuyến nghị:
- Dùng khung 2 giờ trở lên và bỏ 15–30 phút đầu mỗi khung để giảm tác động tràn sang khung sau.
- Ngẫu nhiên hóa theo ngày × khung để cân bằng giờ cao điểm.
- Nếu chỉ thử trong giờ mưa, chạy theo mùa (nhiều tuần) hoặc gộp nhiều thành phố hay khu vực.
- Phân tích bằng hồi quy có hiệu ứng cố định theo giờ, sai số chuẩn cụm theo ngày.

## Kiểm tra lệch tỷ lệ chia nhóm (SRM)

Trước khi đọc kết quả, so số khách thực tế mỗi nhóm với tỷ lệ 90/10 đã định bằng kiểm định chi-bình-phương. Nếu p < 0,001 thì dừng phân tích và tìm lỗi chia nhóm. Ví dụ: 180.000/20.000 cho p = 1,0 (đạt); 179.200/20.800 cho p = 2,5×10⁻⁹ (lệch). Hàm `srm_check` có trong script và notebook.
