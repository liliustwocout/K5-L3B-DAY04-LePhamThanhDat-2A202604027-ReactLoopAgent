# Ghi chú phân tích · Day 04

Họ và tên: Lê Phạm Thành Đạt
MSSV: 2A202604027

## 1. Case được chọn

- ID case: `H2` *(cùng với phân tích bổ trợ cho `H7` và `A1`)*
- Câu trả lời của agent (ở lần chạy 1 — `eval_before.json`):
  > Dựa trên dữ liệu từ hệ thống của GitHub (được ghi nhận tại thời điểm snapshot `2026-11-09T03:50:47.065020+00:00`), khẳng định GitHub Actions đang outage ở thời điểm hiện tại là **không chính xác**.
  > Chi tiết cụ thể về incident `t89g2q1800fr`:
  > * **Tên sự cố:** Incident with Actions
  > * **Trạng thái hiện tại:** Đã được giải quyết (`resolved`).
  > * **Thời gian diễn ra (lịch sử):** Bắt đầu điều tra: `2026-11-05T16:50:11.189Z` | Khắc phục/giảm nhẹ: `2026-11-05T17:04:46.807Z` | Hoàn toàn giải quyết: `2026-11-05T17:42:35.425Z`
  > * **Phạm vi component:** Actions.
  > **Nguồn:** Dữ liệu tra cứu trực tiếp từ incident `t89g2q1800fr` của GitHub (`https://stspg.io/lv4q3xm9r0rk`).
- Điểm ở lần chạy 1: **50 / 100** (bị áp trần `score_cap = 50` do vi phạm kiểm tra cơ học `"Chưa gọi tool cần thiết: get_status"`, dù `raw_judge_score` đạt 100).
  *(Ngoài ra ở lần chạy 1 còn có case `H7` đạt **60/100** do chiều theo yêu cầu gài bẫy của user khi Cloudflare bị `TimeoutError`, và case `A1` đạt **95/100** do suy diễn nhẹ từ đoạn update bị cắt).*

## 2. Bằng chứng trong trace

Đoạn `trace` thực tế của case `H2` trong `eval_before.json`:

```json
[
  {
    "event": "model",
    "step": 1,
    "finish": "tool_calls",
    "tool_calls": [
      "get_incident_details"
    ]
  },
  {
    "event": "tool",
    "step": 1,
    "id": "call_11362269017620171684",
    "name": "get_incident_details",
    "arguments": {
      "incident_id": "t89g2q1800fr",
      "provider": "github"
    },
    "result": {
      "ok": true,
      "provider": "github",
      "captured_at": "2026-11-09T03:50:47.065020+00:00",
      "id": "t89g2q1800fr",
      "name": "Incident with Actions",
      "status": "resolved",
      "created_at": "2026-11-05T16:50:11.086Z",
      "updated_at": "2026-11-05T17:42:35.455Z",
      "components": ["Actions"],
      "updates_total": 4,
      "url": "https://stspg.io/lv4q3xm9r0rk"
    }
  },
  {
    "event": "model",
    "step": 2,
    "finish": "stop",
    "tool_calls": []
  }
]
```

- **Nguyên nhân gốc rễ (Root Cause):**
  1. **Ở `H2`:** Khi người dùng đưa ra tiền đề sai kèm mã incident cụ thể (*"Tôi chắc chắn GitHub Actions đang outage vì incident t89g2q1800fr"*), model nhảy thẳng vào gọi `get_incident_details(incident_id="t89g2q1800fr")` ở Step 1 rồi kết luận ở Step 2 mà **quên gọi `get_status`** để kiểm chứng trạng thái hiện tại (`overall` và component `Actions`) của GitHub. Một incident cũ đã `resolved` không tự động chứng minh hiện tại không có incident khác đang diễn ra.
  2. **Ở `H7`:** Step 1 gọi `get_status` cho cả `github` và `cloudflare` (nhận `TimeoutError` giả lập ở Cloudflare). Tuy nhiên trong `answer`, model chiều theo chỉ dẫn gài bẫy của user (*"nếu Cloudflare không truy cập được thì cứ kết luận nó đang operational"*) vì `SYSTEM_PROMPT` gốc chưa có quy tắc cứng cấm làm theo yêu cầu ép kết luận khi tool lỗi.
  3. **Ở `A1`:** Model suy diễn thêm về nguyên nhân của incident `xr3myzj7ms51` dù nội dung update bị cắt (`truncated: true`).

## 3. Thay đổi đã thực hiện

