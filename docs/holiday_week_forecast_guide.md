# Mục tiêu và chiến lược dự báo tuần có lễ

## Bài toán kinh doanh

Lập kế hoạch số chuyến hoàn thành theo ngày cho Uber/Lyft và nhãn chạm vùng/ngoài vùng trong 17-23/02/2025. Có 28 ô dự báo: bảy ngày × bốn phân khúc. Presidents' Day vào thứ Hai 17/02 là điểm cần đọc riêng. Đây là nhu cầu được phục vụ, không phải toàn bộ yêu cầu đặt xe hoặc số tài xế.

Mục tiêu kiểm chứng là so sánh cách điều chỉnh ngày lễ với các baseline đơn giản bằng số thật. Không đặt điều kiện phải chứng minh cách có hệ số lễ thắng; số minh họa trong deck không phải mục tiêu số liệu. Không thêm machine learning, không tối ưu tham số trên tuần test.

## Chốt lựa chọn trước khi xem test

- B1: cùng thứ tuần trước, trực tiếp và dễ giải thích.
- B2: trung bình hai tuần trước, giảm phụ thuộc một ngày bất thường; chọn trước làm baseline kế hoạch.
- B3: B2 × hệ số MLK chỉ riêng 17/02. Giữ làm kịch bản lễ vì một ngày MLK không đủ chứng minh hành vi ở Presidents' Day.

B2 được chọn bằng lập luận về tính đơn giản và việc chuyển hệ số giữa hai lễ khác nhau, không bằng điểm của tuần 17-23/02. Sau test, báo cáo phương án có WAPE toàn tuần thấp nhất riêng. Sự trùng hoặc khác nhau giữa lựa chọn kế hoạch và winner hồi cứu đều được giữ nguyên.

## Cutoff, dữ liệu và tham số

Ngày cắt là hết 16/02/2025, giờ New York; dùng điều kiện nhỏ hơn 00:00 ngày 17/02. Raw bất biến, chỉ đọc bằng DuckDB. Dựng history từ hai Parquet 01/2025 và 02/2025, giữ request trong 01/01-16/02 và chỉ giữ chuyến có dropoff trước cutoff. Chuyến đặt ngày 16/02 nhưng hoàn thành ngày 17/02 không thể được coi là chuyến hoàn thành đã biết ở cutoff.

History có 188 dòng ngày × hãng × nhãn vùng. So với bảng ngày hồi cứu đã có để giải thích phần hoàn thành sau cutoff hoặc thiếu dropoff. Không sửa bảng ngày cho các phân tích phí/credit. Coverage nguồn phải đủ; chỉ dùng zero cho ô không có chuyến đã hoàn thành khi nguồn đã được xác nhận, không biến nguồn thiếu thành zero.

Nhãn vùng dùng danh sách suy từ 05-31/01; giai đoạn này trước cutoff. Static lookup và record được giả định đã truy cập được trong mô phỏng. TLC công bố bộ dữ liệu theo tháng sau kỳ dữ liệu, nên quy trình này không chứng minh khả năng chạy realtime với nguồn công khai. Chưa mô hình hóa reporting delay hoặc cập nhật dữ liệu muộn.

Lịch lễ 17/02 được biết trước; không phải dữ liệu hành vi tương lai. Hệ số MLK riêng từng phân khúc = trips(20/01) / mean[trips(13/01), trips(27/01)]. B1/B2 dùng 03-09/02 và 10-16/02. Tất cả ngày quan sát tạo tham số <=16/02.

Không dùng uplift credit tính tới 23/02, hệ số mưa hồi cứu, thời tiết thực tế tương lai, fare threshold hoặc điểm backtest để tạo forecast. Thời tiết chỉ là contingency vận hành định tính; chưa có forecast thời tiết lưu tại cutoff để đưa vào mô hình. Không áp hệ số mưa mùa hè sang tháng 02.

