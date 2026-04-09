import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from bot_telegram import dp, bot
from agent import graph

from dotenv import load_dotenv

load_dotenv()

# =========================
# LIFESPAN (Quản lý khởi tạo và đóng bot)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Hành động khi Startup ---
    print("🚀 Starting Telegram Bot...")
    
    # Xóa webhook cũ (nếu có) và bắt đầu polling trong background
    await bot.delete_webhook(drop_pending_updates=True)
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    yield  # FastAPI chạy ở đây
    
    # --- Hành động khi Shutdown ---
    print("🛑 Shutting down Bot...")
    bot_task.cancel()  # Dừng polling
    await bot.session.close() # Đóng kết nối bot an toàn

def send_telegram_notification(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"❌ Lỗi gửi Telegram: {e}")
        return None

app = FastAPI(lifespan=lifespan)

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
async def root():
    return {"status": "Bot + API đang chạy OK"}

# =========================
# CHAT WITH AGENT (TEST API)
# =========================
@app.get("/chat")
async def chat(query: str):
    try:
        # Lưu ý: Invoke có thể là blocking nếu agent chạy nặng, 
        # nhưng trong ví dụ này ta giữ nguyên logic của bạn
        result = graph.invoke({
            "messages": [("human", query)]
        })
        final = result["messages"][-1].content

        return {
            "query": query,
            "response": final
        }
    except Exception as e:
        return {"error": str(e)}

# =========================
# TRIGGER SCRAPER (BACKGROUND)
# =========================
@app.get("/crawl-data")
async def crawl_data():
    # Import bên trong để tránh lỗi vòng lặp import (circular import)
    from calldata import main as crawl_main

    try:
        # Chạy task nền là đúng, nhưng nên dùng task để không block request
        asyncio.create_task(crawl_main())
        return {"message": "🚀 Đang crawl dữ liệu dưới nền (background)"}
    except Exception as e:
        return {"error": str(e)}
    
@app.get("/vnpay-return")
async def vnpay_return(request: Request):
    params = dict(request.query_params)

    if params.get("vnp_ResponseCode") == "00":
        # Thanh toán thành công
        print("✅ Thanh toán thành công")

        # Gửi Telegram
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🎉 Thanh toán thành công! Xe của bạn đang được xử lý."
        )

        return {"message": "Success"}

    return {"message": "Failed"}

@app.post("/webhook/vietqr")
async def vietqr_callback(request: Request):
    data = await request.json()
    
    # Giả lập dữ liệu VietQR gửi về
    # data = {"amount": 10000000, "content": "VINFAST123", "status": "SUCCESS"}
    
    status = data.get("status")
    amount = data.get("amount")
    content = data.get("content")

    if status == "SUCCESS":
        # 1. Tạo nội dung tin nhắn thật kêu
        msg = (
            f"<b>💰 TING TING! NHẬN TIỀN CỌC MỚI</b>\n"
            f"--------------------------\n"
            f"👤 Khách hàng: Kiên\n"
            f"💵 Số tiền: {amount:,.0f} VNĐ\n"
            f"📝 Nội dung: {content}\n"
            f"✅ <b>Trạng thái: Thành công</b>"
        )
        
        # 2. Gửi ngay cho chính mình
        send_telegram_notification(msg)
        
        return {"code": "00", "message": "Done"}
    
    return {"code": "01", "message": "Fail"}