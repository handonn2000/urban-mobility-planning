# Nhật ký sử dụng AI

## 14/10/2026 - Module 0

- Người dùng yêu cầu giữ kế hoạch demo, tạo thư mục riêng và triển khai tuần tự với tiêu chí hoàn thành/cách làm.
- AI tạo cấu trúc, tài liệu và script thu thập/kiểm tra đầu vào. Mọi kết quả phải sinh từ chạy thật.
- Nguồn: link TLC chính thức và tài liệu Open-Meteo. Không dùng số minh họa trong deck làm kết quả.
- Tự kiểm tra của người dùng còn cần: chọn một dòng trong congestion_fee_by_request_date.csv, giải thích vì sao phí trước 05/01 phải không dương. AI không ghi việc này là đã được người dùng thực hiện.

- Kết quả chạy thật: G1 PASS 18/18, notebook 5 code cell không lỗi.
- Kiểm tra phát hiện 1.890 chuyến có phí đặt trước 05/01; 1.184 chuyến đón trước mốc nhưng tất cả trả sau mốc. Vì vậy tiêu chí thời điểm được cụ thể hóa bằng chuyến kết thúc trước mốc, giữ nguyên raw và lưu chênh lệch.
- Dữ liệu tháng theo pickup nhưng phân tích theo request có giờ ngoài tháng; chuyển sang audit M1, không xóa ở M0.

## 14/10/2026 - Notebook độc lập và tên file

- Theo yêu cầu người dùng, bỏ số module/nhãn gate khỏi code và notebook; chỉ giữ kế hoạch và tiêu chí trong tài liệu nội bộ.
- Đổi tên script thành prepare_source_data.py, notebook thành urban_mobility_demand_analysis.ipynb, và CSV/JSON/report theo nội dung.
- Notebook nhúng toàn bộ logic thay vì gọi script ngoài; thêm cài thư viện, cấu hình thư mục, tải nguồn và xử lý đầu vào để chỉ cần upload một notebook.
- CLI và notebook được so sánh AST để xác nhận các hàm dữ liệu giống nhau.

- Kiểm thử hoàn tất: thư mục trống và venv mới, chỉ copy notebook; notebook tự cài thư viện/tải nguồn, 10/10 code cell không lỗi. Không gọi dịch vụ Google Colab thực tế.

## 14/10/2026 - Làm sạch và tổng hợp

- Tạo clean_and_aggregate_trips.py và nhúng toàn bộ SQL/hàm vào notebook; không thêm module/gate vào code/notebook.
- Chính sách: giữ chuyến cho volume nếu ngày/hãng/endpoint xác định; loại từng metric không hợp lệ khỏi mẫu của metric. Chỉ loại hoàn toàn request ngoài phạm vi hoặc endpoint không rõ.
- Nhãn vùng 95%, lưu sensitivity 90%/99%; Q1 cước dương 01/2024=$11,63.
- Chạy SQL và notebook thật; đối chiếu tập giữ lại với bảng ngày/giờ và kiểm tra trực tiếp raw độc lập.
- Phát hiện cước 0 tập trung ngày 21/01/2025 Lyft, chưa gán nguyên nhân.
- Người dùng vẫn cần tự xem một dòng và giải thích phương pháp; không ghi rằng người dùng đã tự kiểm chứng.

## 14/10/2026 - Đơn giản hóa SQL

- Tách chuẩn hóa trường dữ liệu khỏi cờ audit; tách đếm phí khỏi tính tỷ lệ zone.
- Bỏ regex filename, nối tháng từ bảng source_files; dùng tên cột trong GROUP BY.
- Thay FILTER bằng SUM/CASE WHEN; giữ NULL trong mẫu tiền/chờ không hợp lệ.
- Chuyển giải thích sang Markdown và bỏ comment trong code notebook/script.
- Chạy lại script, so 15 bảng CSV cùng tham số với snapshot trước thay đổi; kết quả khớp trong sai số tiền dưới một cent.

- Notebook sau chỉnh sửa chạy từ đầu: 22 code cell, không lỗi; toàn bộ hàm nhúng khớp script; 15 bảng CSV tiếp tục khớp baseline.

## 14/10/2026 - Thời tiết và watchlist

- Sau đồng ý của người dùng, rà ERA5 2024 và chọn cửa sổ 06-08 chỉ từ thời tiết (>=20 giờ heavy, ưu tiên số đợt). Tải ba Parquet bổ sung, lưu riêng weather_raw để không đổi main scope.
- Dùng baseline khô cùng tháng/thứ/giờ; loại lễ và drizzle; báo cáo summer/winter riêng, không ép hệ số khớp nghiên cứu.
- Sinh watchlist trên main scope với D-7/D-14 và D-364; mọi reference date trước observation date. Rà 2 case với giới hạn, không gán nhân quả.
- Chạy CLI, notebook đầy đủ, tính lại một giờ; xem PNG biểu đồ trực tiếp; kiểm tra main tables không thay đổi.
- Kết quả/chứng cứ: docs/weather_and_alerts_report.md và docs/notebook_execution.json.

