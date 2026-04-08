import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from bot_telegram import dp, bot
from agent import graph

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