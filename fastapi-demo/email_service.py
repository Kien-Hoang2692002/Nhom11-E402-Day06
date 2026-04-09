import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def calculate_mock_rolling_price(base_price_str: str) -> dict:
    """
    Tính nháp giá lăn bánh.
    Base price e.g. "529.000.000đ" -> integer -> calculate -> back to strings.
    """
    try:
        # Lọc lấy số
        clean_str = ''.join(filter(str.isdigit, base_price_str))
        base_price = int(clean_str)
        
        vat_fee = int(base_price * 0.1) # Giả lập 10%
        plate_fee = 20000000            # Giả lập 20tr tiền biển
        reg_fee = 340000                # Phí đăng kiểm
        
        total = base_price + vat_fee + plate_fee + reg_fee
        
        def fmt(num):
            return f"{num:,.0f}".replace(",", ".") + " VNĐ"
            
        return {
            "base": fmt(base_price),
            "vat": fmt(vat_fee),
            "plate": fmt(plate_fee),
            "reg": fmt(reg_fee),
            "total": fmt(total)
        }
    except Exception:
        return {}

def send_quotation_email(to_email: str, car_name: str, car_price_str: str):
    """
    Hàm gửi email báo giá bằng SMTPLib.
    Sẽ raise Exception nếu Gửi không thành công (vd: sai mk).
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise Exception("Hệ thống chưa cấu hình SENDER_EMAIL và SENDER_PASSWORD trong file .env")

    fees = calculate_mock_rolling_price(car_price_str)
    
    if not fees:
        fees = {"base": car_price_str, "vat": "N/A", "plate": "N/A", "reg": "N/A", "total": "Liên hệ trực tiếp"}

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; }}
            h2 {{ color: #1e88e5; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; border: 1px solid #ddd; text-align: left; }}
            th {{ background-color: #f4f4f4; }}
            .total-row {{ font-weight: bold; font-size: 18px; color: #e53935; background-color: #ffebee; }}
            .footer {{ margin-top: 30px; font-size: 12px; text-align: center; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Bảng Ước Tính Giá Lăn Bánh Xe VinFast</h2>
            <p>Xin chào Quý khách,</p>
            <p>Cảm ơn Quý khách đã quan tâm đến mẫu xe <strong>{car_name}</strong> của VinFast. Dưới đây là bảng ước tính chi phí lăn bánh (tham khảo) dành cho Quý khách:</p>
            
            <table>
                <tr>
                    <th>Hạng mục chi phí</th>
                    <th>Thành tiền</th>
                </tr>
                <tr>
                    <td>Giá công bố (Base Price)</td>
                    <td>{fees['base']}</td>
                </tr>
                <tr>
                    <td>Thuế GTGT (VAT 10%)</td>
                    <td>{fees['vat']}</td>
                </tr>
                <tr>
                    <td>Phí cấp biển số (Dự kiến)</td>
                    <td>{fees['plate']}</td>
                </tr>
                <tr>
                    <td>Phí kiểm định & bảo trì đường bộ</td>
                    <td>{fees['reg']}</td>
                </tr>
                <tr class="total-row">
                    <td>TỔNG CHI PHÍ ƯỚC TÍNH</td>
                    <td>{fees['total']}</td>
                </tr>
            </table>

            <p style="margin-top: 20px;"><em>Lưu ý: Bảng giá này là nguyên mẫu giả lập sinh tự động và chỉ mang tính tham khảo. Chuyên viên kinh doanh VinFast sẽ liên hệ lại qua email để cung cấp thông tin chính xác nhất.</em></p>
            
            <div class="footer">
                <p>Hệ thống AI Tư vấn - VinFast Prototype Demo</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = f"VinFast - Báo Giá Ước Tính Lăn Bánh Xe {car_name}"
    msg['From'] = f"VinFast Advisor AI <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg.set_content("Quý khách vui lòng mở email hỗ trợ đọc HTML để xem bảng báo giá.")
    msg.add_alternative(html_content, subtype='html')

    try:
        # Dùng SSL (cổng 465)
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        # Nếu dùng TSL (cổng 587) thì code sẽ khác, đa số Gmail dùng cổng 465 SSL là tiện nhất.
        raise Exception(f"Lỗi SMTP: {str(e)}")
