# Bổ sung theo cách Grab đo marketplace

Năm phần bổ sung, chọn theo những gì Grab nêu trong báo cáo quý 2/2026, tin tuyển dụng Demand Planning (GrabFood, GIP Việt Nam) và các bài Inside Grab/Grab Tech về dự báo, cảnh báo và thử nghiệm. Tất cả số dưới đây chạy trên dữ liệu thật bằng `scripts/analyze_marketplace_extensions.py` hoặc phần tương ứng trong notebook. Phạm vi dữ liệu không đổi: 01/2024, 01/2025, 02/2025.

## 1. Kiểm tra trước ngày có phí: −9,49% không tách được tác động của phí

**Cách làm.** Ghép từng ngày 02–29/01/2025 với cùng thứ năm 2024 (D−364). Mỗi ngày tính chênh lệch tương đối giữa trong và ngoài vùng: (chạm vùng 2025 ÷ chạm vùng 2024) ÷ (ngoài vùng 2025 ÷ ngoài vùng 2024) − 1. Ba ngày 02–04/01/2025 là trước khi có phí. Khoảng tin cậy lấy bằng bootstrap: rút lại 21 cặp ngày của cửa sổ chính 5.000 lần, cả rút tự do lẫn rút trong từng thứ.

**Kết quả.**

| Hãng | Trước phí 02–04/01 | Cửa sổ 06–26/01 | Bootstrap 95% (theo ngày) |
|---|---:|---:|---:|
| Tất cả | −13,85% | −9,49% | −10,9% đến −8,0% |
| Uber | −21,57% | −16,31% | −17,6% đến −15,0% |
| Lyft | +12,23% | +13,69% | +11,4% đến +16,0% |

Đếm lại trực tiếp từ raw (không qua `daily_segment`) cho đúng −13,85% và −9,49%.

**Cách đọc.** Chênh lệch đã âm, thậm chí âm hơn, ngay trước khi có phí. Đường theo ngày không gãy xuống ở 05/01 (`reports/fee_pre_period_check.png`). Vì vậy so sánh hiện tại cho thấy một khác biệt mức giữa trong và ngoài vùng từ 2024 sang 2025, nhưng **không tách được phần do phí**. Bootstrap chỉ đo dao động giữa các ngày, không bao phủ sai lệch do xu hướng trước đó.

**Giới hạn của kiểm tra.** Chỉ có ba ngày trước phí. 02–03/01/2025 là thứ Năm, thứ Sáu ngay sau Tết dương lịch (rơi vào thứ Tư), trong khi 04–05/01/2024 là tuần làm việc bình thường. Ngày sạch nhất là thứ Bảy 04/01/2025 so với 06/01/2024: −12,65%, vẫn tương đương mức sau phí. Muốn ước tính sạch cần thêm dữ liệu 11–12/2024 và 11–12/2023 để đo xu hướng trước phí; việc này mở rộng phạm vi nên cần người dùng đồng ý.

**Nhãn vùng lẫn vào nhóm đối chứng.** Trong 06–26/01/2025, 4,7% chuyến Lyft và 5,4% chuyến Uber bị thu phí nằm ở nhóm "ngoài vùng" theo nhãn 38 zone (đi xuyên vùng hoặc zone dưới ngưỡng 95%). Nhóm đối chứng vì thế có 2,7–2,8% chuyến chịu phí (`fee_label_coverage.csv`).

## 2. Cây metric: tăng trưởng đến từ số chuyến hay từ giá

**Cách làm.** Với mỗi cửa sổ 21 ngày và mỗi phân khúc: giá TB = tổng cước ÷ chuyến hợp lệ kinh tế; GMV proxy = chuyến × giá TB; tiền tài xế mỗi chuyến; tỷ lệ nền tảng giữ lại ước tính = 1 − tiền tài xế ÷ cước. Thay đổi GMV được tách bằng log: ln(GMV) = ln(chuyến) + ln(giá TB), nên hai phần cộng đúng bằng tổng. Cước `base_passenger_fare` không gồm phí vùng, thuế, tip; đây không phải GMV kế toán.

