# Báo cáo đánh giá thuật toán

## Phạm vi và giao thức

### Đối chứng tổng hợp — Checkpoint F, 2026-10-20

Baseline core `4dfd62e3bf8289477e291463f5afa4b41c0505d4`, candidate matching/resolver đã commit D/E; F không chỉnh matching/policy. `research/matching_evaluation.py --extended` chạy cùng CSV bytes/policy/seed, warmup + năm lần đo cho demo, hard 1.000, holdout mới và stress 3.000. Source file hashes/commit/dirty flag, môi trường, từng thời gian và tuple allocation được lưu trong `reports/lab/comprehensive-{baseline,candidate}.json`. Trên host Windows 11 26300/AMD64 Family 25 Model 68, Python 3.12.14, Pandas 2.3.3, RapidFuzz 3.14.6, DuckDB 1.5.6. Không đưa truth vào normalizer/engine.

| Bộ dữ liệu | Edge F1 trước → sau | False auto trong phạm vi evaluator trước → sau | Candidate recall sau | Allocation absolute error sau (VND) |
|---|---:|---:|---:|---:|
| Demo 100/98 | 0,962963 → 0,962963 | 0 → 0 | 100% | 1.000.000 |
| Hard 1.000/998 | 0,996481 → 0,996481 | 0 → 0 | 100% | 1.000.000 |
| Holdout gộp/chia 270/260 | 0,740741 → 0,754717 | 10 → 0 | 100% | 68.391.146 |
| Stress 3.000/2.998 | 0,998831 → 0,998831 | 0 → 0 | 100% | 1.000.000 |

Demo/hard/stress có từng tuple allocation giống baseline; conservation true và semantic checksum ổn định trong mỗi implementation qua năm lần lặp. Holdout bổ sung trong `research/financial_cases.py` không import matching code, sinh 180 cases/330 truth edges bằng seed 20261020, gồm 40 cases mỗi 1:1/N:1/1:N/M:N, 10 collision và 10 Unicode false-reference không có truth edge. Hash semantic orders `041988b6…f5a7a1`, banks `06c2bb0e…efccc0`, truth `b2d4c47d…bf352` khớp hai lần đối chứng. Cases được tạo sau khi policy/thuật toán đã chọn; không dùng kết quả để tune. Các họ lỗi adversarial đã biết từ C, không tuyên bố đây là phân phối nghiệp vụ thực hoặc khái niệm lỗi chưa từng biết.

Evaluator phân vùng theo participants có truth edge để hỗ trợ development/holdout; vì vậy zero-edge Unicode cases không vào mẫu số false-auto mặc định. Bổ sung kiểm tra **toàn bộ allocated edge keys trừ toàn bộ truth keys** trên holdout đầy đủ, kể cả hai bên orphan: **20 → 0 cạnh phân bổ sai**, không che 10 Unicode false matches. Trước/sau error trên hợp truth/predicted theo evaluator 73.167.445 → 68.391.146 VND; phần lớn error còn lại là M:N/collision **chưa xác nhận**, không phải tiền biến mất. Không đổi quy tắc an toàn để tăng recall.

Holdout sau sửa: 1:1 có precision 100%, confirmed recall 80% (10 collision chưa xác nhận), candidate recall 100%; N:1 và 1:N precision/recall/candidate recall 100%; M:N confirmed recall 0% đúng phạm vi review-only, candidate recall 100%, candidate precision 35,93%. Group precision 92,31%→100%, group recall giữ 120/170=70,59%. Không dùng F1 tổng để che M:N chưa tự xử lý hoặc candidate burden tăng.

Median giây trước/sau demo 0,117/0,090; hard 3,409/3,671; holdout 0,924/1,048; stress 25,195/16,990. Peak **Python tracemalloc**, không native RSS, trước/sau lần lượt 703.461/732.493; 7.773.952/7.789.364; 2.547.038/2.739.466; 21.824.348/21.873.560 bytes. Baseline có một phần công việc Docker/QA khác chạy trên host; **không suy cải thiện tốc độ từ các chênh lệch này**. Stress chủ yếu là deterministic 1:1 fillers, được bổ sung holdout nhiều group để không gọi 3.000 đơn dễ là bằng chứng chất lượng grouping. Lần yêu cầu sinh 10.000 bị generator từ chối (contract 1.000–3.000); không thay generator để vượt giới hạn và không tuyên bố đã stress 10.000.

