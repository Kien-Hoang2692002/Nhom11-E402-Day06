import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv

# Import graph agent bạn đã build
from agent import graph

load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Khởi tạo Bot và Dispatcher đúng chuẩn 3.x
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Memory đơn giản theo user
user_sessions = {}

# =========================
# START (Sửa syntax Command)
# =========================
@dp.message(Command("start"))
async def welcome(message: types.Message):
    await message.reply(
        "🚗 Xin chào! Tôi là VinFast Advisor\n\n"
        "Bạn có thể hỏi:\n"
        "- Tôi có 500 triệu nên mua xe gì?\n"
        "- So sánh VF6 và VF8\n"
        "- Xe máy điện nào rẻ nhất?"
    )

# =========================
# HANDLE MESSAGE (Sửa syntax handler)
# =========================
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text

    # Lấy lịch sử chat (memory)
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    user_sessions[user_id].append(("human", user_input))

    # Trong aiogram 3, message.answer trả về message object, ta có thể dùng để xóa/edit sau này
    await message.answer("🤖 Đang tư vấn cho bạn...")

    # Gọi AI Agent
    try:
        result = graph.invoke({
            "messages": user_sessions[user_id]
        })

        # Lấy nội dung tin nhắn cuối cùng từ Agent
        final_msg = result["messages"][-1].content

        # Lưu lại response vào bộ nhớ
        user_sessions[user_id].append(("ai", final_msg))

        # Gửi phản hồi cuối cùng
        await message.answer(final_msg)
        
    except Exception as e:
        await message.answer(f"❌ Có lỗi xảy ra: {str(e)}")

# TASK: start - Bắt đầu tư vấn xe
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚗 Chào mừng bạn đến với VinFast Advisor!\n"
        "Tôi có thể giúp bạn chọn xe, tra giá hoặc giải đáp kỹ thuật.\n"
        "Dùng /tu_van để bắt đầu hỏi đáp AI."
    )

# TASK: gia_xe - Sử dụng Agent để lấy bảng giá mới nhất
@dp.message(Command("gia_xe"))
async def cmd_gia_xe(message: types.Message):
    # 1. Gửi thông báo chờ để User không cảm thấy bot bị treo
    waiting_msg = await message.answer("📊 Đang truy xuất bảng giá mới nhất từ hệ thống...")

    try:
        result = graph.invoke({
            "messages": [("human", "Hãy tổng hợp bảng giá các dòng xe VinFast hiện tại (VF5, VF6, VF7, VF8, VF9, VFe34)")]
        })

        final_answer = result["messages"][-1].content
        await message.answer(final_answer, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Lỗi khi lấy bảng giá từ AI: {str(e)}")
    finally:
        await waiting_msg.delete()

# TASK: tu_van - Chat với AI
@dp.message(Command("tu_van"))
async def cmd_tu_van(message: types.Message):
    await message.answer("🤖 Chế độ tư vấn AI đã sẵn sàng. Bạn hãy đặt câu hỏi về dòng xe bạn quan tâm nhé!")

# TASK: update - Cập nhật dữ liệu (Admin)
@dp.message(Command("update"))
async def cmd_update(message: types.Message):
    # Kiểm tra nếu đúng là ID của bạn (Admin) mới cho chạy
    # if message.from_user.id == YOUR_ADMIN_ID:
    await message.answer("🔄 Đang tiến hành cập nhật dữ liệu mới nhất từ hệ thống...")
    # Gọi hàm crawl data ở đây
    from calldata import main as crawl_main
    asyncio.create_task(crawl_main())

# =========================
# RUN BOT
# =========================
async def main():
    # Xóa webhook cũ nếu có để tránh xung đột
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")