# Trạng thái triển khai

| Module | Trạng thái | Bằng chứng |
|---|---|---|
| M0 | Hoàn thành | G1 PASS 18/18; notebook độc lập thực thi 10/10 cell trong môi trường mới, không lỗi; docs/source_data_report.md |
| M1 | Hoàn thành | 59.407.013 chuyến; 360 dòng ngày, 2.160 dòng giờ; đối chiếu đủ và notebook độc lập chạy lại |
| M2 | Hoàn thành | Rà 2024, bổ sung 06-08; rain_factors/watchlist; 2 case đã rà; notebook chạy lại không lỗi |
| M3 | Hoàn thành | 9 dòng chính, 54 sensitivity; đối chiếu raw/tính tay và notebook chạy lại |
| M4 | Hoàn thành | G5 đạt; 18 dòng share tuần, 24 kịch bản; Excel khớp tính tay; brief PDF một trang; notebook 46 cell không lỗi |
| M5 | Hoàn thành | G6 đạt; 28 dự báo, 45 dòng điểm; cutoff theo request/dropoff; notebook 56 cell không lỗi |
| M6 | Hoàn tất phần Mac; chờ Power BI native | 2 preview, memo PDF 1 trang, source PBIP, README/demo; G7 chưa hoàn tất vì chưa mở/kiểm tra/lưu PBIX |

Không dùng trạng thái này thay cho file kết quả kiểm tra từng gate.

## M0 - Hoàn thành 14/10/2026

- 3 file raw: 59.409.057 chuyến, khoảng 1,43 GB.
- Zone 265 dòng; thời tiết 2.160 giờ; lịch lễ 22 ngày.
- Manifest của 7 file tải có URL, thời điểm UTC, kích thước, SHA-256.
- G1 18/18; notebook độc lập chạy từ thư mục trống, 10 code cell không lỗi.
- Chuyến qua nửa đêm được kiểm tra bằng dropoff để không nhầm phí xuất hiện trước mốc.
- M1 tiếp theo: audit, gắn nhãn vùng, tạo 360/2.160 dòng và đối chiếu tập sạch. Chưa có kết quả M1-M6.

## Cập nhật notebook độc lập

- Chỉ copy notebook vào thư mục trống, kernel dùng venv mới không có các thư viện dữ liệu ban đầu.
- Notebook tự cài thư viện, tải lại cả 7 nguồn, xuất bảng dữ liệu/diagnostics và chạy đủ 10 code cell.
- Các bảng inventory/phí khớp đầu ra trước đó; SHA-256 của ba file Parquet khớp nguồn đã lưu.
- Chưa chạy trên dịch vụ Google Colab thực tế; kiểm thử tại máy bằng kernel Jupyter độc lập.
- Code/notebook không còn module hoặc gate; kế hoạch nội bộ giữ trong docs/module-plan.md.

## M1 - Hoàn thành 14/10/2026

- Audit 13 quy tắc, theo từng tháng; quyết định/lý do lưu trong trip_quality_audit.csv và trip_data_quality.md.
- Raw 59.409.057; loại 2.038 request ngoài phạm vi và 6 endpoint không xác định; giữ 59.407.013.
- 38 zone ở ngưỡng 95%; ngưỡng giá thấp cố định $11,63.
- 360 dòng ngày và 2.160 dòng giờ, khóa duy nhất; đầy đủ coverage quan sát; thời tiết/lễ nối không nhân bản.
- Tổng chuyến/số mẫu và hai tổng tiền đối chiếu với tập giữ lại, giữa ngày/giờ và từng ngày; sai khác tiền do floating point trong mức dưới 1 cent.
- Notebook tự chứa, 18 code cell chạy từ đầu không lỗi trong thư mục kiểm thử chỉ có cache raw; bảng khớp CLI. Không chạy trực tiếp dịch vụ Colab.
- Ngày 21/01/2025, Lyft có 13.927/165.825 chuyến không thuộc mẫu cước dương (8,40%). Chưa suy ra nguyên nhân; giữ đếm chuyến, ghi mức mất mẫu.
- G2 đạt; M2 tiếp theo là hệ số mưa và watchlist, chưa triển khai.

## Cập nhật SQL dễ đọc