Mapping đối chứng lại 24 schemas: baseline 34 đúng/7 sai/1 thiếu, precision 82,93%, recall 97,14%, coverage 82%; candidate 35 đúng/0 sai/0 thiếu, precision/recall 100%, coverage 70%. Abstention làm giảm coverage nhưng loại mapping sai. Manual-decision proxy 16→15. Classification cùng case hash D: 17/19→19/19, amount-weighted misclassification 300.000→0, confusion matrix chi tiết ở phần D. Hai số đo không có nghĩa hiệu quả trên toàn bộ dữ liệu ngoài mẫu.

Dữ liệu được chủ dự án chỉ định ở workspace chính có 100/98, không phải 380/362; CSV logical rows của cả bốn file business/truth khớp Lab dù hash vật lý khác line endings. `a_website_first` có OMS 606, bank 279, Shopee 133, TikTok 81 và manifest tự khai Olist-derived/simulated, không phải sao kê tài chính thật. `research/external_import_evaluation.py` đọc từng cặp receivables + bank, không ghép thành nhiều feed. Cả ba đều đòi xác nhận nguồn/cột; không tự coi credit/fee/net là cùng nghĩa, không aggregate settlement. Ground truth ngoài này có scenario/outcome nhưng không có allocated cash edges, vì vậy **không có matching Precision/Recall/allocation benchmark hợp lệ** cho bộ đó. Chỉ báo schema/abstention/hash; không copy raw files hoặc nhãn vào runtime/repository.

Quyết định giữ runtime hiện tại với các guard B/C/D/E và sửa tính toàn vẹn Excel. Valentine/Splink/CP-SAT vẫn chỉ ở môi trường research: không đủ lợi ích vận hành để tích hợp; Pandera không thêm runtime; Sato chỉ ý tưởng, không ML/LLM. Không điều chỉnh threshold hoặc kiến trúc.

### Workflow nhập liệu — Checkpoint E, 2026-10-20

Giả thuyết: bỏ bước xác nhận lại cột đã có đủ chứng cứ sẽ giảm thao tác bắt buộc, không giảm guard tiền/ngày/nguồn. Baseline B browser demo cần hai nút từ source đến Health, không chọn trường/advanced. E cần một nút, không chọn trường/advanced ở desktop/laptop/mobile; vẫn nút **Chạy đối soát** riêng, cảnh báo không tự ghi nhận. Đây là giảm một thao tác bắt buộc theo cùng kịch bản, không phải chứng minh human task time.

Đối chứng file ngoài demo gồm năm tình huống × ba viewport; code và cách sinh tại `scripts/qa_import_workflow.py`, reports ignored `reports/lab/unfamiliar-import*/results-*.json` có từng run ID/source SHA/layout/cash/export. CSV/XLSX rõ và 1.000 dòng đều tự đến Health; hai cột tiền cần một chọn, `1.000` cần hai chọn separator. 15/15 hoàn tất tự động, không cần mở advanced trước Health; không thay thế tỷ lệ hoàn thành của người mới. Desktop elapsed tới Health CSV/XLSX/ambiguous/locale/large lần lượt 451/440/735/838/836 ms; mobile 293/453/707/524/830 ms. Các lần script không warmup/lặp có kiểm soát và có thể chạy song song nên **không dùng để tuyên bố cải thiện latency**. Số clicks tính từ sau file selection; total changes ghi cả hai file selections. Không đo hoặc giả lập câu trả lời “người dùng hiểu thông báo”.

Chọn giải pháp core guard nhỏ + UI progressive disclosure, giữ toàn bộ normalizer/Health Gate/traceability và dependency runtime hiện có. Một lần quét toàn bộ mapped money/currency tránh sample bỏ sót format; conservative abstention có thể đòi xác nhận nhiều hơn với locale có thể hợp lệ. Profile đã xác nhận là cách giảm lặp thao tác, không phải bỏ full-row validation. Nguồn NN/g/WHATWG/W3C ở RESEARCH_REFERENCES; chỉ QA tự động theo quyết định chủ dự án. Matching/classification scores bên dưới không được suy từ UI.

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

