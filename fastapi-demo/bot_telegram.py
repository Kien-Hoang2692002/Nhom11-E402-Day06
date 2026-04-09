import os
import asyncio
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Import graph agent bạn đã build
from agent import graph

load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Khởi tạo Bot và Dispatcher đúng chuẩn 3.x
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# Memory đơn giản theo user
user_sessions = {}

# =========================
# HELPER: Phân tích tin nhắn để rút trích ảnh
# =========================
def extract_images(text: str):
    """
    Rút trích các thẻ [IMAGE] url hoặc các link ảnh markdown và trả về text sạch + list urls.
    """
    # 1. Tìm thẻ [IMAGE] URL
    pattern_tag = r"(?i)\[IMAGE\]\s*(https?://[^\s\n\]\)]+)"
    urls_tag = re.findall(pattern_tag, text)
    
    # 2. Tìm link markdown ![alt](url) hoặc [alt](url) có đuôi là ảnh
    pattern_md = r"!?\[.*?\]\((https?://.*?\.(?:jpg|jpeg|png|webp|gif|bmp).*?)\)"
    urls_md = re.findall(pattern_md, text)
    
    # Gộp lại và lấy unique
    all_urls = list(dict.fromkeys(urls_tag + urls_md))
    
    # Xoá các thẻ và link khỏi văn bản
    clean_text = re.sub(pattern_tag, "", text)
    clean_text = re.sub(pattern_md, "", clean_text).strip()
    
    # Xoá cả những URL trần còn sót lại nếu chúng là ảnh
    for url in all_urls:
        clean_text = clean_text.replace(url, "").strip()
        
    return clean_text, all_urls

from aiogram.utils.media_group import MediaGroupBuilder

async def send_smart_response(message: types.Message, text: str):
    """
    Gửi tin nhắn thông minh: Hiển thị 1 ảnh đại diện kèm Caption
    """
    clean_text, urls = extract_images(text)
    
    # Vô hiệu hóa xem trước liên kết (link trần)
    link_preview = types.LinkPreviewOptions(is_disabled=True)
    
    if not urls:
        if clean_text:
            await message.answer(clean_text, link_preview_options=link_preview)
        return

    # Lấy ảnh đầu tiên làm ảnh chính
    main_image = urls[0]
    
    # Telegram giới hạn caption là 1024 ký tự
    if len(clean_text) < 1000:
        try:
            await message.answer_photo(
                photo=main_image, 
                caption=clean_text,
                link_preview_options=link_preview
            )
            # Nếu còn ảnh khác, gửi album (tối đa thêm 9 tấm)
            if len(urls) > 1:
                media_group = MediaGroupBuilder()
                for url in urls[1:10]:
                    media_group.add_photo(media=url)
                await message.answer_media_group(media=media_group.build())
        except Exception as e:
            # Fallback
            await message.answer(clean_text, link_preview_options=link_preview)
            for url in urls[:3]:
                try: await message.answer_photo(photo=url)
                except: pass
    else:
        # Nếu text quá dài, gửi riêng
        await message.answer(clean_text, link_preview_options=link_preview)
        media_group = MediaGroupBuilder()
        for url in urls[:10]:
            media_group.add_photo(media=url)
        try:
            if len(urls) > 1:
                await message.answer_media_group(media=media_group.build())
            else:
                await message.answer_photo(photo=main_image)
        except:
            pass

# =========================
# START
# =========================
@dp.message(Command("start"))
async def welcome(message: types.Message):
    await message.reply(
        "🚗 VinFast Advisor xin chào!\n"
        "Tôi sẽ hiển thị hình ảnh xe trực tiếp cho bạn."
    )

# =========================
# HANDLE MESSAGE
# =========================
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text

    if not user_input: return

    if user_id not in user_sessions:
        user_sessions[user_id] = []

    user_sessions[user_id].append(("human", user_input))
    waiting_msg = await message.answer("🤖 Đang lấy hình ảnh cho bạn...")

    try:
        result = graph.invoke({"messages": user_sessions[user_id]})
        response_text = result["messages"][-1].content
        
        # Lưu vào history (không lưu tag ảnh)
        clean_msg, _ = extract_images(response_text)
        user_sessions[user_id].append(("ai", clean_msg))

        await send_smart_response(message, response_text)
        
    except Exception as e:
        await message.answer(f"❌ Lỗi: {str(e)}")
    finally:
        try: await waiting_msg.delete()
        except: pass

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot stopped!")