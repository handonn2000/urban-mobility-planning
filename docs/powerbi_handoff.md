# Bàn giao Power BI và bước Microsoft 365

## Đã có trên Mac

`powerbi/draft/UrbanMobility.pbip` là bản nguồn dự thảo: semantic model TMSL, Power Query snapshot nhúng, 27 measures, 16 quan hệ một chiều và hai trang PBIR/19 visuals. `powerbi/data` chứa CSV để đối chiếu. Hai PNG trong reports là preview local từ số thật; PDF memo có một trang.

`powerbi_source_validation.json` ghi 27 file hợp lệ theo 11 schema công khai Microsoft, field references và embedded bytes khớp nguồn. `reporting_pack_validation.json` đối chiếu grain/tổng/một ngày/phân khúc và mẫu số. Các kiểm tra đó không xác nhận native DAX, Power Query hoặc rendering.

## Phần còn cần môi trường Power BI phù hợp

1. Mở PBIP bằng Power BI Desktop hỗ trợ project/report format. Cần mở cả folder, giữ nguyên đường dẫn tương đối Report→SemanticModel. Bản nguồn có dữ liệu nhúng nên không cần tìm lại CSV tại đường dẫn Mac.
2. Refresh/apply model. Nếu phiên bản Desktop không hỗ trợ nguồn hoặc visual configuration, dùng CSV, measures.dax và report_visual_spec.json để dựng theo cùng contract; không đổi định nghĩa/mẫu số chỉ để visual chạy.
3. Xác nhận DimDate là date table, sort DayName theo Weekday, relationships single direction và không có đường từ segment/zone tới city weather.
4. Kiểm tra default 06-26/01/2025: Trips 14.097.953; prior 13.825.022; change +1,974181%; Lyft share 24,929080%; alert rows 45. Chọn 21/01/2025 + Lyft_zone: Trips 58.431. Đối chiếu tiền/chờ nếu thêm visual bằng đúng sample/grain.
5. Chọn Uber/zone rồi Lyft/zone: share vẫn dùng cả hai hãng trên selected zone; city heatmap/weather card giữ grain và không đổi theo segment. Thử chọn cả Jan2025: prior-year result unavailable vì thiếu reference 01-02/02/2024; không xuất tỷ lệ từ partial coverage.
6. Forecast từng method: WAPE B1 4,4497%, B2 3,4843%, B3 3,6129%. Total actual chỉ 4.820.140, không nhân ba. Kiểm tra cùng một ngày/segment với forecast_evaluation.csv; không trung bình WAPE nhóm.
7. Áp background color scale cho matrix City average hourly trips; kiểm tra slicer/filter interactions, các title/sample/assumptions, font và clipping. Capture hai trang từ Power BI thực tế sau khi đối chiếu.
8. Save As PBIX, rồi mở lại PBIX và kiểm tra model/report. Chỉ lúc đó mới ghi PBIX hoàn thành.

## Khi đưa lên Microsoft 365 / Power BI service

Người dùng dự định tải lên cloud sau; hiện chưa có thao tác publish. PBIP source draft không phải PBIX để upload. Sau khi có PBIX đã kiểm tra, chọn đúng Power BI workspace trong tenant Microsoft 365, kiểm tra quyền người xem và tính năng/license đang có trước khi import/publish. Không dùng Publish to web để thay cho chia sẻ nội bộ.

Mô hình này là embedded snapshot, không cần thông tin đăng nhập nguồn. Không có scheduled refresh hoặc gateway được cấu hình; Refresh không tự cập nhật TLC. Nếu muốn nguồn tự cập nhật, đó là thay đổi riêng cần thiết kế access/refresh và kiểm tra lại.

Hướng dẫn chính thức: [Power BI projects](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview), [report source](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report), [semantic model source](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset). Trạng thái bàn giao: Mac artifacts checked; native validation và PBIX pending.