## Đối chứng mapping trong Lab — 2026-10-20

Baseline core là `4dfd62e3bf8289477e291463f5afa4b41c0505d4`, không đổi policy/ngưỡng matching. `research/mapping_cases.py` chứa 24 bảng synthetic độc lập, 35 đáp án cặp cột và 15 quyết định bắt buộc abstain. Hash dataset/đáp án/config: `0254079b10a208b30c7d450f2a8b0e3f948011d0034ac130a50dce2b516362ec`. Mỗi matcher nhận đầy đủ business contract, không nhận đáp án hoặc danh sách trường kỳ vọng riêng của fixture. Split credit/debit được test transformation riêng, không tính hai trường derived thành direct mapping.

| Phương pháp | Đúng/sai/bỏ sót cặp | Precision | Recall | Coverage tự chọn | Quyết định thủ công (proxy) | Median mỗi bảng | Peak Python bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 34 / 7 / 1 | 82,93% | 97,14% | 82% | 16 | 4,84 ms | 38.198 |
| Current đã sửa | 35 / 0 / 0 | 100% | 100% | 70% | 15 | 9,59 ms | 38.088 |
| Valentine COMA | 21 / 20 / 14 | 51,22% | 60% | 82% | 29 | 50,54 ms | 150.658 |
| Current ∩ COMA | 21 / 0 / 14 | 100% | 60% | 42% | 29 | 52,97 ms | 152.054 |

Precision = đúng/(đúng+sai), recall = đúng/(đúng+bỏ sót), coverage = số cặp tự chọn/50 quyết định khai báo, proxy thủ công = bỏ sót + 15 quyết định abstain. Proxy không đo công sức người dùng và không tính công sửa những lựa chọn sai; không suy thành click thật. Baseline coverage cao hơn nhưng bao gồm bảy quyết định không an toàn: tiền rỗng/sai kiểu/đuôi dữ liệu sai/profile drift/signed không quy ước và ngày sai. Candidate phục hồi một fee mapping bị weak ID candidate chiếm cột, không mở rộng ngưỡng hoặc suy tiền từ phép cộng.

Mỗi case warmup một lần, đo năm lần bằng `perf_counter`/`tracemalloc`; median tổng 120 lần. Windows, Ryzen 5 7535HS (6 cores/12 threads), Python 3.12.14, Pandas 2.3.3, RapidFuzz 3.14.6, DuckDB 1.5.6; Valentine 1.1.0 chỉ trong `research/.venv`. `tracemalloc` không đo RSS/native memory và bỏ import warmup. Mapping source SHA-256 baseline `c7eaca1a177bbff9581e6ef55a1a73835d3789720bac989ca2ca873bc4e60b8d`; candidate `cbae660cd64186c99ca66944d9b93df1010d0feb40d87c93da6dee7939b76c0c`. JSON lưu tại `reports/lab/mapping-{baseline,candidate,coma,hybrid}.json`. Đây là benchmark synthetic nhỏ, không chứng minh accuracy trên nguồn tài chính thật; tập gắn nhãn holdout trong bộ nhỏ chỉ là regression chưa dùng để chỉnh ngưỡng, không phải external validation.

Kết luận: giữ heuristic đã sửa và validation hiện có; không tích hợp COMA hay dependency nghiên cứu vào production. Chất lượng quyết định tăng nhưng thời gian mapping tăng khoảng 4,75 ms/case trên phép đo này; không tuyên bố cải thiện tốc độ. Global assignment giữ thuật toán xác định đơn giản, không cho weak type-only guess giữ chỗ của semantic match. Fixture cấu trúc riêng phủ header lệch/hai hàng/multi-sheet/ambiguous-sheet/unnamed/footer; integration phủ CSV/XLSX Việt/Anh/không dấu, leading zeros, toàn bộ dòng và dòng tổng. Sato chỉ là tham khảo về ngữ cảnh, không chạy model.

Tái lập trên nhánh nghiên cứu (đường dẫn baseline chỉ đọc):

