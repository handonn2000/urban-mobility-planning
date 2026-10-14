# Mục tiêu, chiến lược và mô hình báo cáo

## Quyết định người đọc cần hiểu

Trong 30 giây, người quản lý cần biết volume biến động ở nhóm nào, quan sát quanh phí/credit nói được gì và kế hoạch 17-23/02 dùng giả định nào. Hai trang giữ cùng định nghĩa chuyến hoàn thành và tách ba loại thông tin: quan sát, kịch bản kinh tế, kế hoạch đã chốt tại cutoff. Tính đúng grain/mẫu số quan trọng hơn thêm visual.

Trang theo dõi có bốn KPI, trend bốn phân khúc, weekday × hour city-wide và watchlist có bước điều tra. Trang quyết định có fee gap theo nhóm chuyến, share Lyft, forecast/actual hồi cứu và bảng điểm. Đề xuất thử nghiệm phải đọc cùng giả định margin/redemption và quy tắc quyết định trong brief.

## Schema và grain

| Bảng | Grain | Bộ lọc có ý nghĩa |
|---|---|---|
| DimDate | 425 ngày liên tục, 01/01/2024-28/02/2025 | Ngày/thứ/lễ; HasTripSource phân biệt ngày không có nguồn |
| DimSegment | 4 khóa hãng × nhãn endpoint | Segment/operator/zone |
| DimMethod | B1/B2/B3 | Một method mỗi phép chấm điểm |
| DimHour | 24 giờ | Heatmap city-wide |
| DimZone | 2 nhãn endpoint | Nối một chiều tới segment và weekly share |
| DimFeeOperator, DimTripGroup | All/Uber/Lyft; all/short/low fare | Chỉ kết quả phí có cửa sổ cố định |
| FactDaily | Ngày × segment, 360 dòng | Date, segment |
| FactCityHourly | Giờ toàn thành phố, 2.160 dòng | Date/hour; không có segment/zone key |
| FactAlerts | Ngày × segment có alert, 118 dòng | Date, segment; đếm dòng không phải ngày duy nhất |
| FactPlan | 28 ô ngày × segment, B1/B2/B3 | Date, segment; không chứa actual |
| FactForecast | 84 ô = 28 × 3 method | Date, segment, method; actual lặp theo method |
| FactWeeklyShare | 14 dòng full week × zone | Date=week start, zone; không dùng tuần biên thiếu ngày |
| FactFeeEffect | 9 kết quả operator × trip group | Cửa sổ so tháng 01 cố định; không có date/segment relationship |
| FactWeatherFactors | Study × weather group, 14 dòng | Nghiên cứu weather cố định; không date/segment relationship |
| FactCreditSummary | Một dòng proxy/kịch bản mặc định | Cửa sổ credit cố định; không date/segment relationship |

Chỉ quan hệ one-to-many, single direction từ dimension tới fact. Không nối fact-to-fact; không bật both-direction. DimZone→DimSegment→FactDaily và DimZone→FactWeeklyShare là hai grain phù hợp. Không nối DimSegment/DimZone tới city weather hoặc weather coefficients.

## Measure và mẫu số

`powerbi/measures.dax` chứa 27 định nghĩa; `model.bim` nhúng chúng vào table tương ứng. Đây là DAX source draft, chưa chạy engine Power BI.

- Trips là tổng FactDaily[Trips]. Cùng thứ năm trước dùng ngày đang chọn −364; xóa toàn bộ date context trước khi áp ngày dịch chuyển. Nếu thiếu bất cứ ngày reference nào, kết quả unavailable. Không thay bằng năm lịch hoặc điền 0.
- Lyft share giữ cả Uber + Lyft trên vùng đang chọn. Slicer hãng không được biến thị phần thành 0%/100%; measure lấy zones trước khi xóa filter segment/operator.
- Average base fare dùng BaseFareSum / ValidEconomicsTrips trên cùng paired sample. Không chia cho toàn bộ chuyến hoặc valid-fare sample khác.
- Daily median wait chỉ hiện khi đúng một ngày và một segment. Không cộng hoặc lấy trung bình các median rồi gọi pooled median.
- City average hourly trips là trung bình volume giờ được chọn. Weekday/hour matrix phản ánh toàn thành phố và chỉ nhận date/hour context. Hệ số mưa mùa hè là sample riêng, không đổi theo date/operator slicer.
- Fee gap dùng SELECTEDVALUE theo một operator/trip group; không SUM tỷ lệ hoặc cộng short/low fare. Default operator là All. Đó là relative gap so counterfactual, không phải giảm tổng thị trường.
- Forecast WAPE = SUM absolute errors / SUM actual cho một method; MAE chia số ô. Khi không chọn đúng một method, measure trả blank. Actual tổng được lấy một lần từ B2, không cộng ba bản actual lặp theo method. Các measure B1/B2/B3 dùng filter method cố định cho line chart.
- Credit cost $25,88 là kịch bản từ uplift proxy, margin $6, redemption=100%, coverage=100%, extra-credit fraction=100%; không đo ROI thật.

## Filter và bố cục

Trang 1 mặc định 06-26/01/2025, mọi segment. KPI: 14.097.953 chuyến; D-364 +1,974%; Lyft share 24,929%; 45 alert rows. Heatmap dùng volume giờ trung bình của cùng cửa sổ, bất biến theo segment slicer. Cards weather ghi sample Jun-Aug 2024 và 35 heavy-rain hours; không diễn giải là weather impact của cửa sổ January đang chọn.

Trang 2 không có date slicer chung: fee, credit, full-week share và forecast có cửa sổ khác nhau. Fee operator slicer chỉ tác động kết quả fee. Forecast chart chỉ 17-23/02; bảng điểm là hồi cứu. Planned B2 card là plan chốt ở 16/02, không đổi theo lựa chọn winner sau test.

PBIR source chứa hai trang/19 visuals. Heatmap matrix đã có đúng trục và measure; conditional color scale và tương tác cần xác nhận/hoàn thiện native. Preview PNG là render cục bộ, không xác nhận visual native đã hoạt động.

## Nguồn, bảo mật và refresh

CSV trong `powerbi/data` là aggregate công khai; keys/types/row counts nằm trong data_contract.json. Power Query nhúng CSV UTF-8 bằng Base64, giữ null và type rõ ràng. Không có đường dẫn máy, tài khoản, credential hoặc kết nối cloud trong model. Đây là snapshot; Refresh nạp lại snapshot nhúng. Muốn cập nhật, chạy phân tích và builder lại.

Không thiết lập RLS cho dữ liệu aggregate công khai; không thay đổi quyền hoặc phát hành. JSON schema/field reference/embedded bytes đã kiểm tra cục bộ. Chưa xác nhận TMSL load, Power Query, DAX, slicer hoặc renderer native.

Tài liệu Microsoft: [PBIR](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report), [semantic model source](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset). PowerShell wizard của plugin không có runtime tại máy này; design pack được chuẩn bị trực tiếp từ source contract, không ghi là đã chạy wizard hoặc native review.
