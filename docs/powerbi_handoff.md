# Power BI project (PBIP)

`powerbi/UrbanMobility.pbip` là dự án Power BI dạng PBIP: semantic model viết bằng TMDL (`UrbanMobility.SemanticModel/definition/`) và báo cáo dạng PBIR (`UrbanMobility.Report/definition/`). Tạo lại bằng `scripts/build_powerbi_project.py` từ các bảng trong `data/processed`.

## Mở trên Windows

1. Cài Power BI Desktop bản mới (đã bật mặc định định dạng PBIP/TMDL/PBIR).
2. Mở `powerbi/UrbanMobility.pbip`; giữ nguyên cấu trúc thư mục vì báo cáo trỏ tới model bằng đường dẫn tương đối.
3. Bấm **Refresh**. Dữ liệu được nhúng sẵn trong Power Query (CSV mã hóa base64), không cần trỏ lại đường dẫn file. Bản CSV dễ đọc nằm trong `powerbi/data/`.
4. Muốn có file `.pbix` để nộp hoặc đưa lên Microsoft 365: **File → Save as → .pbix**.

## Model

13 bảng, 7 quan hệ một chiều nhiều-một, 42 measure.

| Bảng | Grain | Dùng cho |
|---|---|---|
| DimDate | 1 ngày, 01/01/2024–28/02/2025 (liên tục, đánh dấu date table) | Trục thời gian, so cùng thứ năm trước (-364 ngày) |
| DimSegment, DimMethod | Hãng × vùng; B1/B2/B3 | Slicer, chú giải |
| FactDaily | Ngày × phân khúc | Chuyến, giá trung bình, tỷ lệ giữ lại |
| FactCityForecast | Ngày, toàn thành phố | Thực tế, dự báo hai tuần, dải cảnh báo 2,5 SD |
| FactAlertList | 9 ngày-phân khúc ngoài dải | Bảng cảnh báo và lý do |
| FactFeeGap, FactFeeEffect | Ngày 02–29/01/2025; hãng × nhóm chuyến | Chênh lệch trong/ngoài vùng |
| FactGrowth, FactWeeklyShare | Phân khúc; tuần × vùng | Số chuyến vs giá; thị phần Lyft |
| FactForecast | Ngày × phân khúc × phương án (84 dòng) | Kế hoạch, backtest, WAPE |
| FactWeather, FactKPI | Nhóm thời tiết; 1 dòng | Hệ số mưa; chỉ số tóm tắt từ phân tích |

## Trang báo cáo

1. **Summary**: 8 thẻ KPI, phát hiện chính và đề xuất.
2. **Demand monitoring**: chuyến theo phân khúc, dự báo và dải cảnh báo toàn thành phố, bảng 9 cảnh báo, hệ số thời tiết (lọc năm 2025 trong filter pane).
3. **Fee and credit**: chênh lệch theo ngày trước/sau 05/01, theo nhóm chuyến, tăng trưởng số chuyến vs giá, thị phần Lyft theo tuần, chỉ số credit.
4. **Holiday-week plan**: kế hoạch B2 theo ngày, thực tế vs ba phương án, bảng WAPE/bias/MAE.

## Đã kiểm tra (không có Power BI Desktop)

- 16 file TMDL đọc được bằng `@pbip-tools/tmdl-parser`, không cảnh báo.
- 50 file JSON (PBIP/PBIR) hợp lệ theo schema chính thức của Microsoft; bộ kiểm tra bắt được lỗi cố ý.
- `pbiplint`: 0 lỗi; cảnh báo còn lại là định dạng % có chủ ý (WAPE 2 chữ số) và báo nhầm khóa ngoại theo tên cột.
- Tên measure không trùng tên cột hay measure nào trong model (script dừng nếu trùng). Lỗi Power BI Desktop 'The Trips measure cannot be created because a column with the same name already exists' đã sửa bằng cách đổi cột thành `TripCount`.
- 67 tham chiếu trường trên visual và mọi tham chiếu DAX đều tồn tại trong model; 40 visual nằm trong khung 1280×720, không chồng nhau.
- Dữ liệu nhúng trùng CSV; tính lại: 59.407.013 chuyến, kế hoạch B2 4.871.468, WAPE B2 3,48%, B3 3,61%, 9 cảnh báo.
- Script chạy lại trên máy khác cho file giống hệt.

Chưa kiểm tra được: Power Query refresh, kết quả DAX và hiển thị visual trong Power BI Desktop. Nếu Desktop báo lỗi khi mở, ghi lại thông báo và sửa trong script dựng, không sửa tay file sinh ra.