```powershell
uv sync --project research --frozen
research/.venv/Scripts/python.exe research/mapping_evaluation.py --method current --core-source C:/Work/ReconcileEngine/src --repeats 5 --output reports/lab/mapping-baseline.json
research/.venv/Scripts/python.exe research/mapping_evaluation.py --method current --repeats 5 --output reports/lab/mapping-candidate.json
research/.venv/Scripts/python.exe research/mapping_evaluation.py --method coma --repeats 5 --output reports/lab/mapping-coma.json
research/.venv/Scripts/python.exe research/mapping_evaluation.py --method hybrid --repeats 5 --output reports/lab/mapping-hybrid.json
```

Trên Linux dùng `research/.venv/bin/python`. Runner ghi path/hash/source commit/dirty state để tránh vô tình import editable package từ worktree khác. Không truyền truth vào mapping runtime.

## Matching, sensitivity và công cụ nghiên cứu trong Lab — 2026-10-20

`research/matching_evaluation.py` chạy baseline `4dfd62e` và core candidate trên **cùng đường dẫn demo chủ dự án cung cấp**, raw CSV hashes tại QA_REPORT, rồi sinh cùng hard dataset 1.000 orders bằng seed `20261016`. Mỗi dataset warmup một lần, năm lần đo, so checksum trong từng implementation và conservation ở mọi run. Cấu hình/thư viện/phần cứng/source hashes/source commit/dirty state/từng thời gian được ghi JSON. Trước đo đã chạy 32 golden/property tests; sau sửa có thêm engine allocation property test. Không dùng truth làm input engine.

| Full engine | Baseline | Candidate |
|---|---:|---:|
| Demo confirmed cash (VND) | 66.431.000 | 66.431.000 |
| Demo edge P / R / F1 | 1 / 0,928571 / 0,962963 | Không đổi |
| Demo candidate recall / false auto | 1 / 0 | Không đổi |
| Demo allocation absolute error (VND) | 1.000.000 | 1.000.000 |
| Holdout edge F1 / false auto | 0,955556 / 0 | Không đổi |
| Hard **full truth** edge F1 / false auto | 0,996481 / 0 | Không đổi |
| Demo median / peak Python allocation | 129,61 ms / 740.413 bytes | 107,48 ms / 732.493 bytes |
| Hard median / peak Python allocation | 3,317 s / 7.758.272 bytes | 3,638 s / 7.851.076 bytes |

Từng tuple `(order_id, bank_id, cash)` trên cả demo và hard **giống nhau hoàn toàn** trước/sau; không chỉ so tổng tiền. Sai số đánh giá bao gồm truth edges chưa tự xác nhận (prediction 0), không phải cash bị mất/allocated sai. Semantic checksum giữa hai implementation khác vì thay ưu tiên/sắp xếp evidence groups; trong mỗi implementation năm lần có checksum ổn định. Snapshot run cũ không được tính lại hay ghi đè. Thời gian có dao động hệ thống local, không kết luận nâng tốc độ; đây không phải stress benchmark hoặc dữ liệu tài chính thật.

| Quan hệ trên demo (full truth) | Truth edges | Candidate recall | Confirmed recall |
|---|---:|---:|---:|
| 1:1 | 89 | 100% | 97,75% |
| N:1 | 4 | 100% | 50% |
| 1:N | 2 | 100% | 100% |
| M:N | 3 | 100% | 0% (review-only) |

Sensitivity dùng **development** và grid khai báo trước: `max_days_diff ∈ {0,1,3,7}`, fuzzy threshold `{70,85,95}`, group/split size `{2,3,4}` (36 cấu hình). Mọi run conservation đúng/false auto 0 trên tập này; candidate recall 100%; F1 lần lượt 0,583333 / 0,8 / 0,969697 / 0,969697 theo cửa sổ ngày. Không chọn policy dựa trên holdout, không đổi default 3 ngày/85/top-5/size-3/block-20/2.000 tổ hợp. Đây là độ nhạy trên demo ít hard cases, không kết luận ngưỡng tối ưu phổ quát.

### Splink: chỉ đánh giá ranking, không auto-confirm

Train EM không nhãn trên development hiện có; holdout participant không giao development. Cùng raw input, cùng envelope currency/date 0–3 ngày/amount ±10%, top-5, seed 42; feature challenger gồm reference token đầu tiên trong memo, tên, amount và ngày. RapidFuzz giữ scorer/tokenization hiện hành; hai cách trích/so sánh chuỗi không tương đương nên không gán mọi khác biệt cho riêng EM. Mô hình 1:1 không giải group/split. Default prior 0,0001 chưa hiệu chuẩn; Splink cảnh báo m/u của tên không đủ quan sát, giữ default các mức thiếu. Không giấu warning, không mô tả match probability là chứng cứ thu tiền.