**Kết quả toàn thị trường.**

| So sánh | Chuyến | Giá TB | GMV proxy | Phần do số chuyến |
|---|---:|---:|---:|---:|
| 01/2024 → 01/2025 | +1,97% | +0,73% | +2,72% | 73% |
| 01/2025 → 02/2025 | +3,37% | +3,01% | +6,48% | 53% |

**Theo phân khúc, 01/2024 → 01/2025:** Uber chạm vùng −7,8% chuyến nhưng giá TB +9,2% (từ $29,55 lên $32,26, chưa gồm phí). Lyft chạm vùng +5,8% chuyến nhưng giá TB −5,8%. Tỷ lệ giữ lại ước tính của Uber chạm vùng tăng 3,8 điểm % (29,1% → 32,9%), của Lyft giảm 1,5 điểm.

**Cách đọc.** Chuyển dịch giữa hai hãng trong vùng đi kèm thay đổi giá rõ: Uber đắt lên, Lyft rẻ đi. Đây là một giải thích cạnh tranh cho cả "tác động phí" của Uber (−16%) lẫn thị phần Lyft tăng, cần nêu khi trình bày. Đây là quan hệ quan sát, chưa phải nhân quả. Biểu đồ: `reports/gmv_volume_price_decomposition.png`.

## 3. Chi phí credit so với GMV

Đếm trên raw: 1.315.183 chuyến Lyft bị thu phí trong 06–26/01/2025, và 1.661.878 chuyến trong cả đợt phát 05–31/01. Nếu mọi credit đều được dùng, chi phí là $1,97 triệu cho cửa sổ so sánh, tức 5,9% GMV proxy của Lyft chạm vùng và 2,5% toàn bộ GMV proxy của Lyft. Với tỷ lệ sử dụng 25%, các tỷ lệ này là 1,5% và 0,6%.

Để tham chiếu, Grab công bố chi phí khuyến mãi bằng 10,9% GMV On-Demand trong quý 2/2026. Phạm vi khác hẳn (mọi khuyến mãi, mọi dịch vụ), nên chỉ dùng để đặt độ lớn vào cùng một thước đo, không so trực tiếp. Tỷ lệ sử dụng credit thật không có trong TLC.

## 4. Cảnh báo theo dự báo thay cho ngưỡng ±7%

**Vì sao đổi.** Kỳ vọng của watchlist cũ là trung bình hai ngày cùng thứ trước đó. Sai số "bình thường" của kỳ vọng này (độ lệch chuẩn robust = 1,4826 × MAD của log thực tế/kỳ vọng, trên 45 ngày không có sự kiện) là 4,8–6,5% cho mỗi phân khúc mỗi ngày. Ngưỡng ±7% chỉ bằng 1,05–1,42 lần mức đó, nên khoảng 1/3 số ngày bị báo động dù không có gì bất thường.

**Quy tắc mới**, gần với cách Grab dùng dự báo để phát cảnh báo:
- Kỳ vọng là trung bình hai ngày cùng thứ gần nhất, không phải ngày lễ, không thuộc 01–07/01, trong vòng 35 ngày.
- Nếu chỉ có một ngày tham chiếu, dải nới thêm √(4/3).
- Cảnh báo khi lệch quá 2,5 độ lệch chuẩn robust, và tối thiểu 3%.
- Ngày lễ và giai đoạn chuyển phí được gắn nhãn "sự kiện đã biết".
- Mỗi cảnh báo kèm thời tiết của ngày đó và các ngày tham chiếu.

**Kết quả.** Từ 118 cảnh báo xuống còn 9 ngày-phân khúc lệch khỏi dải: 2 là ngày lễ MLK 2024, 5 có thời tiết xấu ở ngày tham chiếu, 2 chưa giải thích được (15/01/2025 Lyft ngoài vùng, z = −3,4; 28/02/2025 Uber chạm vùng, z = −2,65). Ở mức toàn thành phố chỉ có một cảnh báo: 17/01/2024 cao hơn kỳ vọng 20%, vì ngày tham chiếu 10/01 có 4 giờ mưa.

