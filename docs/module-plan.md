# Kế hoạch thực hiện và tiêu chí hoàn thành

Giữ phạm vi và thứ tự M0-M6 của deck. Tổng ngân sách tham chiếu 35 giờ, gồm 32 giờ cho M0-M6 và 3 giờ kiểm tra/đóng gói. Đây là ngân sách dự kiến, không phải thời gian đã thực hiện. Từng module được đánh giá bằng đầu ra thật, không bằng số giờ.

## M0 - Môi trường và dữ liệu (3 giờ)

**Cách làm:** tạo môi trường Python riêng và khóa phiên bản thư viện; tải 3 file HVFHV Parquet từ TLC cùng bảng zone; gọi Open-Meteo Historical Weather API cho Central Park, tọa độ 40.7812/-73.9665, múi giờ America/New_York, theo đúng 3 tháng; xuất lịch lễ Mỹ năm 2024-2025 bằng holidays. Ghi URL, thời điểm tải UTC, kích thước và SHA-256. Dùng DuckDB đọc metadata và quét phí theo ngày; không làm sạch ở bước này.

**Đầu ra:** `.venv/`, `requirements.txt`, 3 file raw, `taxi_zone_lookup.csv`, `weather_hourly.csv`, `holidays.csv`, `source_manifest.json`, `trip_file_inventory.csv`, `congestion_fee_by_request_date.csv`, `trip_data_schema.json`, `urban_mobility_demand_analysis.ipynb` tự chứa và báo cáo dữ liệu.

**G1:** nhập được mọi thư viện; đọc đủ 3 file, mỗi file có dòng; các cột cần dùng có mặt (phí thiếu ở 2024 được ghi rõ); bảng zone có khóa duy nhất; thời tiết đúng 2.160 giờ, không trùng khóa và không thiếu; lịch lễ có 15/01/2024, 20/01/2025, 17/02/2025; không có phí dương ở chuyến kết thúc hoàn toàn trước 05/01/2025 và có phí sau mốc. Báo cáo riêng số chuyến đặt/đón trước mốc nhưng kết thúc sau mốc; không coi chuyến qua nửa đêm là lỗi chỉ vì ngày đặt. Mọi kiểm tra có kết quả lưu được. G1 chỉ xác nhận đầu vào, không thay audit M1.

## M1 - Audit, nhãn vùng và tổng hợp (6 giờ)

**Cách làm:** rà ngày/giờ ngoài tháng, mã zone lạ, hãng, chờ âm hoặc >60 phút, cước <=0; đếm riêng lỗi và viết quyết định giữ/gắn cờ/loại. Đếm theo tháng file và theo request_datetime để thấy chuyến qua ranh giới tháng. Giữ chuyến hợp lệ cho đếm, dùng mẫu hợp lệ riêng cho giá/chờ; không loại cả chuyến chỉ vì một metric không hợp lệ nếu chưa có lý do. Dùng 05-31/01/2025 suy ra zone tại ngưỡng 95%; gắn nhãn PU hoặc DO thuộc vùng cho cả 3 tháng. Chuyến ngắn <2 dặm; ngưỡng giá thấp lấy từ 01/2024. Gộp bằng SQL, lấp lưới 90 ngày × 4 phân khúc và 90 ngày × 24 giờ; nối thời tiết/lễ sau tổng hợp.

**Đầu ra:** `crz_zones.csv`, `daily_segment.csv`, `hourly_city.csv`, `trip_data_quality.md`, `trip_quality_audit.csv`, `trip_exclusion_summary.csv`, SQL và bảng reconciliation. Bảng ngày có chuyến, chuyến ngắn/giá thấp, tổng cước/driver pay, mẫu hợp lệ và median chờ. Bảng giờ phải có median chờ và số quan sát hợp lệ để M2 sử dụng.

**G2:** 360 dòng ngày, 2.160 dòng giờ; khóa duy nhất; tổng chuyến ngày = giờ = tập sạch; đối chiếu tổng cước/driver pay trên cùng mẫu; audit có số dòng và lý do; tỷ lệ phí theo nhãn được báo cáo. Phân biệt ô không có chuyến với dữ liệu nguồn bị thiếu; chỉ điền 0 khi có cơ sở.

## M2 - Thời tiết và watchlist (4 giờ)

**Cách làm (đã điều chỉnh theo đồng ý của người dùng):** rà thời tiết cả năm 2024 trước khi xem kết quả chuyến; chọn cửa sổ liên tục ba tháng có >=20 giờ mưa >2 mm/h sau khi bỏ lễ, ưu tiên nhiều đợt độc lập rồi số giờ. Chọn 06-08/2024; dữ liệu bổ sung chỉ cho phần mưa. Phân loại giờ theo deck, quy định rõ ranh giới và ưu tiên tuyết; khô = không mưa/không tuyết, nhẹ = 0,5-2 mm, vừa+ = >2 mm, mưa nhỏ >0 và <0,5 mm không dùng. Dựng trung vị khô cùng năm/tháng/thứ/giờ, bỏ lễ cả mẫu khô và mẫu thời tiết. Báo cáo mưa 06-08/2024 riêng, tuyết giữ trong mẫu mùa đông; không chuyển trực tiếp hệ số mùa hè vào tháng 02. Tính tỷ số chuyến và chờ; tổng hợp median theo loại thời tiết, ghi số giờ/ngày/đợt, đánh dấu <20 giờ. Watchlist so với trung bình cùng thứ của 2 tuần trước, fallback cùng thứ năm trước khi có dữ liệu; thiếu cả hai thì ghi không đủ baseline. Cảnh báo ±7% chuyến hoặc ±20% chờ, điều tra theo lỗi/lễ/thời tiết/giá.