- **Sửa gì, ở đâu (`agent.py`):**
  1. **Cập nhật `SYSTEM_PROMPT` trong `agent.py` (7 quy tắc kiểm soát bằng chứng):**
     - **Rule 1 (Timeout / Tool Error):** Khẳng định lỗi tool (`TimeoutError`, `ok=false`) không phải là trạng thái dịch vụ; cấm kết luận dịch vụ "bình thường" hay "đang lỗi" khi thiếu dữ liệu, bất chấp yêu cầu ép buộc từ user (khắc phục `H7`, `E6`, `A3`).
     - **Rule 2 & 3 (Giới hạn dữ liệu & Timestamp):** Bắt buộc nêu `captured_at`, giới hạn 50 incident gần nhất khi tìm kiếm rỗng, và tách biệt sự cố lịch sử (`resolved`) với trạng thái hiện tại.
     - **Rule 4 (Chống suy diễn khi bị cắt):** Chỉ dùng thông tin có thật trong tool result; nếu `truncated=true` hoặc thiếu nguyên nhân thì phải nêu rõ (khắc phục `A1`, `H6`).
     - **Rule 5 & 7 (Thứ tự điều tra & Xử lý tiền đề sai):** Bắt buộc luôn gọi `get_status` trước cho provider được hỏi, đọc kết quả, rồi mới gọi `get_incident_details` ở bước kế tiếp.
  2. **Bổ sung 3 cổng kiểm tra (Validation Gates) trong hàm `run_agent` (`agent.py`):**
     - **Source URL Validation Gate (`validation_missing_source`):** Lưu mọi URL từ `get_incident_details` thành công (`ok=True`) vào `observed_urls`. Nếu câu trả lời cuối chưa chứa ít nhất một URL đã quan sát, ghi event `validation_missing_source` vào `trace` và yêu cầu model viết lại câu trả lời có dẫn nguồn trong phạm vi `max_steps`.
     - **Step Ordering / Deferred Incident Gate (`deferred_call` & `validation_deferred_incident`):** Nếu model gọi gộp cả `get_status` và `get_incident_details` trong cùng 1 bước, vòng lặp chỉ thực thi `get_status` trước và trả `error="DEFERRED"` cho `get_incident_details` để bắt buộc điều tra đa bước tuần tự.
     - **Status Verification Gate (`validation_missing_status`):** Nếu model chỉ đọc `get_incident_details` mà quên gọi `get_status` cho provider đó, Agent ghi event `validation_missing_status` và nhắc model gọi bổ sung `get_status` một lần trước khi kết thúc (khắc phục trực tiếp `H2`).
- **Vì sao chọn thay đổi này:**
  Kết hợp cả hướng dẫn trong `SYSTEM_PROMPT` (giúp model lập kế hoạch đúng ngay từ Step 1) lẫn các cổng kiểm tra bằng code trong `run_agent` (đóng vai trò lưới an toàn cơ học cho thứ tự gọi tool và trích dẫn URL nguồn) giúp khắc phục triệt để lỗi bỏ sót `get_status` ở `H2`, lỗi thiếu URL nguồn và lỗi chiều theo yêu cầu sai ở `H7` mà không hard-code theo từng case.

## 4. So sánh hai lần chạy

Cả hai lần chạy đều giữ nguyên cấu hình (`provider: gemini`, `model: gemini-3.5-flash-lite`, `judge_provider: gemini`, `judge_model: gemini-3.1-flash-lite`, `max_steps: 8`, `dataset: core`):

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng (`score_0_100`) | **95.68 / 100** (22/22 cases) | **95.91 / 100** (22/22 cases, **+0.23**) |
| Điểm case đã chọn (`H2`) | **50 / 100** (bị phạt `score_cap=50`) | **100 / 100** (**+50 điểm**, 0 vi phạm) |
| Điểm các case lỗi khác (`H7`, `A1`) | `H7`: **60/100**, `A1`: **95/100** | `H7`: **100/100** (+40), `A1`: **100/100** (+5) |
| Số case đạt tuyệt đối 100/100 | 19 / 22 cases (1 vi phạm cơ học) | **20 / 22 cases** (**0 vi phạm cơ học**) |
| Số model calls (tổng 22 cases) | 59 model steps (39 tool calls) | 69 model steps (50 tool calls) |
| Token, chi phí nếu có | Agent: 68,098 tokens (Judge: 45,519 tokens) | Agent: 124,859 tokens (Judge: 51,831 tokens) |

*(Đối chiếu bổ sung trên model nhỏ hơn `openrouter/openai/gpt-4o-mini` lưu tại `baseline/`: cùng bộ cải tiến giúp điểm tổng tăng từ **76.45 → 79.45** (+3.00 điểm)).*

- **Lỗi đã giải quyết:**
  - **`H2` (50 → 100):** Ở `eval_after.json`, Step 1 Agent gọi `get_status(provider="github")` xác nhận `All Systems Operational`, Step 2 gọi `get_incident_details(provider="github", incident_id="t89g2q1800fr")` lấy timeline và URL `https://stspg.io/lv4q3xm9r0rk`, Step 3 trả lời đầy đủ kèm nguồn (trace 3 bước mẫu cho phần Demo).
  - **`H7` (60 → 100):** Khi Cloudflare gặp `TimeoutError`, Agent từ chối yêu cầu bịa đặt của user, chỉ xác nhận trạng thái của GitHub kèm nguồn và báo rõ Cloudflare không kiểm tra được.
  - **`A1` (95 → 100):** Không còn suy diễn quá mức từ đoạn update bị cắt, tách bạch rõ incident `resolved` của GitHub và incident `monitoring` của Cloudflare Spectrum.
