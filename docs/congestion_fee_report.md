# Phí vùng trung tâm và chênh lệch tăng trưởng

## Phạm vi và phương pháp

So 08-28/01/2024 với 06-26/01/2025: 21 ngày, cùng thứ, mỗi kỳ có một ngày MLK. Nhãn chạm vùng dùng endpoint; đối chứng là không chạm vùng. Ngưỡng chính 95%, kiểm tra 90%/99%. Mưa mùa hè không tham gia phép tính này.
Counterfactual = chuyến trong vùng 2024 × (chuyến ngoài vùng 2025 / chuyến ngoài vùng 2024). Chênh lệch tương đối = chuyến trong vùng 2025 / counterfactual - 1. Đây là ratio-of-ratios, không phải hiệu hai tỷ lệ tăng trưởng tính bằng điểm phần trăm.

## Kết quả chính

| Hãng | Nhóm chuyến | Tăng trưởng chạm vùng | Tăng trưởng ngoài vùng | Chênh lệch tương đối | Chênh lệch chuyến phản thực |
|---|---|---:|---:|---:|---:|
| All | all_trips | -4.44% | +5.58% | -9.49% | -498,016 |
| All | short_trips | -5.33% | +7.09% | -11.59% | -202,790 |
| All | low_fare_trips | -18.68% | +6.85% | -23.89% | -160,192 |
| Uber | all_trips | -7.76% | +10.21% | -16.31% | -675,416 |
| Uber | short_trips | -10.55% | +12.94% | -20.80% | -300,139 |
| Uber | low_fare_trips | -33.39% | +14.23% | -41.69% | -225,399 |
| Lyft | all_trips | +5.84% | -6.90% | +13.69% | +154,411 |
| Lyft | short_trips | +13.42% | -7.06% | +22.04% | +72,921 |
| Lyft | low_fare_trips | +26.49% | -11.95% | +43.67% | +59,266 |

## Tính tay một dòng

Tổng chuyến thực tế trong mẫu tăng +1.97% so với cùng kỳ. Chênh lệch -9.49% dưới đây áp cho nhóm chạm vùng so với nhịp tăng của đối chứng, không phải toàn thị trường giảm từng đó.
Chạm vùng: 4,969,745 → 4,748,865; ngoài vùng: 8,855,277 → 9,349,088.
Nếu nhóm chạm vùng tăng cùng nhịp đối chứng: 4,969,745 × 9,349,088 / 8,855,277 = 5,246,880.85 chuyến.
Thực tế / phản thực - 1 = -0.094917, tức -9.49%. Chênh lệch -498,015.85 chuyến chỉ là ước tính dưới giả định đối chứng, không phải số chuyến mất đã quan sát trực tiếp.

## Độ vững

| Hãng | Nhóm | Khoảng chênh lệch qua 6 lựa chọn | Cùng chiều? |
|---|---|---|---|
| All | all_trips | -9.49% đến -9.26% | True |
| All | short_trips | -11.65% đến -11.49% | True |
| All | low_fare_trips | -24.21% đến -23.89% | True |
| Uber | all_trips | -16.31% đến -16.00% | True |
| Uber | short_trips | -20.80% đến -20.67% | True |
| Uber | low_fare_trips | -41.89% đến -40.95% | True |
| Lyft | all_trips | +13.67% đến +14.44% | True |
| Lyft | short_trips | +21.67% đến +22.91% | True |
| Lyft | low_fare_trips | +41.98% đến +43.67% | True |

Bỏ cặp tuần có tổng lượng mưa hai năm lớn nhất, cùng bảy thứ ở hai kỳ. Không chỉ bỏ tuần ở một năm. Các phương án đều giữ số ngày lễ bằng nhau trong dữ liệu hiện tại. Khoảng sensitivity không phải khoảng tin cậy thống kê.

- 2024: bỏ 08/01–14/01, mưa 63.2 mm, tuyết 0.00 cm.
- 2025: bỏ 06/01–12/01, mưa 0.0 mm, tuyết 2.66 cm.

## Độ nhạy giá: chỉ minh họa

Lấy cước cơ bản trung bình dương của nhóm chạm vùng trong kỳ 2024, giả định giá tăng $1,50/cước đó, rồi chia chênh lệch tương đối cho tỷ lệ tăng giá. naive_elasticity_proxy được xuất để hiểu phép tính, không coi là độ nhạy giá nhân quả: cước không gồm mọi phí/thuế, giá động và mix chuyến thay đổi, Lyft có credit tương lai, đối chứng có thể bị ảnh hưởng.
Nhóm giá thấp là nhóm theo ngưỡng cước cố định trong mỗi kỳ, không phải cùng khách hoặc cùng tuyến; cước tăng cũng làm chuyến chuyển ra khỏi nhóm. Chuyến ngắn và giá thấp có thể chồng lấn, không cộng các tác động nhóm.

## Đối chiếu nghiên cứu

Tóm tắt của Zhang, Sang & Wu (2026) trên Transportation Research Part A báo cáo giảm tổng ride-hailing khoảng 0,5–1,5%, Uber giảm tới 6% và Lyft tăng 2–5% trong kỳ credit; phản ứng tập trung ở chuyến ngắn/giá thấp. Họ dùng thiết kế two-way fixed effects. Nguồn: [tạp chí](https://www.sciencedirect.com/science/article/pii/S0965856426001072), DOI 10.1016/j.tra.2026.104966.
Demo này chỉ đối chiếu tóm tắt công bố, không tái lập mô hình của nghiên cứu. Có điểm tương đồng về hướng khác nhau giữa hai hãng và nhóm giá thấp nhạy hơn, nhưng độ lớn khác rõ. Nhóm chạm vùng và mẫu số của ratio-of-ratios không đồng nhất với tổng ride-hailing nghiên cứu. scaled_total_gap quy đổi sang tổng mẫu phản thực dưới chính giả định demo, vẫn không phải ước lượng tương đương của nghiên cứu.
Dòng All/all_trips sau quy đổi theo tổng mẫu phản thực là -3.41%; vẫn khác khoảng công bố và không thể coi là so sánh cùng thiết kế.

## Giới hạn và cách diễn giải

- Cùng chiều qua sensitivity không xác nhận parallel trends. Dữ liệu trước sự kiện ngắn và cách so cùng kỳ không kiểm soát hết thay đổi giữa hai năm.
- Nhóm ngoài vùng có chuyến xuyên vùng chịu phí; dòng kiểm tra fee_label_diagnostics.csv đã cho thấy sai khác nhãn. Đối chứng còn có thể chịu tác động chuyển hãng/chuyển điểm đón.
- Kỳ so có mưa/tuyết khác nhau; chỉ bỏ một cặp tuần chưa kiểm soát đầy đủ thời tiết.
- Lyft credit xảy ra cùng lúc; gộp hai hãng phản ánh nhiều thay đổi, tách Uber vẫn chưa loại cạnh tranh/chuyển hãng.
- Chỉ đo chuyến hoàn thành của tập giữ lại, không đo mọi yêu cầu đặt xe hay booking bị hủy.
- Cách viết phù hợp: nhóm chạm vùng tăng trưởng thấp hơn/cao hơn đối chứng X% trong cửa sổ này. Không viết phí chắc chắn làm mất X% chuyến hoặc dùng proxy elasticity để quyết định tăng giá.