**Đầu ra:** `rain_factors.csv`, `watchlist.csv`, biểu đồ và ghi chú giải thích.

**G3:** tính tay một hệ số khớp; mỗi hệ số có mẫu và baseline; nhóm ít mẫu được đánh dấu; mọi cảnh báo được giải thích hoặc ghi bước tiếp. Mục tiêu điều tra 2 cảnh báo nếu dữ liệu có, không tạo cảnh báo giả. Không suy ra số tài xế từ thời gian chờ. Hệ số là liên hệ quan sát, không phải nhân quả.

## M3 - Ước tính phí (5 giờ)

**Cách làm:** so 06-26/01/2025 với 08-28/01/2024; tính tăng trưởng nhóm trong/ngoài nhãn vùng và ratio-of-ratios; quy ra chuyến phản thực. Lặp cho chuyến ngắn/giá thấp và hãng; kiểm tra 90%/95%/99%, bỏ tuần mưa nhiều nhất. Độ nhạy giá là ước tính theo mức giá đại diện, có mẫu số rõ. Đối chiếu nghiên cứu theo phạm vi và mẫu số, không ép kết quả khớp.

**Đầu ra:** `fee_effect.csv`, `fee_sensitivity.csv`, biểu đồ, đoạn so nghiên cứu và giả định đối chứng.

**G4:** một ô tính tay khớp; cửa sổ/nhãn/mẫu số tái lập; sensitivity có đủ lựa chọn. Nếu đổi chiều, kết luận không vững và báo cáo như vậy, không coi đó là lỗi để sửa số. Nêu nhóm ngoài vùng có thể gồm chuyến đi xuyên vùng và spillover.

## M4 - Khuyến mãi và hòa vốn (5 giờ)

**Cách làm:** tính thị phần Lyft theo tuần, hai nhóm; giữ so sánh 06-26/01 và 03-23/02 theo deck. Tính chênh lệch thị phần, quy đổi uplift gần đúng dưới giả định quy mô thị trường cố định; kèm volume Uber/Lyft/tổng. Ghi credit phát tới 31/01 và có hiệu lực 7 ngày, khiến đầu tháng 02 có carryover và đối chứng ngoài vùng có thể bị ảnh hưởng. Excel dùng c=$1,50, m giả định và tỷ lệ trợ giá s; thêm kịch bản tỷ lệ sử dụng credit. Brief thử nghiệm khách đủ điều kiện, 10% holdout, ít nhất 14 ngày; ghi rõ mẫu số uplift.

**Đầu ra:** `lyft_share_weekly.csv`, `lyft_credit_breakeven.xlsx`, campaign brief Markdown và PDF một trang; phần phân tích nhúng trong notebook tự chứa.

**G5:** phép tính thị phần và kịch bản 100 chuyến khớp tay; giả định m/credit được ghi rõ, không gọi ROI thật. Ngưỡng 10% chỉ áp khi uplift tính trên toàn bộ chuyến nền và s=30% theo mô hình deck; nếu uplift tính riêng nhóm đủ điều kiện thì dùng ngưỡng tương ứng. Không dùng TLC để tuyên bố đã biết khách dùng credit hoặc retention.

## M5 - Dự báo 17-23/02/2025 (4 giờ)

**Cách làm:** chốt cutoff 16/02; B1=D-7, B2=trung bình D-7/D-14, B3=B2×hệ số MLK riêng 17/02 (20/01 chia trung bình 13 và 27/01). Lưu dự báo trước khi ghép actual. Tính MAE, WAPE, bias tuần/ngày lễ/phân khúc. Ba cách được so hồi cứu; winner trên test không được mô tả như lựa chọn đã biết tại cutoff. Thời tiết dùng làm kịch bản vận hành tham khảo, không đưa thời tiết thực tế tương lai vào baseline.

**Đầu ra:** `forecast_week.csv` (28 dòng, cột B1/B2/B3), bảng điểm, biểu đồ, mô tả cutoff.

**G6:** đủ 28 khóa; mọi tham số/nguồn cho forecast <=cutoff; một dự báo và các metric khớp tay; WAPE tổng tính từ tổng lỗi/tổng actual. Không bắt B3 phải thắng. Tách kết quả backtest khỏi memo tại 16/02.

## M6 - Báo cáo và đóng gói (5 giờ)

**Cách làm:** Power BI nhập CSV, dim_date liên tục, quan hệ một chiều và dimension phân khúc; measure chuyến, cùng thứ năm trước -364 ngày, share, WAPE. Tạo 2 trang theo mockup. Fact thời tiết toàn thành phố không nhận slicer hãng/vùng nếu không có grain tương ứng. Làm memo tiếng Anh 1 trang, demo 3 phút, README có 8 mục và nhật ký AI. Tách memo kế hoạch tại cutoff và báo cáo hồi cứu.

**Đầu ra:** `mobility.pbix`, 2 ảnh báo cáo, memo, README, hướng dẫn demo.

**G7:** số liệu dashboard khớp CSV ở 1 ngày/phân khúc và tổng; filter đúng grain; không còn số giả lập hoặc placeholder; notebook chạy lại từ đầu; memo phân biệt bằng chứng/giả thuyết; repo không chứa raw/.venv. Power BI Desktop cần Windows theo kế hoạch; trên Mac chuẩn bị dữ liệu/measure/spec trước, trạng thái PBIX chỉ hoàn thành khi thực sự dựng và kiểm tra trên Windows. Không tự đăng GitHub.