| Ranking trên 47 truth edges/46 queries | Fuzzy-only | Splink | Splink bỏ tên |
|---|---:|---:|---:|
| Candidate recall | 93,62% | 95,74% | 95,74% |
| Precision@1 / MRR | 95,65% / 0,9565 | 97,83% / 0,9783 | Không đổi |
| Precision@5 | 19,13% | 19,57% | 19,57% |
| False candidates / tổng candidates | 15 / 59 | 45 / 90 | 45 / 90 |
| Candidates trung bình/query | 1,283 | 1,957 | 1,957 |
| Median inference (kể khởi tạo DB/linker) | 8,94 ms | 222,92 ms | 287,95 ms |
| Peak Python bytes | 17.088 | 334.599 | 282.069 |

P@5 chia 5 cho mỗi query kể cả trả ít hơn năm candidates. Recall theo quan hệ: 1:1 44/45 → 45/45; N:1 0/2 ở cả hai ranking vì amount block 1:1, không được che bằng số tổng. Holdout này không có 1:N/M:N; full-engine table phía trên báo các quan hệ đó. Reverse input order cho cả ba cách giữ ranking giống nhau. Thời gian train được lưu riêng trong `candidate-ranking.json`; không tính vào inference. Giữ RapidFuzz runtime; Splink cần dữ liệu độc lập/hiệu chuẩn tốt hơn, không giúp candidate recall của full engine vốn đã 100% trong demo.

### CP-SAT: nghiệm tổ hợp không phải chứng cứ tài chính

Tám subset fixtures, hash `634531f47c3361688ce0e2caf3f4d4a2b76634e8e6a67cabaee37690fa898f2e`; oracle tổ hợp không gọi engine/solver. So cùng max subset size; size-4 là cấu hình nghiên cứu tường minh, không đổi policy mặc định. CP-SAT giới hạn 1 giây/một worker/seed 42; ngoại lệ timeout fixture dùng 0 giây và explosion dừng sau năm nghiệm.

| Case | Số nghiệm oracle | Bounded tìm được | CP-SAT tìm được / status | Tìm hết? |
|---|---:|---:|---|---|
| N:1 đơn giản | 1 | 1 | 1 / OPTIMAL | Có |
| 1:N đơn giản | 1 | 1 | 1 / OPTIMAL | Có |
| Cùng tổng, participant khác | 4 | 4 | 4 / OPTIMAL | Có |
| Block 21 phần tử | 40 | 0, báo exhausted | 40 / OPTIMAL | Có |
| Nhóm bốn phần tử | 1 | 1 | 1 / OPTIMAL | Có |
| Enumeration budget 1 | 37 | 0, báo exhausted | 37 / OPTIMAL | Có |
| 80 khoản cùng tiền, chọn bốn | 1.581.580 | 0, báo exhausted | 5 / FEASIBLE | Không |
| Time limit trước search | 1 | 1 | 0 / UNKNOWN | Không |

CP-SAT median lần lượt 2,844 / 2,470 / 3,518 / 96,742 / 4,118 / 100,294 / 11,660 / 1,777 ms; peak Python allocations tối đa 42.729 bytes (không phải native solver RSS). Mỗi nghiệm được kiểm tra lại bằng phép cộng integer và participant identity. Một ví dụ M:N 100.000+200.000 đối 150.000+150.000 có hai flow khác nhau nhưng đều đúng tổng; script chứng minh không thể suy identity từ conservation. Không chuyển bất kỳ nghiệm CP-SAT thành allocation/confirmed. Solver có lợi cho block lớn trong fixture nhưng nhiều nghiệm/budget/triage còn cần benchmark rộng: giữ bounded runtime, CP-SAT chỉ nghiên cứu tiếp.

Tái lập (sau `uv sync --project research --frozen`):