- Chia chuẩn hóa/cờ hợp lệ/đếm phí/tỷ lệ zone thành bước ngắn.
- Dùng CASE WHEN và GROUP BY tên cột; chuyển giải thích sang Markdown.
- Notebook chạy lại 22 code cell không lỗi; 15 bảng CSV và tham số khớp trước refactor.

## M2 - Hoàn thành 14/10/2026

- Người dùng đồng ý mở rộng riêng phần mưa sau rà thời tiết; chọn 06-08/2024 trước khi xem kết quả chuyến, vì có 35 giờ >2mm/h trong 14 đợt không phải lễ.
- 58.430.874 chuyến bổ sung, 2.208 giờ; phạm vi chính không đổi (59.407.013 chuyến, 360/2.160 dòng).
- Hệ số so giờ khô cùng năm/tháng/thứ/giờ; bỏ lễ cả hai mẫu. Mưa nhẹ: chuyến 1,03068, chờ 1,00337 (110 giờ). Mưa >2: chuyến 1,07717, chờ 1,00917 (35 giờ).
- Tuyết/mùa đông giữ báo cáo riêng; nhóm mưa mạnh mùa đông dưới 20 giờ được gắn cờ. Không áp hệ số mùa hè vào tháng 02.
- Watchlist: 118 dòng trên 58 ngày; 56 dòng thiếu baseline được giữ NULL, không tạo cảnh báo.
- Rà 2 case (20/01 Lyft ngoài vùng; 21/01 Lyft chạm vùng), có evidence/finding/next_step và so cả 4 phân khúc. Trạng thái reviewed_with_limitations, không khẳng định root cause. Các case khác có bằng chứng và bước tiếp.
- Tính tay một giờ: 8.463/7.427=1,13949; baseline khớp median giờ khô độc lập.
- Notebook có 31 code cell chạy lại từ đầu không lỗi; hàm nhúng khớp CLI, không có nhãn module/gate hoặc comment trong code.
- G3 đạt; M3 (tác động phí) chưa bắt đầu.

## M3 - Hoàn thành 14/10/2026

- So 08-28/01/2024 và 06-26/01/2025, 21 ngày cùng thứ/một MLK; không đưa dữ liệu mùa hè vào phép tính.
- 9 dòng: All/Uber/Lyft × all/short/low fare; 54 sensitivity: 3 ngưỡng × 2 cửa sổ × 9 nhóm.
- Ngưỡng95: All/all_trips −9,4917%; Uber −16,3061%; Lyft +13,6918%. Các lựa chọn giữ cùng chiều; All/all_trips từ −9,4917% tới −9,2650%.
- Bỏ cặp tuần mưa nhiều nhất: 08-14/01/2024 và 06-12/01/2025; cả hai còn 14 ngày cùng thứ, một MLK.
- Đối chiếu bốn ô trực tiếp raw và tính tay counterfactual; ngưỡng95 khớp daily_segment đã có.
- Tổng chuyến thực tế vẫn tăng khoảng1,97%; gap−9,49% không phải mức giảm toàn thị trường.
- Proxy elasticity chỉ minh họa, có giả định/mẫu số và giới hạn; không gọi causal elasticity.
- Đối chiếu tóm tắt nghiên cứu Zhang/Sang/Wu(2026), không tái lập mô hình và không ép số khớp.
- Notebook 39 code cell chạy lại không lỗi; bốn đầu ra trước đó không thay đổi; PNG đã xem trực tiếp.
- G4 đạt; M4 (credit và hòa vốn) chưa bắt đầu.

## M4 - Hoàn thành 14/10/2026