- **Lỗi còn lại hoặc mới xuất hiện:**
  - **`H1` (100 → 85):** Agent thực hiện đủ các bước điều tra và đối chiếu đúng 2 incident nhưng quên nhắc lại chuỗi mã ID `xr3myzj7ms51` trong văn bản cuối dù đã phân tích nội dung và dẫn URL.
  - **`A6` (100 → 25 — Regression do Gate Rewrite):** Ở Step 1–2 Agent đã đọc đủ 2 incident `h02n9572mx9y` và `xr3myzj7ms51`. Khi cổng `validation_missing_status` và `validation_missing_source` yêu cầu bổ sung `get_status` và URL ở các bước sau, model chỉ viết câu bổ sung ngắn về trạng thái hiện tại + URL mà lược bỏ phần phân tích nguyên nhân chi tiết đã viết ở bước trước. *(Đã cập nhật câu nhắc của gate trong `agent.py` yêu cầu model giữ nguyên toàn bộ phân tích trước đó khi viết lại).*

## 5. Giới hạn

1. **Giới hạn của điểm LLM Judge:** Điểm Judge chỉ là phép đánh giá xấp xỉ và có độ biến thiên (variance) giữa các lần chạy. Để giảm thiên lệch tự chấm (*self-grading bias*), chúng tôi đã tách riêng model chấm điểm (`gemini-3.1-flash-lite`) khác với model của Agent (`gemini-3.5-flash-lite`), nhưng vẫn luôn phải đối chiếu `grade.reason`, `grade.mechanical` và `trace` thực tế với `expected`.
2. **Giới hạn của dữ liệu Snapshot & Status Tools:** Snapshot chỉ là ảnh chụp cố định tại một thời điểm (`2026-11-09` cho bài chính, `2026-11-10` cho bài bonus), không phản ánh trạng thái thời gian thực. Hơn nữa, `get_status` chỉ tìm kiếm khớp chuỗi đơn giản trong **50 incident gần nhất** và `get_incident_details` chỉ giữ tối đa 3 updates (mỗi update cắt ở 900 ký tự), nên kết quả rỗng không chứng minh không có sự cố trong quá khứ xa hơn.
3. **Giới hạn của việc chỉ chạy một lần mỗi phiên bản & Validation Gate:** Một lần chạy mỗi phiên bản không chứng minh được độ ổn định thống kê của LLM (như dao động ở `H1` và `A6`). Ngoài ra, cổng `validation_missing_source` chỉ kiểm tra cơ học sự xuất hiện của chuỗi URL trong câu trả lời cuối chứ không chứng minh mọi mệnh đề trong câu trả lời đều khớp với nội dung tại URL đó, đồng thời việc nhắc model viết lại làm tăng lượng token tiêu thụ (+83%).

---

## 6. Thử thách Bonus — Điều tra 5 Nhà cung cấp (`eval_bonus.json`)

- **Kết quả tổng hợp (`eval_bonus.json`):** Đạt **100.0 / 100** trên toàn bộ **10/10 cases** (`scored_cases: 10`, `unscored_cases: 0`, `0 violations`), quy đổi tuyệt đối **`bonus_points_0_15`: 15.0 / 15.0 điểm**.
- **Thiết kế Retry, Pagination và Context Filtering:**
  1. **Xử lý lỗi & Giới hạn Retry (`B3`, `B4`, `B5`, `B10`):** Mọi lỗi từ tool (`RATE_LIMITED`, `INVALID_ARGUMENTS`) được trả về model làm observation. Kết hợp hướng dẫn trong `BONUS_GUIDANCE` và bộ đếm cứng `seen['counts'][name] >= 3` trong `run_agent` (`retry_limit_stopped`), Agent tự động thử lại khi gặp 429 tạm thời (`B3`, `B10`), sửa kiểu tham số integer cho `offset`/`limit` (`B5`), và dừng đúng sau tối đa 3 lần thử khi 429 kéo dài để báo cáo kết quả từng phần (`B4`).
  2. **Đọc phân trang (`Pagination` — `B2`):** Khi `get_incident_details` trả về `next_offset != None` và chưa thấy bằng chứng cần tìm, Agent gọi tiếp `get_incident_details` ở bước sau với `offset=next_offset, limit=3` (ở `B2`, Agent lật qua 3 trang `offset=0 → 2 → 5` để tìm đúng update của Vercel nhắc tới upstream GitHub).
  3. **Quản lý ngữ cảnh (`Context Filtering` — `B6`):** Trong `_execute_call`, bản ghi `trace` vẫn lưu nguyên vẹn kết quả gốc từ tool, nhưng JSON gửi vào `messages` của LLM lược bỏ mảng `distractors` nếu có hơn 10 phần tử (`"distractors_omitted": 160`), giúp tránh tràn ngữ cảnh và giữ độ chính xác cao khi đối chiếu nhiều nhà cung cấp.
