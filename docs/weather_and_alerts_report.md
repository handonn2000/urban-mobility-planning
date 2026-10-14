# Thời tiết và theo dõi biến động

## Chọn khoảng dữ liệu

Rà 8,784 giờ thời tiết 2024 trước khi phân tích chuyến. Cửa sổ 2024-06-01 đến 2024-08-31 có 35 giờ mưa >2 mm/giờ thuộc 14 đợt ẩm liên tục sau khi bỏ ngày lễ. Chọn theo số đợt, không theo kết quả chuyến.
Dữ liệu bổ sung chỉ cho mưa: 58,430,874 chuyến, 2,208 giờ. Phí/credit/dự báo và watchlist giữ phạm vi ban đầu.

## Cách tính

Ưu tiên tuyết khi snowfall>0. Khô: rain=0 và không tuyết; mưa nhỏ 0<rain<0,5 bỏ khỏi hệ số; nhẹ 0,5-2; vừa trở lên >2. Mỗi giờ chia cho trung vị giờ khô cùng tháng/năm/thứ/giờ, bỏ lễ ở cả mẫu khô và mẫu thời tiết. Hệ số nhóm là median các tỷ số giờ.

## Hệ số quan sát

| Mẫu | Thời tiết | Giờ dùng | Ngày | Đợt | Chuyến | Chờ |
|---|---|---:|---:|---:|---:|---:|
| summer_2024 | light_rain | 110 | 32 | 36 | 1.031 | 1.003 |
| summer_2024 | moderate_or_heavy_rain | 35 | 13 | 14 | 1.077 | 1.009 |
| winter_2024 | light_rain | 37 | 9 | 7 | 1.101 | 1.057 |
| winter_2024 | moderate_or_heavy_rain | 15 | 4 | 3 | 1.029 | 1.066 |
| winter_2024 | snow | 50 | 5 | 5 | 1.090 | 1.035 |
| winter_2025 | light_rain | 38 | 9 | 7 | 1.012 | 1.045 |
| winter_2025 | moderate_or_heavy_rain | 4 | 2 | 2 | 1.056 | 1.012 |
| winter_2025 | snow | 94 | 15 | 13 | 1.027 | 1.078 |

Nhóm dưới 20 giờ được đánh dấu ít mẫu trong rain_factors.csv. Số giờ không phải số quan sát độc lập; xem cả số ngày/đợt. Dry reference ít giờ được lưu ở từng dòng, không giấu độ thưa.

## Theo dõi và điều tra

360 dòng ngày/phân khúc; 118 cảnh báo trên 58 ngày; 56 dòng thiếu baseline không được gán số 0 hoặc tạo cảnh báo.
Kỳ vọng là trung bình cùng thứ của D-7 và D-14. Thiếu cả bộ hai ngày thì dùng cùng thứ năm trước D-364 khi có; thiếu tiếp thì để NULL. Cảnh báo |lệch chuyến|>7% hoặc |lệch chờ|>20%. Baseline có lễ được ghi riêng.

### 2025-01-20 - Lyft, chạm vùng=False

Chuyến -7.7%; chờ +5.0%; cước không thuộc mẫu 0.0%; mưa 0 giờ, tuyết 2 giờ; lễ hiện tại=True, lễ trong baseline=False.

Có ngày lễ MLK nhưng biến động không đồng đều giữa hãng/nhãn vùng. Ngày lễ là bối cảnh, chưa đủ giải thích riêng sự giảm của Lyft ngoài vùng.

Bước tiếp: So cả bốn phân khúc và ngày lễ năm trước; kiểm tra thời tiết trước khi gán nguyên nhân.

### 2025-01-21 - Lyft, chạm vùng=True

Chuyến +9.9%; chờ +2.1%; cước không thuộc mẫu 10.3%; mưa 0 giờ, tuyết 1 giờ; lễ hiện tại=False, lễ trong baseline=False.

Chuyến tăng đồng thời nhiều cước không thuộc mẫu dương. Đã đối chiếu với raw; giữ volume, không dùng trung bình giá bị mất mẫu để suy ra hiệu quả credit.

Bước tiếp: Rà nguồn cước/chờ; giữ volume, không dùng giá thiếu mẫu để gán nguyên nhân.

## Giới hạn sử dụng

- Mưa mùa hè không dùng trực tiếp để điều chỉnh nhu cầu tháng 02. Tuyết được đọc riêng trong mẫu mùa đông.
- Hệ số là liên hệ quan sát với chuyến hoàn thành, không đo toàn bộ booking demand hoặc quan hệ nhân quả.
- Baseline có ít giờ khô, sự kiện đặc biệt và nhiệt độ có thể ảnh hưởng kết quả; chưa có mô hình kiểm soát đầy đủ.
- Chờ tăng không chứng minh tài xế ít đi. Không có số tài xế hoạt động.
- Weather factors dùng toàn bộ cửa sổ hồi cứu. Nếu dùng trong forecast, phải ước tính lại chỉ với dữ liệu có trước cutoff.
- Hai case đã rà với giới hạn; nguyên nhân cuối cùng chưa được chứng minh. Các cảnh báo khác đều có evidence và next_step, không tự ghi đã xử lý xong.