- 18 dòng share tuần trong/ngoài vùng; hai tuần biên thiếu ngày được đánh dấu, counts/share đối chiếu bảng ngày. Hai cửa sổ 06-26/01 và 03-23/02 có 21 ngày và một lễ mỗi kỳ.
- Chênh lệch share +1,6077 pp; uplift quy đổi 6,1529%. Proxy thị trường cố định 76.349 chuyến, uplift 6,3317%; ghi rõ khác mẫu số và không phải tác động nhân quả/ROI thật.
- Volume trong vùng từ January sang February: Lyft +1,15%, Uber +5,76%, tổng +4,52%; không gọi share giảm là volume giảm.
- Sensitivity bỏ tuần đầu February: +1,339 pp, uplift 5,08%; nêu carryover và cửa sổ/holiday mix không hoàn toàn tương đương.
- 24 kịch bản m/redemption/coverage. Ví dụ 100 chuyến, u=3%: $154,50 credit cost, $51,50/chuyến thêm, hòa vốn 33,33%. Targeting s=30%: hòa vốn 10% toàn mẫu, tương đương 33,33% eligible. Không dùng fare-pay gap làm margin thật.
- `docs/lyft_credit_validation.json`: 12 kiểm tra hợp lệ; weekly counts/share, coverage, uplift, chi phí kịch bản và edge cases. `docs/credit_workbook_verification.json`: workbook đã recalculated bằng Artifact Tool; chưa chạy Excel native.
- Brief có đủ sáu mục, holdout ngẫu nhiên 10%, ít nhất 14 ngày + redemption follow-up, KPI bao gồm zero-trip users, quy tắc expand/stop hoặc redesign; PDF một trang đã kiểm tra nội dung và xem ảnh trực tiếp.
- Notebook nhúng toàn bộ bảy hàm credit, AST khớp CLI. Chạy 46/46 code cell trong kernel mới/thư mục độc lập chỉ có notebook và cache nguồn đã xác minh; không cung cấp script hay processed inputs. 36 CSV khớp baseline, không lỗi. Chưa chạy dịch vụ Colab thực tế; bootstrap tải/cài từ thư mục trống đã được kiểm tra ở lần trước.
- G5 đạt theo đầu ra thực tế. Tài liệu hướng dẫn/README/AI log được cập nhật; M5 chưa bắt đầu. Kết quả credit tới 23/02 là hồi cứu, không đưa vào memo tại cutoff 16/02.

## M5 - Hoàn thành 14/10/2026

- Mục tiêu: 28 ô dự báo 17-23/02/2025 cho bốn phân khúc; kiểm chứng ba baseline trên số thật, không bắt hệ số lễ phải thắng. Mục tiêu/chiến lược/cách tính nằm trong holiday_week_forecast_guide.md.
- Chọn B2 trước làm baseline kế hoạch vì trung bình hai tuần giảm phụ thuộc một ngày; B3 là kịch bản lễ chuyển từ MLK. Winner hồi cứu được lưu riêng; không viết lại memo theo test.
- History 188 dòng Jan-Feb tới 16/02, raw đọc DuckDB. Chỉ giữ request trước 17/02 và dropoff trước 17/02: loại 9.961 chuyến kết thúc sau cutoff, không có dòng thiếu completion time. Bảng ngày/raw không đổi. Zone calibrated 05-31/01; không dùng weather factors, future weather hoặc uplift credit.
- 28 dòng forecast_week.csv với B1/B2/B3, khóa duy nhất, ngày D-7/D-14 và hệ số đã áp; bốn hệ số MLK, 68 dòng lineage nguồn. Forecast/memo được lưu trước actual join, hash trước/sau scoring khớp.
- 45 dòng điểm: ba cách × week/holiday/ordinary_days × toàn mẫu/bốn phân khúc. WAPE tổng từ 28 absolute errors/tổng actual, không trung bình WAPE nhóm. B1 4,4497%, B2 3,4843%, B3 3,6129%; winner hồi cứu B2. Riêng lễ: B1 3,5980%, B2 1,4120%, B3 2,4617%.
- B3 không thắng B2 toàn mẫu; Uber chạm vùng có cải thiện nhẹ, các nhóm khác xấu hơn. Không ép kết quả theo ví dụ trong deck hoặc coi một tuần là bằng chứng tổng quát.
- holiday_week_forecast_validation.json: 15/15 kiểm tra; một forecast và MAE/WAPE/bias khớp tay; thay volume tương lai không đổi forecast; thiếu reference bị từ chối. Năm counts tham số của một phân khúc đã đối chiếu trực tiếp raw độc lập, lưu forecast_raw_reference_verification.csv.
- Memo tại cutoff: holiday_week_planning_memo.md; báo cáo hồi cứu: holiday_week_forecast_report.md; biểu đồ 4 phân khúc đã xem PNG trực tiếp. Weather là contingency định tính, không thêm dữ liệu sau cutoff vào mô hình.
- Notebook tự chứa thêm toàn bộ chín hàm forecast và SQL, AST khớp CLI. 56/56 code cell chạy từ đầu trong thư mục/kernel mới chỉ có notebook và verified source cache; không script/processed inputs, không lỗi. 44 CSV khớp baseline; chưa truy cập Google Colab thực tế.
- Giới hạn availability được ghi rõ: mô phỏng giả định record/lookup đã có tại cutoff; TLC monthly release là hồi cứu, chưa mô hình hóa reporting delay và không khẳng định nguồn công khai là realtime feed.
- G6 đạt theo đầu ra thực tế. M6 chưa bắt đầu; chưa có PBIX/dashboard hoặc bản memo portfolio cuối.

