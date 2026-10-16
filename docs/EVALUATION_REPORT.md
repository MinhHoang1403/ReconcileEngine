# Báo cáo đánh giá thuật toán

## Phạm vi và giao thức

Báo cáo này ghi kết quả thực đo ngày 2026-10-16 trên dữ liệu synthetic VND của SmartRecon. Hai feed business là khoản phải thu và giao dịch bank/PSP mô phỏng; không có sao kê thật và không có dữ liệu Olist-derived trong repository. Ground truth nằm ở `truth_edges.csv`/`truth_cases.csv`, được evaluator đọc sau khi engine hoàn tất và không được truyền cho matching runtime.

Development/holdout được tách ổn định theo parity của byte đầu `SHA-256(case_id)`. Policy không được điều chỉnh bằng kết quả holdout. Kết quả dưới đây dùng holdout gồm 47 truth edges. Manifest demo có seed `42`; hard benchmark dùng seed `20261016`. Public API duy nhất để chạy thuật toán là `smartrecon.engine.run_reconciliation`, giống backend.

Các định nghĩa:

- Edge precision = TP / (TP + FP); edge recall = TP / (TP + FN); F1 là harmonic mean của hai đại lượng này.
- Group exact match chỉ đúng khi toàn bộ tập order IDs và bank transaction IDs trùng truth group.
- Allocation error là sai lệch tuyệt đối giữa tiền phân bổ dự đoán và truth trên hợp của predicted/truth edges, tính bằng integer minor units; cạnh thiếu hoặc thừa được so với 0 thay vì bị bỏ qua.
- Auto-confirm chỉ gồm group có review status `NOT_REQUIRED`. Proposal không được cộng vào predicted confirmed edges; group do người dùng duyệt được đếm riêng.
- Khi mẫu số bằng 0, evaluator trả `null`/N/A, không tự gán 0 hoặc 1.

## Kết quả holdout

| Chỉ số | Giá trị thực đo |
|---|---:|
| Edge precision | 1,0000 (43/43) |
| Edge recall | 0,9149 (43/47) |
| Edge F1 | 0,9556 |
| Group exact precision | 1,0000 (43/43) |
| Group exact recall | 0,9348 (43/46) |
| Candidate precision | 0,9038 (47/52) |
| Candidate recall | 1,0000 (47/47) |
| Auto-confirm coverage | 0,9149 (43/47) |
| False auto-confirm | 0; rate 0/43 |
| Allocation MAE trên hợp predicted/truth edges | 14.893,62 VND |
| Tổng absolute allocation error | 700.000 VND |

Theo relation type trên holdout:

| Quan hệ | Truth edges | Confirmed precision | Confirmed recall | Candidate precision | Candidate recall |
|---|---:|---:|---:|---:|---:|
| 1:1 | 45 | 1,0000 | 0,9556 | 0,9184 | 1,0000 |
| N:1 | 2 | N/A | 0,0000 | 0,4000 | 1,0000 |

N:1 yếu không được tự xác nhận vì chỉ có tổng tiền, nhưng vẫn được tìm thấy để review. Đây là chủ đích ưu tiên correctness trước coverage. Holdout hiện không chứa truth edge 1:N; chỉ số 1:N được đo trên full demo, nơi confirmed precision/recall đều bằng 1,0000 cho 2 edges. Do số mẫu quan hệ phức tạp nhỏ, không được diễn giải các tỷ lệ này thành bảo đảm tổng quát.

## Phân biệt engine, proposal và review

Trên full demo 98 truth edges, engine tự xác nhận 91 edges, không có false auto-confirm; candidate retrieval tìm đủ 98 truth edges trong 104 candidates/confirmed edges. Một thí nghiệm review minh họa phê duyệt rõ ràng group N:1 gồm hai edges: tổng confirmed tăng lên 93 và reviewed-confirmed là 2, nhưng auto-confirmed vẫn giữ 91. Vì vậy thao tác con người không làm tăng giả tạo auto-confirm coverage.

## Ablation trên cùng holdout

