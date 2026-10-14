# Lyft credit: thị phần và kinh tế theo kịch bản

## So sánh quan sát

06-26/01/2025 so với 03-23/02/2025: cùng ba tuần, cùng thứ và một lễ thứ Hai. Credit phát trong 05-31/01 và dùng cho chuyến tương lai/Citi Bike trong tuần kế tiếp; giai đoạn đầu tháng 02 có thể còn credit. Ngoài vùng cũng có thể hưởng credit.

| Kỳ | Nhãn vùng | Lyft | Uber | Thị phần Lyft |
|---|---|---:|---:|---:|
| credit_issuance | False | 2,232,319 | 7,116,769 | 23.88% |
| credit_issuance | True | 1,282,171 | 3,466,694 | 27.00% |
| post_issuance | False | 2,365,453 | 7,244,232 | 24.62% |
| post_issuance | True | 1,296,909 | 3,666,442 | 26.13% |

Chênh lệch của thay đổi thị phần = +1.608 điểm phần trăm. Quy đổi xấp xỉ theo deck, chia cho thị phần Lyft trong vùng giai đoạn sau: 6.15%.
Nếu giữ quy mô thị trường tháng 01 cố định và điều chỉnh mức share phản thực bằng thay đổi ngoài vùng, proxy là 76,349 chuyến, uplift trên chính mẫu phản thực 6.33%. Hai tỷ lệ khác mẫu số; không coi là hai ước lượng nhân quả độc lập.
Từ kỳ January sang February, volume trong vùng: Lyft +1.15%, Uber +5.76%, tổng +4.52%. Lyft không giảm volume tuyệt đối dù share giảm; chưa kết luận toàn bộ chênh lệch là lấy chuyến từ Uber hay tạo nhu cầu mới.

## Bỏ tuần đầu tháng 02

- planned_three_weeks: +1.608 pp; uplift xấp xỉ 6.15%; 21 ngày kỳ credit so 21 ngày kỳ sau.
- exclude_first_february_week: +1.339 pp; uplift xấp xỉ 5.08%; 21 ngày kỳ credit so 14 ngày kỳ sau.

Phép kiểm tra 10-23/02 giảm lo ngại carryover nhưng có hai tuần so ba tuần, khác thành phần thứ/lễ; chỉ là độ vững tham khảo, không dùng volume thô để suy ra tăng giảm nhân quả.

## Mô hình kinh tế

N: chuyến nền; u: uplift trên toàn bộ N; s: phần chuyến nền nhận credit; a: phần chuyến tăng thêm nhận credit; c: mệnh giá; r: tỷ lệ sử dụng; m: contribution margin giả định mỗi chuyến tăng thêm.
Credit cost=N×(s+a×u)×c×r. Contribution thêm=N×u×m. Chênh lệch=N×[u×(m−a×c×r)−s×c×r]. Hòa vốn toàn mẫu u*=s×c×r/(m−a×c×r), nếu mẫu số dương. Hòa vốn riêng nhóm đủ điều kiện=u*/s khi incrementals nằm trong nhóm đó.
Mặc định N=100, c=$1,50, m=$6 (giả định), r=100%, s=100%, a=100%, u=6.15%: cost/extra trip=$25.88; net contribution=$-122.31/100 chuyến nền. Đây không phải ROI thực tế.
m=$6 không lấy trực tiếp từ cước trừ driver pay. TLC không có đủ chi phí nền tảng. Credit cost là mệnh giá kỳ vọng được dùng, chưa có redemption/cost thực tế và chưa tính lợi ích tương lai hay Citi Bike.

## Hai ví dụ cần tự giải thích

100 chuyến nền, u=3%, hoàn toàn bộ và dùng hết: 103 credit ×$1,50=$154,50; 3 chuyến thêm đem $18 contribution; cost/extra=$51,50. Hòa vốn=33,33%.
Chỉ trợ giá 30% chuyến nền, r=100%, a=100%: hòa vốn=10% toàn mẫu, tương đương 33,33% trên nhóm đủ điều kiện. Không dùng ngưỡng 10% cho KPI uplift đo riêng nhóm eligible. Đổi targeting phải ước tính lại uplift, không giả định đáp ứng giữ nguyên.

## Sản phẩm và giới hạn

Excel riêng có nguồn counts, công thức thị phần, input chỉnh được và sensitivity hòa vốn. Notebook tự chứa các phép tính và xuất CSV/JSON; không cần Excel hay builder để chạy trên Colab.
Không có customer ID, credit redemption, retention hoặc lợi nhuận đóng góp trong dữ liệu công khai. Khác mùa/thời tiết, cạnh tranh và nhóm đối chứng hưởng credit làm giả định DiD chưa được kiểm chứng. Kết quả dùng để thiết kế thử nghiệm, không phê duyệt chi phí chiến dịch thật.
Nguồn credit: [Lyft](https://www.lyft.com/blog/posts/navigating-the-new-nyc-congestion-fee-with-lyft). Nguồn volume: daily_segment.csv từ NYC TLC, quy tắc trong trip_data_quality.md.