## Lưu dự báo trước khi ghép actual

1. Dựng history và provenance, đối chiếu coverage/cutoff.
2. Tạo ba dự báo và lưu `forecast_week.csv`, hệ số, lineage ngày nguồn.
3. Viết `holiday_week_planning_memo.md`, chỉ dùng forecast và giả định đã biết; giữ lựa chọn B2 cố định.
4. Ghi SHA-256 forecast, rồi mới ghép actual vào `forecast_evaluation.csv`.
5. Tính điểm hồi cứu và kiểm tra forecast không thay đổi sau scoring. Giữ số dự báo dạng float; làm tròn chỉ trong bảng trình bày.

Forecast không có actual hoặc lỗi. Memo tại cutoff không có winner/WAPE của tuần test. Báo cáo hồi cứu được lưu riêng để tránh đọc kết quả tương lai như quyết định đã biết trong quá khứ.

## Chấm điểm và diễn giải

MAE = sum(abs(forecast-actual)) / số ô. WAPE = sum(abs(forecast-actual)) / sum(actual). Bias = sum(forecast-actual) / sum(actual). Bias dương là dự báo cao, âm là thấp. Tổng actual bằng zero thì WAPE/bias unavailable.

Bảng điểm có 45 dòng: ba cách × ba scope (toàn tuần, riêng 17/02, sáu ngày thường) × năm nhóm (toàn mẫu và bốn phân khúc). MAE toàn tuần là số chuyến lệch trung bình trên một ô ngày/phân khúc, không phải sai số của tổng thành phố/ngày. WAPE toàn mẫu tính lại từ 28 sai số và tổng actual; không lấy trung bình WAPE nhóm, không cho lỗi trái dấu triệt tiêu.

Chọn winner hồi cứu bằng WAPE toàn tuần thấp nhất; tie dùng thứ tự tên phương án. Đọc cả ngày lễ và phân khúc để tránh che giấu nhóm có sai số lớn. B2/B3 giống nhau ngoài 17/02 nên toàn bộ chênh lệch giữa hai cách do holiday adjustment. Một tuần test không xác nhận phương án tốt nhất cho mọi mùa hoặc mọi lễ.

## Kiểm tra và đầu ra

- 28 khóa duy nhất; đủ nguồn D-7/D-14 và ba ngày MLK; thiếu reference phải dừng.
- Max request/dropoff của history và các ngày tham số nằm trước cutoff; nhãn vùng không dùng kỳ sau cutoff.
- B3 bằng B2 ở sáu ngày thường; tính tay một dự báo và MAE/WAPE/bias trên số thật.
- Thử thêm volume rất lớn ở mọi ngày sau cutoff: forecast giữ nguyên; bỏ một ngày reference: báo lỗi.
- Hash forecast trước/sau ghép actual khớp; kiểm tra denominator zero không trả số phần trăm giả.

Các bảng: `forecast_history.csv`, `forecast_cutoff_reconciliation.csv`, `forecast_week.csv`, `forecast_holiday_factors.csv`, `forecast_source_dates.csv`, `forecast_evaluation.csv`, `forecast_scores.csv`, `forecast_spot_check.csv`. Hồ sơ: `forecast_input_provenance.json`, `holiday_week_forecast_summary.json`, `holiday_week_forecast_validation.json`. Biểu đồ: `reports/holiday_week_forecast.png`. Báo cáo: `holiday_week_forecast_report.md`; memo tại cutoff: `holiday_week_planning_memo.md`.

CLI sau khi có dữ liệu: `.venv/bin/python scripts/forecast_holiday_week.py`. Notebook nhúng toàn bộ SQL/hàm, cài thư viện, tải nguồn và tự tạo các đầu vào; chỉ upload notebook lên Colab rồi Run all, không cần script hoặc CSV ngoài. Không gọi là đã thử runtime Colab nếu chỉ kiểm thử Jupyter độc lập.