| Biến thể | Edge precision | Edge recall | Edge F1 | Candidate precision | Candidate recall |
|---|---:|---:|---:|---:|---:|
| Exact-reference baseline | 1,0000 | 0,3830 | 0,5538 | 1,0000 | 0,3830 |
| Reference + constrained | 1,0000 | 0,9149 | 0,9556 | 0,9565 | 0,9362 |
| Thêm fuzzy candidates | 1,0000 | 0,9149 | 0,9556 | 0,9574 | 0,9574 |
| Thêm bounded group/split candidates | 1,0000 | 0,9149 | 0,9556 | 0,9038 | 1,0000 |
| Full waterfall | 1,0000 | 0,9149 | 0,9556 | 0,9038 | 1,0000 |

Fuzzy và group/split tăng candidate recall nhưng không tăng auto-confirm recall, vì các lớp này giữ bằng chứng yếu ở proposal. Ablation lọc public rule IDs từ cùng engine output; không có matching engine thứ hai trong notebook.

## Hard-profile benchmark

Lệnh tái lập:

```powershell
uv run python scripts/run_evaluation.py --orders 1000 --seed 20261016 --output reports/evaluation_results.json
```

Kết quả Windows 11, Python 3.12.14, AMD64 Family 25 Model 68:

| Thuộc tính | Giá trị |
|---|---:|
| Orders | 1.000 |
| Bank rows | 998 |
| Runtime engine | 3,440 giây |
| Peak Python allocation (`tracemalloc`) | 9.741.897 bytes |
| Edge precision | 1,0000 |
| Edge recall | 0,9922 |
| Candidate recall | 1,0000 |
| False auto-confirm | 0 |
| Allocation MAE | 1.369,86 VND |
| Allocation absolute error | 700.000 VND |

Dataset hashes:

- orders: `706e889534bbddc753fc99508e7efd52f0075562748d4950f1aefd97df89fa9b`
- bank transactions: `b85f7c0fdcae217382f2a90a9510f583781d19eba9294a3ddf014a4a5e1136c6`
- truth edges: `70d4ddae0476aa69fda35a723ad0a33439c372dcc454b38152d05340579`
- truth cases: `c7561b7bb3150752ca61603e6e1507992c00af6f39e647990c90cb5e7683e94d`

Profile 1.000 orders giữ các hard cases được định nghĩa (ambiguous, N:1, 1:N, partial/over, duplicate, typo, orphan, fee có/không có chứng cứ) và mở rộng tải bằng exact fillers. Vì tỷ lệ filler exact cao, benchmark này chứng minh khả năng tái lập và một mức tải cụ thể, không chứng minh hiệu năng hoặc accuracy trên phân bố hard cases dày đặc hay dữ liệu thực.

Sai số phân bổ 700.000 VND đến từ truth edges không được engine tự xác nhận do thiếu bằng chứng; chúng được đánh giá như prediction bằng 0. Các cạnh đã xác nhận đúng có sai số tiền bằng 0. Cách tính này tránh báo cáo sai lệch bằng 0 bằng cách chỉ nhìn các cạnh đã match.

## Tái lập

Notebook chính là `notebooks/reconciliation_research.ipynb`. Kiểm thử dùng kernel sạch, working directory tương đối và chạy mọi cell bằng `nbclient`; notebook đã được thực thi và lưu output thực. Dependency được khóa trong `uv.lock`. Script evaluation ghi manifest, seed, dataset hashes, policy snapshot, phần cứng và commit hiện hành vào JSON output. Runtime artifact nằm trong `reports/` và bị Git ignore để tránh commit dữ liệu chạy tùy máy; bảng kết quả kiểm chứng được version hóa trong tài liệu này.

## Hạn chế và cách đọc kết quả

- Đây là synthetic evaluation nhỏ, không phải external validation và không chứng minh độ chính xác trên sao kê thật.
- Holdout được tách theo synthetic case ID; chưa có independent source/customer groups từ dữ liệu quan sát.
- Số truth group N:1/1:N/M:N ít. M:N tổng quát vẫn review-only và không nằm trong chính sách auto-allocation.
- `tracemalloc` đo Python allocations, không phải toàn bộ resident memory của process/container.
- Chưa benchmark 10.000+ orders, đồng thời nhiều người dùng, FX hoặc public deployment.
- Precision 1,0000 là kết quả của đúng bộ holdout/seed/policy đã nêu, không phải cam kết phổ quát.

Nguồn phương pháp và tài liệu kỹ thuật được phân loại tại [RESEARCH_REFERENCES.md](RESEARCH_REFERENCES.md), gồm record linkage, Precision/Recall/F1, RapidFuzz, Decimal, PostgreSQL và các giới hạn heuristic nội bộ.
