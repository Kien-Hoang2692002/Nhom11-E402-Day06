# 🚗 VinFast Advisor Telegram Bot (Prototype)

Một trợ lý ảo Telegram (Chatbot) tích hợp Trí tuệ Nhân tạo thế hệ mới (LLM) hỗ trợ tư vấn mua xe VinFast. Dự án sử dụng hệ thống luồng LangGraph để điều phối kịch bản một cách thông minh, ngăn chặn AI "ảo giác" và có khả năng tự động soạn, gửi báo giá chi tiết lăn bánh thẳng vào Email thực của khách hàng.

---

## ✨ Tính Năng Nổi Bật

1. **Smart Matching Logic:** Tự động lọc xe khớp với khả năng tài chính của khách. Nếu ngân sách khách không bù nổi xe rẻ nhất, bot tự bẻ lái mời mua trả góp.
2. **Luồng hội thoại cưỡng bức (State-Machine):** Buộc người dùng và AI đi qua các bước làm rõ nhu cầu: Nhập budget -> Xác nhận thuế/pin -> Ưu tiên Rộng rãi hay Hiệu năng -> Báo kết quả.
3. **Rich UI Rendering:** Trích xuất ảnh ngoại thất chính xác và ném thành Album Media Group lên Telegram. Sinh nút bấm "🎯 Nhận tư vấn (Gửi Email)" đính kèm Card Form chuyên nghiệp.
4. **Auto Quotation Mailer (Real Email):** Khi khách chốt xe và gõ Email, hệ thống quét bắt Email bằng Regex. Module `email_service` sẽ âm thầm nhận lệnh tạo bảng tính HTML tính Thuế, Biển số và tự gửi bằng SMTP đi thẳng hộp thư của khách, sau tự động trả bot lại luồng trò chuyện bình thường.

## 🛠️ Công Nghệ Sử Dụng

- Lõi AI: Ngôn ngữ **Python**, thư viện **LangChain** & **LangGraph**
- Model: **GPT-4o-mini**
- Nền tảng Bot: **Aiogram v3**
- Gửi mail tự động: `smtplib` + MIME (Python Standard Library)

---

## 🚀 Hướng Dẫn Cài Đặt (Local)

### 1. Chuẩn bị Môi trường
Tải dự án và di chuyển vào thư mục dự án:
```bash
# Đổi thư mục nếu cần thiết
cd fastapi-demo
```

Tạo một môi trường ảo (Khuyến nghị) và cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt

playwright install chromium
```

### 4. Run project
```bash
python agent.py
```

### 5. Run fastapi
```bash
python bot_telegram.py
```
Bạn sẽ thấy thông báo Bot đang chạy. Lúc này lên Telegram tìm đúng tên Bot của bạn, gõ lệnh `/start` và test thử *"Tôi có khoảng 600 củ mua xe gì..."* để tận hưởng thành quả.

---

## 📂 Cơ cấu Tệp Lõi

Dự án này sử dụng mô hình Module hóa để dễ dàng mở rộng và tái sử dụng mã sau này:
- `bot_telegram.py`: Lớp chặn cửa ngoài cùng. Xử lý Telegram Update, Callback Query, Regex tóm email khách hàng, và hàm tối ưu nhúng gửi Ảnh thông minh kèm theo tin nhắn.
- `agent.py`: Trái tim AI. Chứa cụm kiến trúc đồ thị hội thoại LangGraph.
- `system_prompt.txt`: Chứa toàn bộ Prompt hệ thống ép luồng và bắt LLM phải tuân thủ nghiêm ngặt kỹ năng Sale.
- `tools.py`: Cung cấp 6 Tools thông minh cho AI - Điển hình: `analyze_user_budget`, tính năng lọc rác để lấy 12 tấm ảnh cực sắc nét `extract_images`, `search_vinfast_live`. Rút xuất thông tin siêu chi tiết.
- `email_service.py`: Module giả lập tính giá lăn bánh theo quy định thực tế và gửi thẳng kết quả chuẩn HTML vào Inbox Socket.
- `vinfast_data.json`: Storage (Cơ sở dữ liệu) giả lập.

---
*Dự án thuộc Nhóm 11 - AI Thực Chiến 2026*