## M6 - Đóng gói trên Mac 14/10/2026; native Power BI pending

- Người dùng xác nhận chỉ dùng Mac, dự định đưa PBIX lên Microsoft 365 sau. Không đăng nhập/publish cloud, không ghi draft PBIP là PBIX hoặc PNG local là screenshot native.
- Mục tiêu/chiến lược trong report_model_guide.md: người quản lý hiểu biến động January và kế hoạch holiday week trong 30 giây; tách observation/scenario/cutoff plan và ưu tiên grain/mẫu số.
- 16 bảng Power BI input, DimDate 425 ngày liên tục, bốn segment, ba method và 16 quan hệ một chiều; không có segment/zone relationship tới city weather. FactForecast 84 dòng lặp actual theo method, DAX lấy actual một lần và WAPE theo một method.
- 16 đối chiếu local đạt: tổng 59.407.013 chuyến, một ngày/segment 21/01 Lyft_zone=58.431, các WAPE khớp nguồn, prior-year missing coverage giữ unavailable, share giữ cả hai hãng trên selected zone. Đây là kiểm tra local semantics, chưa phải native filter test.
- Hai trang local preview có số thật và grain/cửa sổ rõ. Default 06-26/01: 14.097.953 chuyến, YoY D-364 +1,974%, Lyft share 24,929%, 45 alert rows. Xem PNG trực tiếp; sửa spacing/caption và kiểm tra chữ số card ở kích thước gốc.
- Source PBIP draft nhúng CSV, TMSL model, Power Query, 27 DAX measures, hai trang PBIR/19 visuals. Kiểm tra 27 file theo 11 public Microsoft JSON schemas, field references và embedded bytes khớp CSV. PowerShell wizard không có runtime; không ghi đã chạy wizard/native review.
- Memo tiếng Anh mobility_planning_memo.pdf: đúng một trang, một biểu đồ, plan 4.871.468 trips. Nội dung tại cutoff 16/02 không chứa backtest WAPE hoặc share uplift/credit cost dùng post-cutoff data. Bản retrospective review riêng. 12 numeric/design claims có source/selection/known_at_cutoff, PDF đã đọc và xem render.
- README đúng tám mục, có nguồn/ngày tải/phương pháp/cách chạy/kết quả/giới hạn/AI use; demo script đủ 180 giây. Có hướng dẫn bàn giao native và bước Microsoft 365, chưa nói là đã demo thật hoặc tự kiểm tra bởi người dùng.
- Notebook tự chứa nhúng bảy hàm reporting, thêm six code cells; 62/62 code cells chạy từ đầu trong kernel/thư mục mới chỉ notebook + verified source cache; không repository scripts/processed inputs, không lỗi. 46 CSV khớp baseline. Chưa chạy runtime Colab thực tế.
- Gói ZIP được xây từ allowlist source/aggregate/artifacts, loại raw/weather_raw/.venv/cache/local Power BI state; kiểm tra integrity và inventory riêng. Workspace vẫn giữ raw/.venv để chạy local; không xóa nguồn.
- G7 local artifacts đạt; chưa PASS toàn bộ. Còn native model refresh/Power Query/DAX, slicer interactions, heatmap conditional formatting, hai ảnh chụp thực tế, Save As/mở lại PBIX. Ghi trạng thái chờ ở powerbi_source_validation.json và powerbi_handoff.md; không tạo binary PBIX giả.

## Bổ sung theo cách Grab đo marketplace - 14/10/2026