| k | Tỷ lệ báo nhầm nếu phân phối chuẩn | Ngoài dải | Cần điều tra |
|---:|---:|---:|---:|
| 2,0 | 4,6% | 21 | 19 |
| 2,5 | 1,2% | 9 | 7 |
| 3,0 | 0,3% | 3 | 3 |

**Giới hạn.** Hiệu chỉnh dải trên chính dữ liệu quan sát (in-sample). 112 ngày-phân khúc, chủ yếu hai tuần đầu mỗi tháng 01, không có kỳ vọng vì thiếu dữ liệu tháng 12; khi vận hành thật cần lịch sử liên tục. Biểu đồ: `reports/forecast_band_alerts.png`.

## 5. Thiết kế thử nghiệm: cỡ mẫu, switchback, SRM

Chi tiết ở `docs/experiment_design_addendum.md`. Tóm tắt:
- **Holdout theo khách cho credit nhắm mục tiêu (giả định, vì TLC không có ID khách):** với 50.000 khách đủ điều kiện, chia 90/10, hệ số biến thiên số chuyến mỗi khách là 1,5, mức tác động nhỏ nhất phát hiện được là 6,3%. Với 200.000 khách là 3,1%, và còn 2,6% nếu CUPED giảm 30% phương sai. Holdout 10% đủ để phát hiện uplift 10% (ngưỡng hòa vốn toàn mẫu) ngay ở quy mô nhỏ.
- **Switchback theo giờ cho thưởng tài xế giờ mưa (dùng phương sai thật của `hourly_city` 2025):** tự tương quan giữa các giờ liền kề là 0,78, làm phương sai tăng khoảng 8 lần. Chạy 14 ngày trên mọi giờ phát hiện được thay đổi 4,0% số chuyến hoặc 6,9% thời gian chờ. Nếu chỉ áp vào giờ mưa (3,4% số giờ mùa đông 2025), 14 ngày chỉ có khoảng 11 khung giờ, mức phát hiện được là 22% số chuyến và 38% thời gian chờ; 56 ngày vẫn là 11% và 19%. Kết luận: thử nghiệm chỉ trong giờ mưa cần nhiều tuần, hoặc đổi sang chỉ số và đơn vị ít nhiễu hơn.
- **SRM:** kiểm định chi-bình-phương trên số khách mỗi nhóm so với tỷ lệ 90/10 đã định. Ví dụ 179.200/20.800 cho p = 2,5×10⁻⁹, tức đã chia lệch: dừng phân tích và tìm lỗi chia nhóm trước khi đọc kết quả.

## Kiểm tra

`docs/marketplace_extensions_validation.json`: cửa sổ ghép theo ngày cho đúng −9,4917% của `fee_effect.csv`; tổng phân khúc khớp tổng toàn thị trường; hai phần log cộng đúng tổng; bảng cảnh báo đủ 360 dòng. Raw đếm lại độc lập cho đúng chênh lệch trước phí (−13,85%), chênh lệch cửa sổ (−9,49%) và giá TB Uber chạm vùng ($32,26).

## Liên hệ Việt Nam (gợi ý thay slide 39)

Quý 2/2026, giá xăng tăng đẩy chi phí của tài xế lên. Grab chi hơn 7 triệu USD hỗ trợ thu nhập tài xế và tăng khuyến mãi ở Việt Nam, trong khi đẩy gói Saver làm giá trung bình mỗi chuyến giảm. Cấu trúc bài toán giống phí $1,50: một cú sốc chi phí tác động cùng lúc lên cung, cầu và tỷ lệ giữ lại. Cách tiếp cận trong dự án (tách số chuyến và giá, kiểm tra xu hướng trước sự kiện, khuyến mãi có holdout) áp dụng được trực tiếp, với dữ liệu nội bộ thay cho TLC.