## 14/10/2026 - So sánh quanh phí

- SQL đơn giản chọn mẫu/gắn nhãn/tổng hợp; hàm nhúng khớp CLI và notebook không gọi script ngoài.
- 9 kết quả chính và 54 sensitivity; không làm đẹp kết quả theo số giả lập/nghiên cứu.
- Kiểm tra matched weekday/holiday count, bốn ô raw độc lập và tính tay; cùng chiều không chứng minh nhân quả.
- Quy đổi scaled_total_gap và tính proxy elasticity với cước dương baseline, ghi rõ không phải độ nhạy được nhận diện.
- Nguồn nghiên cứu: abstract xuất hiện trong kết quả tìm kiếm từ ScienceDirect; open toàn trang bị403, không khẳng định đọc full text.
- Chạy39 code cell từ đầu không lỗi, so output trước đó không đổi và xem PNG trực tiếp.

## 14/10/2026 - Credit Lyft và hòa vốn

- Đối chiếu trang 26-29 của deck gốc với share tuần, hai cửa sổ, uplift, chi phí/chuyến thêm, workbook và brief.
- Nhúng các hàm credit vào notebook tự chứa; không gọi script repo hoặc dùng processed CSV bên ngoài. Giữ tên nghiệp vụ, không đưa số module/gate vào code hoặc notebook.
- Thêm đối chiếu coverage ngày/phân khúc, share/volume, hai mẫu số uplift, 24 kịch bản, ví dụ 100 chuyến và edge cases. Lưu hồ sơ ở lyft_credit_validation.json.
- G5 đạt theo kiểm tra chạy thật: ví dụ credit cost $154,50, cost/extra $51,50; targeting ngưỡng 10% toàn mẫu/33,33% eligible. Workbook recalculated trong Artifact Tool; không tự ghi đã thử Excel native.
- Hoàn thiện brief với holdout 10%, eligibility trước treatment, zero-trip users, redemption follow-up và quy tắc mở rộng/dừng/thiết kế lại. Tạo PDF một trang, đọc đủ sáu mục và xem ảnh render trực tiếp.
- Chạy notebook 46 code cell từ đầu trong thư mục độc lập với kernel mới, chỉ notebook và cache nguồn; không script/processed input, không lỗi. 36 CSV trước đó không đổi, hàm credit nhúng khớp AST của CLI.
- Không truy cập Google Colab thực tế; hồ sơ phân biệt kiểm thử Jupyter độc lập và kiểm thử runtime Colab. Không đo customer redemption/retention hay ROI thực tế từ TLC.
- Người dùng vẫn cần tự chọn một dòng và giải thích phép tính; không ghi là người dùng đã làm việc này. Không đăng GitHub hoặc chạy chiến dịch thật.

## 14/10/2026 - Dự báo tuần có lễ

- Người dùng yêu cầu phân tích mục tiêu/chiến lược và hoàn thành phần dự báo theo kế hoạch. Đọc yêu cầu 28 ô, ba baseline, cutoff và cách tính metric trong deck/kế hoạch.
- Chốt B2 làm baseline kế hoạch trước test vì độ đơn giản/smoothing; giữ B3 là kịch bản chuyển hệ số giữa hai lễ. Không giả định B3 phải thắng.
- Phát hiện bảng ngày theo request gồm chuyến kết thúc sau cutoff. Dựng forecast_history bằng DuckDB, loại 9.961 chuyến dropoff sau 16/02; đối chiếu với bảng ngày mà không sửa raw/bảng ngày. Ghi giả định availability vì TLC không phải live feed.
- Tạo 28 forecast, bốn hệ số, lineage ngày nguồn, 45 dòng điểm, biểu đồ và ví dụ tính tay. Lưu forecast + memo trước actual join và kiểm tra SHA-256 sau scoring.
- 15 kiểm tra có kết quả thật: cutoff, nhãn vùng, nguồn tham số, hand forecast/metric, tương lai bị thay volume không đổi forecast, thiếu reference báo lỗi. Đối chiếu năm counts tham số trực tiếp raw độc lập.
- WAPE B1 4,45%, B2 3,48%, B3 3,61%; kết quả không giống mục tiêu minh họa B3 tốt hơn trong deck. Giữ B2 winner hồi cứu, không sửa số hoặc hệ số để B3 thắng.
- Memo tại 16/02 không chứa actual/score/winner tuần test hoặc kết quả credit tới 23/02. Weather chỉ là contingency định tính, không dùng weather actual tương lai hay hệ số mùa hè.
- Nhúng toàn bộ SQL/chín hàm vào notebook tự chứa; không thêm số module/tiêu chí gate vào code/notebook. Chạy 56 cell từ đầu trong môi trường độc lập với cache nguồn, không lỗi; 44 CSV khớp trước đó; AST forecast khớp CLI.
- Không truy cập dịch vụ Colab; không ghi rằng người dùng đã tự tính tay. G6 đạt theo artifact thật; không triển khai dashboard/đăng GitHub khi chưa được yêu cầu.