- Theo yêu cầu người dùng sau khi đối chiếu báo cáo quý 2/2026 của Grab, tin tuyển dụng Demand Planning và các bài Grab Tech/Inside Grab. Không mở rộng phạm vi dữ liệu; chỉ đọc thêm cột phí trên raw 01/2025.
- Kiểm tra trước phí: chênh lệch trong/ngoài vùng 02–04/01/2025 so cùng thứ 2024 đã là −13,85%, cửa sổ chính −9,49% (bootstrap −10,9% đến −8,0%). Raw đếm lại độc lập khớp. Kết luận đổi: so sánh hiện tại không tách được phần do phí. Memo tại 16/02 và bản hồi cứu đã cập nhật; PDF vẫn một trang.
- Nhãn vùng: 4,7% chuyến Lyft và 5,4% chuyến Uber bị thu phí nằm ở nhóm ngoài vùng.
- Cây metric: tách GMV proxy thành số chuyến × giá TB; Uber chạm vùng giá +9,2%/chuyến −7,8%, Lyft chạm vùng giá −5,8%/chuyến +5,8% (01/2024→01/2025).
- Chi phí credit tối đa 5,9% GMV proxy Lyft chạm vùng; 1.315.183 chuyến Lyft bị thu phí trong 06–26/01.
- Cảnh báo theo dải dự báo: 118 → 9 (2 lễ, 5 thời tiết ở ngày tham chiếu, 2 chưa giải thích). Sensitivity k = 2/2,5/3.
- Thiết kế thử nghiệm: MDE holdout theo khách (giả định), switchback theo giờ từ phương sai thật, SRM check.
- Notebook thêm section tự chứa; các CSV Power BI và preview giữ nguyên bản đã commit vì giá trị không đổi (script tạo lại chỉ khác định dạng số do phiên bản pandas).
- Còn mở: dữ liệu 11–12/2024 và 11–12/2023 để kiểm tra xu hướng trước phí (cần người dùng đồng ý mở rộng phạm vi); Power BI native vẫn chờ máy Windows; chưa commit/push.
- Notebook: Run all toàn bộ 73/73 code cell từ thư mục trống, kernel mới (pandas 3.0.6, Python 3.13), chỉ có notebook và 14 file nguồn khớp SHA-256; không lỗi. 45/62 CSV trùng byte, 17 chỉ khác làm tròn số thực (<1e-9; tổng tiền lệch <0,4 cent); 3 memo trùng. Ghi trong notebook_execution.json; chưa chạy trên Google Colab.

## Notebook nộp nhà tuyển dụng - 14/10/2026

- Viết lại notebook bằng tiếng Anh, 6 phần theo câu hỏi nghiệp vụ, mở đầu bằng executive summary và kết bằng bảng đề xuất. 139 ô/2.724 dòng code còn 58 ô/748 dòng.
- Giữ nguyên quy tắc: phạm vi request, loại zone 264, mẫu hợp lệ từng metric, vùng ≥95%, ngưỡng giá thấp $11,63, cửa sổ mưa chọn từ thời tiết, cutoff theo thời điểm hoàn thành chuyến.
- Bỏ khỏi notebook: Power BI pack, memo PDF, Excel, file kiểm tra và proxy độ nhạy giá (vì phép so sánh phí không tách được tác động).
- Run all từ thư mục trống, kernel mới: 31/31 code cell, không lỗi. Bảng ngày/giờ, 38 zone, hệ số mưa, 54 phương án phí, kiểm tra trước phí, phân rã GMV, thị phần Lyft, 28 dự báo, WAPE, 9 cảnh báo và MDE switchback khớp bảng repo (sai số tương đối 1e-9). Khoảng bootstrap lệch ở chữ số thứ tư do một luồng ngẫu nhiên.
- Chưa chạy trên Google Colab; chưa commit/push.

## Power BI project mới - 14/10/2026

- Thay bản PBIP nháp (TMSL, 2 trang, thẻ "Fee all-trip gap", 118 cảnh báo ±7%) bằng PBIP mới: model TMDL 13 bảng/42 measure, báo cáo PBIR 4 trang theo kết luận mới (−9,5% không phải tác động phí; cảnh báo theo dải dự báo; số chuyến vs giá).
- `scripts/build_powerbi_project.py` viết lại; `prepare_reporting_pack.py` chuyển đầu ra sang `data/reporting/` để không ghi đè `powerbi/`.
- Kiểm tra: TMDL parser, schema Microsoft cho 50 file JSON, pbiplint 0 lỗi, đối chiếu tham chiếu và số liệu, chạy lại trên máy người dùng cho file giống hệt. Chưa mở bằng Power BI Desktop.

## Current-state review — 15/10/2026

