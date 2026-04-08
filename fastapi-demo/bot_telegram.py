from aiogram import Bot, Dispatcher, types
from recommender import VinFastRecommender

API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
recommender = VinFastRecommender()

@dp.message_handler(commands=['start'])
async def welcome(message: types.Message):
    await message.reply("Chào Kiên! Bạn muốn tìm xe VinFast trong tầm giá bao nhiêu hoặc cho mục đích gì?")

@dp.message_handler()
async def handle_message(message: types.Message):
    user_input = message.text
    # Gọi AI để tìm xe phù hợp
    suggestions = recommender.get_recommendation(user_input)
    
    response = "Dựa trên nhu cầu của bạn, tôi gợi ý:\n\n"
    for car in suggestions:
        response += f"🚗 {car['name']}\n💰 Giá: {car['price']:,} VNĐ\n📝 {car['desc']}\n---\n"
    
    await message.answer(response)