## 14/10/2026 - Báo cáo và đóng gói trên Mac

- Người dùng yêu cầu phân tích/hoàn thiện báo cáo, rồi xác nhận chỉ có Mac và sẽ đưa PBIX lên Microsoft 365 sau. Không coi ý định publish sau là quyền đăng nhập hoặc publish ngay.
- Đọc kế hoạch trang 34-37, AGENTS và skills Power BI/PDF; chuẩn bị phần portable, ghi native boundary rõ. PowerShell wizard không có runtime trên máy, nên tạo design/source pack trực tiếp và không ghi wizard đã chạy.
- Tạo report input có calendar/segment/method dimensions; giữ city weather độc lập slicer segment và kết quả window cố định độc lập date filter không phù hợp. DAX prior-year kiểm tra coverage; share giữ market denominator; WAPE theo absolute-error sum và actual một method.
- Kiểm tra 16 local rules và tổng/một ngày/segment bằng source CSV. Sinh hai preview từ số thật, xem trực tiếp, sửa caption spacing và kiểm tra card crop khi preview thu nhỏ làm chữ số khó đọc.
- Chuẩn bị source PBIP/TMSL/PBIR, kiểm tra public Microsoft schemas và field references. Resolver dùng cache/alias của schema embedded; không ghi việc đó là native DAX/model execution.
- Tạo memo tiếng Anh một trang/một chart, mọi giá trị truy nguồn và đúng cutoff. Không đưa credit kết quả tới 23/02 hoặc forecast test WAPE vào memo tại 16/02. Retrospective review lưu riêng.
- README tám mục, demo180 giây, native/cloud handoff. Người dùng chưa tự demo hoặc thực hiện native checks; hồ sơ không nhận thay việc đó.
- Notebook nhúng reporting logic, 62 cells Run all trong môi trường độc lập không lỗi; 46 CSV khớp baseline. Không truy cập Colab thực tế.
- Đóng gói ZIP loại raw/.venv/cache, kiểm tra entries/integrity. Không xóa raw, không đăng GitHub/cloud, không tạo PBIX giả. G7 còn native Power BI và không được đánh dấu hoàn thành toàn bộ.

## 14/10/2026 - Chuẩn bị repository GitHub theo yêu cầu

- Người dùng yêu cầu đẩy dự án lên GitHub bằng GitHub CLI; đây là quyền xuất bản repository được yêu cầu sau các bước phân tích/đóng gói trước đó.
- Xác nhận CLI đăng nhập handonn2000, tạo repository urban-mobility-planning ở chế độ private và khởi tạo branch main local.
- Chỉ stage source, aggregate và sản phẩm đã kiểm tra; loại toàn bộ data/raw, weather_raw, .venv, cache, ZIP và artifact-tool inspect files. Raw trên máy giữ nguyên.
- Kiểm tra không có file lớn từ 50 MB hoặc chuỗi credential phổ biến trong tập stage. Thêm Git attributes để bảo toàn byte CSV nguồn và nhận dạng PDF/PNG/XLSX là binary.
- README giữ trạng thái native Power BI pending, không biến việc đưa source lên GitHub thành bằng chứng đã tạo/kiểm tra PBIX hoặc đã publish Microsoft 365.

## 14/10/2026 - Bổ sung theo cách Grab đo marketplace

- Người dùng yêu cầu đối chiếu nguồn công khai của Grab và bổ sung theo đề xuất. Đọc báo cáo quý 2/2026, tin tuyển dụng GrabFood/GIP Demand Planning, bài Inside Grab về dự báo, cảnh báo, mưa và công cụ thử nghiệm của Grab Tech.
- Viết `scripts/analyze_marketplace_extensions.py`: kiểm tra trước phí và bootstrap, cây metric số chuyến × giá, chi phí credit/GMV, cảnh báo theo dải dự báo, MDE switchback/holdout và SRM.
- Phát hiện quan trọng: chênh lệch trong/ngoài vùng đã có trước 05/01. Đếm lại từ raw độc lập trước khi đổi kết luận; ghi rõ giới hạn ba ngày và tuần Tết dương lịch không cân.
- Dải cảnh báo bản đầu hiệu chỉnh trên 01/2024 quá rộng (±23–36%); sửa: bỏ ngày tham chiếu trong 01–07/01 và ngày lễ, hiệu chỉnh trên ngày không có sự kiện của cả hai năm, nới dải khi chỉ có một ngày tham chiếu. Ghi là in-sample.
- Kiểm tra giả định ban đầu "chuyến Lyft bị thu phí ≤ chuyến chạm vùng" sai; thay bằng bảng độ phủ nhãn vùng (4,7–5,4% chuyến chịu phí bị gắn ngoài vùng).
- Chạy lại `prepare_reporting_pack.py` để cập nhật memo; khôi phục CSV Power BI và preview về bản commit vì chỉ khác định dạng số. PDF memo một trang, đã xem ảnh render.
- Các phép tính holdout theo khách dùng phương sai giả định (TLC không có ID khách), ghi rõ trong bảng và phụ lục. Không commit hoặc đẩy GitHub.