- Chạy lại toàn bộ notebook trong kernel mới/thư mục độc lập: 31/31 code cells, 0 lỗi, 0 stderr; 14 source hashes khớp manifest. Dùng cache và môi trường sẵn có, không retest tải/cài hoặc Colab.
- Đối chiếu 13 nhóm bảng chính khớp, có ánh xạ schema; bằng chứng trong notebook_execution.json.
- Báo cáo docs/current_state_review.md ghi các vấn đề: ZIP cũ chưa có TMDL/slide, alert calibration toàn mẫu và coverage khác nhau, power statement quá rộng, trạng thái Power BI/validation chưa đồng bộ, framing cutoff và retrospective trong notebook.
- Không sửa phương pháp hay kết luận trong notebook; chỉ cập nhật outputs. Không sửa raw, không mở rộng dữ liệu, không commit/push/publish.

## Rút gọn notebook theo slide báo cáo — 17/10/2026

- Đối chiếu notebook với `UrbanMobility_Report.pdf` (16 slide). Giữ đúng các phần có trên slide: dữ liệu và 4 nhóm, phí (so với nhóm ngoài vùng + kiểm tra trước phí), credit Lyft (thị phần + chi phí mỗi chuyến tăng thêm), mưa mùa hè 2024, cảnh báo 118 → 9, dự báo B1/B2/B3 và đề xuất.
- Bỏ phần không có trên slide: biểu đồ nhu cầu theo ngày, phân rã GMV, chuyến ngắn/giá thấp, ngưỡng vùng 90/99% và tuần mưa nhiều nhất, bootstrap CI, độ phủ phí, thị phần theo tuần, lưới kịch bản credit, chi phí credit/GMV, cỡ mẫu holdout/switchback/SRM, hệ số mưa mùa đông, độ nhạy k và biểu đồ dải toàn thành phố, WAPE theo nhóm/ngày lễ.
- Thêm phần slide có mà notebook cũ thiếu: số chuyến raw 59.409.057 và 2.044 chuyến bị loại, bảng 4 nhóm 06–26/01/2025, các bước 8,86 → 9,35 triệu / 5,25 triệu dự kiến, bảng 4 bước $25,88 và mức $12,94 khi dùng 50%, phân loại tự động 9 cảnh báo (2 lễ, 5 thời tiết ngày tham chiếu, 2 chưa giải thích), ví dụ thứ Bảy 22/02, lệch kế hoạch theo từng ngày và thời tiết 09/02, 16/02, 23/02.
- SQL dùng tên cột trong GROUP BY, không còn GROUP BY ALL. Quy tắc làm sạch, vùng ≥95%, cửa sổ mưa, quy tắc cảnh báo và cutoff giữ nguyên.
- 58 → 41 ô, 31 → 19 ô code. Chạy lại bằng kernel mới trong thư mục tạm chỉ có nguồn đã cache: 19/19 ô, 0 lỗi, 0 stderr. 8 nhóm bảng khớp data/processed (rtol 1e-9), hash 14 nguồn khớp bản ghi cũ. Chưa chạy trên Colab; chưa commit.
- Ghi chú: ví dụ 22/02 cho ra đúng 799.268,5 nên slide làm tròn thành 799.269; notebook in cả hai.

## Rút gọn Power BI theo slide — 17/10/2026

- Viết lại `build_tables`, measure và trang trong `scripts/build_powerbi_project.py` để 4 trang đi theo các bước trên slide: Summary, Fee and credit, Weather and alerts, Holiday-week plan. 13 → 11 bảng, 42 → 22 measure, 40 → 38 visual.
- Bỏ phần không có trên slide (GMV, nhóm chuyến, bootstrap, thị phần theo tuần, dải cảnh báo thành phố, mưa mùa đông, MAE, credit/GMV, bộ lọc năm). Thêm phần slide có: cột 2024/dự kiến/thực tế, thị phần Lyft theo giai đoạn, thẻ 33% hòa vốn và +7,7%, lý do cảnh báo theo quy tắc ≥3 giờ mưa/tuyết như notebook, lệch kế hoạch theo ngày.
- Kiểm tra: TMDL parser 0 cảnh báo, pbiplint 0 lỗi, tham chiếu trường/DAX và bố cục sạch, số tính lại từ dữ liệu nhúng khớp slide. Chưa mở bằng Power BI Desktop; chưa kiểm tra lại schema JSON; chưa commit.