```powershell
research/.venv/Scripts/python.exe research/matching_evaluation.py --dataset C:/Work/ReconcileEngine/data/demo/vn_synthetic_demo --core-source C:/Work/ReconcileEngine/src --output reports/lab/matching-baseline.json
research/.venv/Scripts/python.exe research/matching_evaluation.py --dataset C:/Work/ReconcileEngine/data/demo/vn_synthetic_demo --output reports/lab/matching-candidate.json
research/.venv/Scripts/python.exe research/ranking_evaluation.py --output reports/lab/candidate-ranking.json
research/.venv/Scripts/python.exe research/solver_evaluation.py --output reports/lab/subset-solvers.json
uv run python scripts/qa_matching.py --output reports/lab/matching-http-oracles.json
```

`qa_matching.py` chỉ cho mutation tại loopback Lab port 8002, từ chối URL chính trước request. Các thí nghiệm vẫn chưa thay thế kiểm định classification, stress test, UX, restart/concurrency tổng hợp và diễn tập release ở các checkpoint sau.

## Classification và residual ownership trong Lab — 2026-10-20

Đáp án độc lập trong `research/classification_evaluation.py`: 15 tình huống, 19 bản ghi cần kiểm tra, case hash `a82203b936482b52775e96523cb3705197f9f3d93a42c7c5cac45abb4fde737c`. Bao phủ full/partial/overpaid riêng một order/residual bank dùng chung/no receipt/unknown/ineligible/duplicate/collision/PSP fee/search budget và approve/reject/undone. Ineligible được kiểm tra là **bị loại khỏi effective input**, giữ contract cũ; không báo sai rằng API đã materialize trạng thái `NOT_ELIGIBLE` cho order không có trong result.

Baseline source `4dfd62e` và candidate cùng dữ liệu/expected labels:

| Expected → observed | Baseline | Candidate |
|---|---:|---:|
| FULL → FULL | 4 | 6 |
| FULL → OVERPAID (sai) | 2 | 0 |
| PARTIAL → PARTIAL | 2 | 2 |
| OVERPAID → OVERPAID | 1 | 1 |
| NO_CONFIRMED_RECEIPT → cùng nhãn | 5 | 5 |
| UNKNOWN → UNKNOWN | 4 | 4 |
| Ineligible → bị loại đúng | 1 | 1 |

Accuracy 17/19 (89,47%) → 19/19 (100%) chỉ trên bộ synthetic nhỏ này. Tổng nghĩa vụ của hai order bị phân loại sai 300.000 → 0 VND; **không phải tiền allocation sai/mất**. Trước sửa, ca N:1 100.000 + 200.000 nhận 350.000 đã phân bổ đúng 100.000/200.000 và giữ 50.000 nhưng gán OVERPAID cho cả hai. Sau sửa là FULL/FULL, 50.000 vẫn bank unapplied và một `OVERPAY_RESIDUAL` 50.000, không tự quy thuộc vào từng order. Trường hợp một order có confirmed ownership riêng với credit 120.000 cho nghĩa vụ 100.000 vẫn OVERPAID/20.000 unapplied. Pure review rebuild dùng cùng helper và confirmed group ownership, không copy logic sang backend/frontend.

Oracle revision thuần tách payment/link/review: approve → FULL/CONFIRMED/APPROVED, reject → NO_CONFIRMED_RECEIPT/REJECTED/REJECTED, restored snapshot undo → UNKNOWN/PROPOSED/UNDONE. Test HTTP/PostgreSQL kiểm tra transaction/audit/idempotency/concurrency độc lập, không coi pure snapshot rewind là bằng chứng đã thử DB undo.

```powershell
uv run python research/classification_evaluation.py --output reports/lab/classification-candidate.json
uv run pytest tests/audit/test_payment_classification.py tests/api/test_reviews.py -q
uv run python scripts/qa_matching.py --output reports/lab/classification-http-oracles.json
uv run python scripts/qa_concurrency.py --url http://127.0.0.1:8002 --output reports/lab/classification-concurrency.json
```

Baseline được chạy bằng cùng runner, đặt `C:/Work/ReconcileEngine/src` trước editable source trong `sys.path`; JSON ghi path/hash/commit implementation để kiểm chứng nguồn. Nhãn chỉ dùng trong evaluator sau khi engine chạy. Không thay enum/allocation/matching policy để đạt accuracy; không sửa lại snapshot lịch sử đã lưu.

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