## 14/10/2026 - Viết lại notebook để nộp

- Người dùng yêu cầu review, refactor, chia section theo góc nhìn Specialist GIP Demand Planning, bỏ dấu vết văn phong máy, giữ một notebook tự chứa, tiếng Anh.
- Đọc lại 7 script để giữ đúng định nghĩa trước khi viết gọn; dựng notebook mới với SQL DuckDB ngắn và bảng/biểu đồ phục vụ kết luận.
- Đối chiếu từng bảng chính với data/processed trước khi thay notebook cũ; sửa trình bày (định dạng số, nhãn trục, chú thích chồng) sau khi xem từng biểu đồ.
- Sửa một số liệu trong tóm tắt: chênh lệch trước phí là −13,8% (−13,848%), không phải −13,9%.

## 14/10/2026 - Dựng lại Power BI project

- Người dùng yêu cầu tạo PBIP. Rà bản nháp cũ thấy nội dung lỗi thời; dựng lại bằng script sinh TMDL + PBIR với dữ liệu nhúng.
- Không dùng gói MCP Power BI của Microsoft vì cần người dùng chấp nhận EULA; kiểm tra bằng schema chính thức, `@pbip-tools/tmdl-parser`, `pbiplint`, đối chiếu tham chiếu và tính lại measure từ dữ liệu nhúng.
- Sửa theo lint: định dạng %, ẩn cột số của fact, đánh dấu khóa, kiểu thập phân cố định, bỏ cột không dùng.

## 15/10/2026 — Current-state audit after a full notebook rerun

Ran the single notebook end to end in a new kernel and isolated working directory with 14 SHA-256 verified cached sources: 31/31 code cells, no cell errors/stderr. Compared 13 corresponding table groups with mapped schemas, exact counts and 1e-9 floating tolerance. Existing dependencies/cache were reused; Colab, network downloads and clean dependency installation were not retested. Outputs and execution evidence refreshed. Review recorded in current_state_review.md: stale delivery archives, retrospective alert calibration and unequal coverage/metrics, overstated power narrative, version-specific Power BI validation gaps and retrospective/cutoff framing. Analysis source and raw files unchanged; no publication.

## 17/10/2026 — Rút gọn notebook khớp slide báo cáo

- Người dùng gửi `UrbanMobility_Report.pdf` và yêu cầu notebook chỉ cần khớp số liệu trên slide, không phân tích thừa. Đọc 16 slide và từng ô notebook, lập bảng đối chiếu số trên slide với output.
- Viết lại notebook (41 ô) theo thứ tự slide; bỏ các phân tích không xuất hiện trên slide; thêm các bước tính mà slide trình bày nhưng notebook cũ chưa in ra. Cảnh báo được phân loại bằng quy tắc trong code (ngày lễ; ngày tham chiếu có ≥3 giờ mưa/tuyết), không gõ tay.
- Giữ quy tắc cũ ±7% kèm điều kiện thời gian chờ ±20% vì 118 trên slide gồm cả 4 cảnh báo chỉ do thời gian chờ; ghi rõ trong Markdown.
- Kiểm tra: chạy toàn bộ trong thư mục độc lập, so 8 bảng với data/processed, xem lại 4 biểu đồ. Cập nhật notebook_execution.json. Không sửa raw, không commit/push.

## 17/10/2026 — Rút gọn Power BI theo slide

- Người dùng yêu cầu review Power BI và bỏ thông tin thừa. Đối chiếu 40 visual/42 measure với 16 slide; phần lớn trang Demand monitoring và nửa trang Fee and credit không có trên slide.
- Sửa builder rồi sinh lại toàn bộ PBIP, không sửa tay file sinh ra. Lý do cảnh báo dùng cùng quy tắc với notebook (ngày lễ; ngày tham chiếu ≥3 giờ mưa/tuyết) thay cho quy tắc cũ "có mưa bất kỳ"; kết quả 9 cảnh báo không đổi.
- Dùng pbiplint, TMDL parser cài trong thư mục tạm; không cài vào repo. Không commit/push.
