import asyncio
from fastapi import FastAPI
from bot_telegram import dp, bot

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    # Chạy Polling của Bot khi FastAPI khởi động
    asyncio.create_task(dp.start_polling())

@app.get("/")
async def root():
    return {"status": "Bot is running"}

@app.get("/update-prices")
async def update_prices():
    # Endpoint để bạn chủ động kích hoạt cào lại dữ liệu
    from scraper import crawl_vinfast_prices
    msg = crawl_vinfast_prices()
    return {"message": msg}