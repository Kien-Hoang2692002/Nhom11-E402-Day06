import os
import asyncio
import json
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.media_group import MediaGroupBuilder
from dotenv import load_dotenv

from agent import graph

load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

user_sessions = {}
user_states = {}

def extract_images(text: str):
    pattern_tag = r"(?i)\[IMAGE\]\s*(https?://[^\s\n\]\)]+)"
    urls_tag = re.findall(pattern_tag, text)
    pattern_md = r"!?\[.*?\]\((https?://.*?\.(?:jpg|jpeg|png|webp|gif|bmp).*?)\)"
    urls_md = re.findall(pattern_md, text)
    all_urls = list(dict.fromkeys(urls_tag + urls_md))
    clean_text = re.sub(pattern_tag, "", text)
    clean_text = re.sub(pattern_md, "", clean_text).strip()
    for url in all_urls:
        clean_text = clean_text.replace(url, "").strip()
    return clean_text, all_urls

async def send_smart_response(message: types.Message, text: str, reply_markup=None):
    clean_text, urls = extract_images(text)
    link_preview = types.LinkPreviewOptions(is_disabled=True)
    if not urls:
        if clean_text:
            await message.answer(clean_text, link_preview_options=link_preview, reply_markup=reply_markup)
        return
    main_image = urls[0]
    if len(clean_text) < 1000:
        try:
            await message.answer_photo(photo=main_image, caption=clean_text, reply_markup=reply_markup)
            if len(urls) > 1:
                media_group = MediaGroupBuilder()
                for url in urls[1:10]:
                    media_group.add_photo(media=url)
                await message.answer_media_group(media=media_group.build())
        except Exception:
            await message.answer(clean_text, link_preview_options=link_preview, reply_markup=reply_markup)
            for url in urls[:3]:
                try: await message.answer_photo(photo=url)
                except: pass
    else:
        await message.answer(clean_text, link_preview_options=link_preview, reply_markup=reply_markup)
        media_group = MediaGroupBuilder()
        for url in urls[:10]:
            media_group.add_photo(media=url)
        try:
            if len(urls) > 1: await message.answer_media_group(media=media_group.build())
            else: await message.answer_photo(photo=main_image)
        except: pass


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🚗 Xin chào! Tôi là VinFast Advisor.\nBạn cần tìm xe gì, với ngân sách khoảng bao nhiêu?")

@dp.callback_query(F.data.startswith('url_sales_'))
async def process_sales_url(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    car_id = callback_query.data.replace('url_sales_', '')
    await bot.answer_callback_query(callback_query.id)
    sys_msg = f"[SYSTEM] User clicked Nhận tư vấn for car {car_id}"
    if user_id not in user_sessions: user_sessions[user_id] = []
    user_sessions[user_id].append(("human", sys_msg))
    user_states[user_id] = {"status": "AWAITING_EMAIL", "car_id": car_id}
    try:
        result = graph.invoke({"messages": user_sessions[user_id]})
        final_msg = result["messages"][-1].content
        user_sessions[user_id].append(("ai", final_msg))
        await callback_query.message.answer(final_msg)
    except Exception: pass

@dp.callback_query(F.data.startswith('skip_'))
async def process_skip(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    car_id = callback_query.data.replace('skip_', '')
    await bot.answer_callback_query(callback_query.id, text="Đã ghi nhận, bạn muốn xem xe khác ạ?")
    sys_msg = f"[SYSTEM] User skipped car {car_id}. I need to apologize and ask for budget again."
    if user_id in user_sessions: user_sessions[user_id].append(("human", sys_msg))
    user_states[user_id] = None
    await callback_query.message.answer("Bạn có muốn xem dòng xe khác không? Xin hãy nhập lại mức ngân sách.")


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text
    if not user_input: return

    # Xử lý luồng xin Email trước (nếu đang chờ email)
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', user_input.strip())
    state_info = user_states.get(user_id)
    is_awaiting = isinstance(state_info, dict) and state_info.get("status") == "AWAITING_EMAIL"

    if email_match:
        email_address = email_match.group(0)
        car_id = state_info.get("car_id") if is_awaiting else None
        
        from tools import normalize_data
        cars = normalize_data()
        if not car_id and user_id in user_sessions:
            recent_texts = [msg for role, msg in user_sessions[user_id][-5:] if isinstance(msg, str)]
            history = " ".join(recent_texts).lower() + " " + user_input.lower()
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
                await asyncio.to_thread(send_quotation_email, to_email=email_address, car_name=car_info['name'], car_price_str=str(car_info['price']))
                await message.answer(f"✅ Báo giá mẫu xe **{car_info['name']}** đã được gửi thành công đến địa chỉ `{email_address}`! \n\nQuý khách vui lòng kiểm tra hộp thư đến (hoặc Spam). Xin cảm ơn!", parse_mode="Markdown")
            except Exception as e:
                await message.answer(f"❌ Rất tiếc, đã có lỗi kết nối khi gửi Email: {str(e)}\n*(Hãy đảm bảo bạn đã điền chính xác tài khoản SMTP/Gmail App Password)*", parse_mode="Markdown")
            user_states[user_id] = None
            return
        elif is_awaiting:
            await message.answer("Địa chỉ Email không hợp lệ. Bạn vui lòng kiểm tra lại định dạng nhé (VD: abc@gmail.com).")
            return

    # Nếu không phải email -> trò chuyện bình thường với Bot
    if user_id not in user_sessions: user_sessions[user_id] = []
    user_sessions[user_id].append(("human", user_input))
    waiting_msg = await message.answer("🤖 Đang xử lý...")

    try:
        result = graph.invoke({"messages": user_sessions[user_id]})
        response_text = result["messages"][-1].content
        clean_msg, _ = extract_images(response_text)
        user_sessions[user_id].append(("ai", clean_msg))

        # Nếu Bot trả về form thẻ đặc biệt (RECOMMEND CARD)
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and data.get("type") == "card":
                builder = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Nhận tư vấn", callback_data=f"url_sales_{data['car_id']}")],
                    [InlineKeyboardButton(text="⏭ Bỏ qua", callback_data=f"skip_{data['car_id']}")]
                ])
                caption = f"🚗 **{data.get('name', 'VinFast')}**\n💰 Giá: {data.get('price', 'N/A')}\n📝 {data.get('desc', '')}"
                await waiting_msg.edit_text(caption, reply_markup=builder, parse_mode="Markdown")
                return
        except ValueError:
            pass 

        await waiting_msg.delete()
        
        # Lấy markup tuỳ chọn (quét xem AI có nhắc đến xe nào không thì hiển thị nút Hỏi giá luôn)
        from tools import normalize_data
        cars = normalize_data()
        markup = None
        for c in sorted(cars, key=lambda x: len(x['id']), reverse=True):
            if c['name'].lower() in response_text.lower() or c['id'] in response_text.lower():
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Nhận tư vấn (Gửi Email)", callback_data=f"url_sales_{c['id']}")]
                ])
                break

        # In text trả về bình thường, lọc smart images
        await send_smart_response(message, response_text, reply_markup=markup)
        
    except Exception as e:
        try:
            await waiting_msg.edit_text(f"❌ Có lỗi xảy ra: {str(e)}")
        except Exception:
            await message.answer(f"❌ Có lỗi xảy ra: {str(e)}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot stopped!")