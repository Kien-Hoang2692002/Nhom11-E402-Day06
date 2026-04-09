import os
import asyncio
import json
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
user_states = {} # Dùng lưu state Handoff

# =========================
# START
# =========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚗 Xin chào! Tôi là VinFast Advisor.\n"
        "Bạn cần tìm xe gì, với ngân sách khoảng bao nhiêu?"
    )

# =========================
# CALLBACK QUERY (NÚT BẤM)
# =========================
@dp.callback_query(F.data.startswith('url_sales_'))
async def process_sales_url(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    car_id = callback_query.data.replace('url_sales_', '')
    await bot.answer_callback_query(callback_query.id)
    
    # Ép System Context đánh lừa Agent rằng người dùng đã nhấn Nhận tư vấn
    sys_msg = f"[SYSTEM] User clicked Nhận tư vấn for car {car_id}"
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    user_sessions[user_id].append(("human", sys_msg))
    
    # Turn on State
    user_states[user_id] = {"status": "AWAITING_EMAIL", "car_id": car_id}
    
    try:
        # Nhờ AI Replying "Xin SĐT..." dựa theo system prompt
        result = graph.invoke({"messages": user_sessions[user_id]})
        final_msg = result["messages"][-1].content
        user_sessions[user_id].append(("ai", final_msg))
        await callback_query.message.answer(final_msg)
    except Exception as e:
        pass


@dp.callback_query(F.data.startswith('skip_'))
async def process_skip(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    car_id = callback_query.data.replace('skip_', '')
    await bot.answer_callback_query(callback_query.id, text="Đã ghi nhận, bạn muốn xem xe khác ạ?")
    
    # Ép System Context cập nhật skip training logic
    sys_msg = f"[SYSTEM] User skipped car {car_id}. I need to apologize and ask for budget again."
    if user_id in user_sessions:
        user_sessions[user_id].append(("human", sys_msg))
    
    user_states[user_id] = None # Reset luồng về mặc định
    await callback_query.message.answer("Bạn có muốn xem dòng xe khác không? Xin hãy nhập lại mức ngân sách.")


# =========================
# HANDLE TEXT MESSAGE
# =========================
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text

    # Quét xem người dùng có gõ Email vào không (Dù họ bấm nút hay tự gõ tay)
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', user_input.strip())
    state_info = user_states.get(user_id)
    is_awaiting = isinstance(state_info, dict) and state_info.get("status") == "AWAITING_EMAIL"

    if email_match:
        email_address = email_match.group(0)
        car_id = state_info.get("car_id") if is_awaiting else None
        
        from tools import normalize_data
        cars = normalize_data()
        
        # Fallback: Trực tiếp tìm xe dựa vào 5 tin nhắn gần nhất nếu không bấm nút
        if not car_id and user_id in user_sessions:
            recent_texts = [msg for role, msg in user_sessions[user_id][-5:] if isinstance(msg, str)]
            history = " ".join(recent_texts).lower() + " " + user_input.lower()
            
            # Sắp xếp theo độ dài ID xe giảm dần để tránh trùng (ví dụ vf6 và vf6plus)
            for c in sorted(cars, key=lambda x: len(x['id']), reverse=True):
                if c['id'] in history or c['name'].lower() in history:
                    car_id = c['id']
                    break

        if car_id:
            car_info = next((c for c in cars if c['id'] == car_id), None)
            
            if not car_info:
                await message.answer("Rất tiếc, dữ liệu xe này đang có lỗi.")
                user_states[user_id] = None
                return

            await message.answer("🔄 *Hệ thống đang soạn báo giá lăn bánh và gửi qua Email...*", parse_mode="Markdown")
            
            from email_service import send_quotation_email
            try:
                # Gửi Email phi đồng bộ
                await asyncio.to_thread(
                    send_quotation_email,
                    to_email=email_address,
                    car_name=car_info['name'],
                    car_price_str=str(car_info['price'])
                )
                await message.answer(f"✅ Báo giá mẫu xe **{car_info['name']}** đã được gửi thành công đến địa chỉ `{email_address}`! \n\nQuý khách vui lòng kiểm tra hộp thư đến (hoặc Spam). Xin cảm ơn!", parse_mode="Markdown")
            except Exception as e:
                await message.answer(f"❌ Rất tiếc, đã có lỗi kết nối khi gửi Email: {str(e)}\n*(Hãy đảm bảo bạn đã điền chính xác tài khoản SMTP/Gmail App Password vào file .env)*", parse_mode="Markdown")

            # Trở lại luồng bình thường sau khi xử lý xong
            user_states[user_id] = None
            return
        elif is_awaiting:
            await message.answer("Địa chỉ Email không hợp lệ. Bạn vui lòng kiểm tra lại định dạng nhé (VD: abc@gmail.com).")
            return
        # Nếu ko trong state awaiting và ko tìm ra xe thì coi như text bình thường cho LLM xử lý

    # Lấy lịch sử chat (memory)
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    user_sessions[user_id].append(("human", user_input))
    waiting_msg = await message.answer("🤖 Đang xử lý...")

    # Gọi AI Agent
    try:
        result = graph.invoke({
            "messages": user_sessions[user_id]
        })
        final_msg = result["messages"][-1].content
        user_sessions[user_id].append(("ai", final_msg))

        # Phân rã xem tin nhắn có phải JSON Recommendation Card không
        try:
            data = json.loads(final_msg)
            if isinstance(data, dict) and data.get("type") == "card":
                
                builder = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Nhận tư vấn", callback_data=f"url_sales_{data['car_id']}")],
                    [InlineKeyboardButton(text="⏭ Bỏ qua", callback_data=f"skip_{data['car_id']}")]
                ])
                
                caption = f"🚗 **{data.get('name', 'VinFast')}**\n💰 Giá: {data.get('price', 'N/A')}\n📝 {data.get('desc', '')}"
                
                # Hiển thị Card bằng Text + Button thay vì Image vì không có Image Link tiêu chuẩn
                await waiting_msg.edit_text(caption, reply_markup=builder, parse_mode="Markdown")
                return
        except ValueError:
            pass # Lỗi parse Json nghĩa là text thường

        # Gửi phản hồi cuối cùng (Text thường)
        await waiting_msg.edit_text(final_msg)
        
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Có lỗi xảy ra: {str(e)}")

# =========================
# RUN BOT
# =========================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")