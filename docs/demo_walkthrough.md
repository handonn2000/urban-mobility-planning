# Demo 3 phút

Mục tiêu: cho người xem hiểu câu hỏi, logic và quyết định; không đọc code. Trên Mac dùng hai PNG và memo PDF. Khi có Power BI native đã kiểm tra, dùng cùng thứ tự visual và filter. Timing dưới đây cộng đúng 180 giây; luyện bằng đồng hồ, không ghi là đã demo nếu mới có script.

## 00:00-00:30 — Câu hỏi và sản phẩm

**Show:** demand_monitoring_preview.png; nói rõ local preview.

“This project asks how New York's congestion fee, Lyft credits and weather relate to completed ride-hailing demand, and how to plan a holiday week. I use three main months and four operator-zone segments. The two pages summarize monitoring and decisions; the notebook provides the evidence. These are local previews. Native Power BI testing is still pending.”

## 00:30-01:15 — Dữ liệu và nhãn vùng

**Show:** trend bốn phân khúc; đối chiếu ngày 21/01 + Lyft/zone từ report_reconciliation.csv.

“The retained sample contains 59.407 million completed trips. DuckDB handles the large files; pandas receives small aggregates. I classify 38 zones using a 95 percent fee rate in January, and label a trip when either endpoint touches a zone. Through-zone trips remain a limitation. Invalid fares affect price samples without removing valid trip volume. For one check, Lyft zone trips on January 21 equal 58,431 in the source and report input.”

## 01:15-02:15 — Phí, credit và kinh tế

**Show:** price_credit_plan_preview.png; fee bars, share trend, cost card.

“The pooled zone volume is 9.49 percent below a comparison-based counterfactual in matched January windows, while total observed trips rose 1.97 percent. I treat the gap as observational because the control may be affected. Uber and Lyft move differently. The January-February credit comparison gives a 1.608 percentage-point share gap and a 6.15 percent uplift proxy. At an assumed six-dollar contribution and full redemption, credit cost is 25.88 dollars per extra trip. That is a scenario, not measured ROI. The proposed next step is a targeted credit test with a ten-percent randomized holdout, net contribution as the economic decision metric, and waiting-time and cancellation guardrails.”

## 02:15-02:45 — Mưa, dự báo và cutoff

**Show:** summer card và forecast chart; mở memo PDF nếu cần.

“Summer heavy-rain hours show a city-wide trip factor of 1.077 across 35 hours; I do not transfer it to February. The cutoff plan uses B2 and totals 4.871 million trips. History excludes trips completed after February 16. Retrospectively, B2 WAPE is 3.48 percent and beats the holiday adjustment. The planning memo contains no test-week score or future credit comparison.”

## 02:45-03:00 — Giới hạn và bước tiếp

“The data measures served demand, with no customer redemption, true margin or driver supply. One holiday and one test week limit generalization. The next verification step is native Power BI refresh, filter checks and saving the PBIX before cloud sharing.”

## Tự chuẩn bị câu trả lời

- Vì sao endpoint proxy không thấy hết phí? Vì sao đối chứng có spillover?
- Với 100 chuyến nền, uplift 3%, vì sao có 103 credit nhưng chỉ ba chuyến tăng thêm?
- Vì sao 10% whole-base uplift khác 33,33% eligible uplift khi coverage=30%?
- WAPE tổng lấy 28 absolute errors chia tổng actual, khác average WAPE nhóm thế nào?
- Tại sao B3 không thắng? Vì chuyển một hệ số MLK sang Presidents' Day không được bảo đảm.
- Vì sao card city weather không đổi theo segment? Vì nguồn không có grain hãng/vùng.

Không dùng demo hồi cứu làm bài phát biểu giả lập tại 16/02; memo cutoff là tài liệu khác.
