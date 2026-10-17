# Power BI project (PBIP)

`powerbi/UrbanMobility.pbip` là dự án Power BI dạng PBIP: semantic model viết bằng TMDL (`UrbanMobility.SemanticModel/definition/`) và báo cáo dạng PBIR (`UrbanMobility.Report/definition/`). Tạo lại bằng `scripts/build_powerbi_project.py` từ các bảng trong `data/processed`.

## Mở trên Windows

1. Cài Power BI Desktop bản mới (đã bật mặc định định dạng PBIP/TMDL/PBIR).
2. Mở `powerbi/UrbanMobility.pbip`; giữ nguyên cấu trúc thư mục vì báo cáo trỏ tới model bằng đường dẫn tương đối.
3. Bấm **Refresh**. Dữ liệu được nhúng sẵn trong Power Query (CSV mã hóa base64), không cần trỏ lại đường dẫn file. Bản CSV dễ đọc nằm trong `powerbi/data/`.
4. Muốn có file `.pbix` để nộp hoặc đưa lên Microsoft 365: **File → Save as → .pbix**.

## Model

Chỉ giữ những số có trên slide báo cáo (`UrbanMobility_Report.pdf`). 11 bảng, 6 quan hệ một chiều nhiều-một, 22 measure.

| Bảng | Grain | Dùng cho |
|---|---|---|
| DimDate | 1 ngày, 01/01/2024–28/02/2025, có tên ngày lễ | Trục thời gian |
| DimSegment, DimMethod | Hãng × vùng; B1/B2/B3 | Slicer, bảng sai số |
| FactDaily | Ngày × phân khúc | Tổng 59.407.013 chuyến |
| FactFeeWindow, FactFeeGap | 3 cột 2024 / dự kiến / thực tế; ngày 02–26/01/2025 | Bước 1: phí |
| FactLyftShare | Giai đoạn × vùng | Bước 2: thị phần Lyft |
| FactWeather, FactAlertList | Mưa nhẹ/to mùa hè 2024; 9 cảnh báo | Bước 3: mưa, cảnh báo và lý do |
| FactForecast | Ngày × phân khúc × phương án (84 dòng) | Bước 4: kế hoạch, thực tế, WAPE |
| FactKPI | 1 dòng | Chỉ số tóm tắt: −13,8%/−9,5%, +5,6%, 1,6 điểm, $25,88, 33%, +7,7%, 118 |

## Trang báo cáo

1. **Summary**: 8 thẻ (chuyến phân tích, chênh lệch trước phí, chi phí credit, mưa to, 118 vs 9 cảnh báo, kế hoạch B2, WAPE), kết quả (slide 4) và 3 đề xuất (slide 15).
2. **Fee and credit**: chuyến trong vùng 2024 / dự kiến / thực tế, chênh lệch theo ngày trước/sau 05/01, thị phần Lyft có/hết credit, thẻ 1,6 điểm, 6,15%, $25,88, 33%.
3. **Weather and alerts**: thay đổi chuyến và thời gian chờ khi mưa nhẹ/to, 118 vs 9 cảnh báo, lý do và bảng 9 cảnh báo kèm thời tiết ngày tham chiếu.
4. **Holiday-week plan**: thực tế vs kế hoạch B2 theo ngày (slicer phân khúc), bảng WAPE/bias của B1/B2/B3, bảng lệch theo ngày.

Đã bỏ so với bản trước (không có trên slide): phân rã GMV/giá trung bình/tỷ lệ giữ lại, nhóm chuyến ngắn/giá thấp, khoảng bootstrap, thị phần theo tuần, dải cảnh báo toàn thành phố, hệ số mưa mùa đông, MAE, chi phí credit/GMV, hòa vốn credit có chọn lọc, bộ lọc năm.

## Màu sắc

Theme riêng `UrbanMobility.Report/StaticResources/RegisteredResources/UrbanMobility.json`, cùng bảng màu với slide: nền trang be `#F4F1EA`, khung trắng bo góc, tiêu đề trang nền navy `#1B2430` chữ trắng, thẻ số chữ teal có vạch nhấn bên trái, tiêu đề cột bảng nền navy.

Màu cố định theo ý nghĩa (tham chiếu màu theme, không mã hex cứng): trước phí, có credit, chưa giải thích = cam `#D2632A`; có phí, sau credit, mưa/tuyết = teal `#0F7B6C`; mức dự kiến, kế hoạch B2 = teal nhạt `#7FC4B5`; năm 2024, ngày lễ, thời gian chờ = xám; thực tế = navy. Biểu đồ cột có nhãn số. Đổi màu toàn báo cáo: sửa `THEME` trong builder rồi chạy lại.

## Đã kiểm tra (không có Power BI Desktop) — bản rút gọn 17/10/2026

- 14 file TMDL đọc được bằng `@pbip-tools/tmdl-parser` 0.2.1, không cảnh báo.
- `pbiplint` 0.2.5: 0 lỗi. Cảnh báo còn lại có chủ ý: cột tỷ lệ dùng số thực (fixed decimal làm -0,138477 thành -13,9%), measure tỷ lệ dùng định dạng có dấu +/−, điểm % có 1 chữ số thập phân, và báo nhầm khóa ngoại theo tên cột.
- Tên measure không trùng tên cột hay measure khác (script dừng nếu trùng).
- 51 tham chiếu trường trên visual và mọi tham chiếu DAX đều tồn tại; 38 visual nằm trong khung 1280×720, không chồng nhau.
- Tính lại từ dữ liệu nhúng: 59.407.013 chuyến; 4,97 / 5,25 / 4,75 triệu chuyến trong vùng; thị phần Lyft 27,0→26,1% và 23,9→24,6%; 9 cảnh báo = 2 lễ + 5 thời tiết ngày tham chiếu + 2 chưa giải thích; kế hoạch B2 4.871.468, thực tế 4.820.140; WAPE B1/B2/B3 4,45% / 3,48% / 3,61%; lệch theo ngày +0,2 / −1,7 / +1,3 / +1,0 / +2,5 / −0,4 / +4,5%.
- 48 file PBIP/PBIR hợp lệ theo schema Microsoft (report 3.2.0, page 2.1.0, visualContainer 2.8.0 và các schema con); theme hợp lệ theo `reportThemeSchema-2.159.json`. Schema để trống kiểu của nhiều thuộc tính định dạng, nên tên thuộc tính màu được đối chiếu thêm với danh sách thuộc tính trong schema theme.

Bản in PDF từ Power BI Desktop (14/10/2026) đã mở được cả 4 trang. Các sửa sau đó: thẻ số chuyến hiển thị số đầy đủ (trước là 59M, 5M), thẻ khoảng tin cậy rộng hơn để không bị cắt chữ, bỏ dòng Total trong bảng WAPE, bảng cảnh báo hiện đủ 9 dòng, tiêu đề trang không còn thanh cuộn.

Chưa kiểm tra được sau bản rút gọn: Power Query refresh, kết quả DAX và hiển thị visual trong Power BI Desktop. Nếu Desktop báo lỗi khi mở, ghi lại thông báo và sửa trong script dựng, không sửa tay file sinh ra.
