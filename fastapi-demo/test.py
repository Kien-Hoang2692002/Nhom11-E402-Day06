import os
from dotenv import load_dotenv
from email_service import send_quotation_email

# Load biến môi trường
load_dotenv()

def test_send_email():
    # ⚠️ sửa email test của bạn tại đây
    to_email = "kien20205089@gmail.com"

    car_name = "VinFast VF8"
    car_price = "529.000.000đ"

    try:
        send_quotation_email(to_email, car_name, car_price)
        print("✅ Gửi email thành công!")
    except Exception as e:
        print("❌ Lỗi khi gửi email:")
        print(e)


if __name__ == "__main__":
    test_send_email()