import base64

from langchain_core.tools import tool
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import csv
import os
from datetime import datetime
from email.mime.image import MIMEImage
import qrcode
import io
import hashlib
import urllib.parse
import hmac
import requests


from dotenv import load_dotenv

load_dotenv()

# =========================
# LOAD DATA JSON
# =========================
DATA_PATH = os.path.join(os.path.dirname(__file__), "vinfast_data.json")

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

def send_email(to_email: str, subject: str, content: str, qr_buffer=None):
    host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    port = int(os.getenv("EMAIL_PORT", 587))
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")

    try:
        # ✅ Dùng "related" để embed ảnh
        msg = MIMEMultipart("related")
        msg["From"] = user
        msg["To"] = to_email
        msg["Subject"] = subject

        # =========================
        # HTML content
        # =========================
        msg.attach(MIMEText(content, "html", "utf-8"))

        # =========================
        # Attach QR nếu có
        # =========================
        if qr_buffer:
            qr_buffer.seek(0)
            img = MIMEImage(qr_buffer.read())
            img.add_header("Content-ID", "<qrcode>")
            msg.attach(img)

        # =========================
        # SMTP
        # =========================
        server = smtplib.SMTP(host, port)
        server.set_debuglevel(1)
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()

        return True

    except Exception as e:
        print(f"❌ Chi tiết lỗi: {e}")
        return str(e)

def create_vietqr_payment(amount: int, content: str):
    url = "https://api.vietqr.io/v2/generate"

    payload = {
        "accountNo": "0967543960",        # Số tài khoản thực tế của bạn
        "accountName": "HOANG VAN KIEN", # Tên chủ TK (nên viết hoa không dấu)
        "acqId": "970422",               # MB Bank mã BIN là 970422
        "amount": amount,
        "addInfo": content,
        "format": "text",
        "template": "compact"
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(url, json=payload, headers=headers)
        res_json = res.json()

        if res_json.get("code") == "00":
            data = res_json["data"]
            return {
                "qr_code": data["qrDataURL"], # Link ảnh Base64
                "qr_text": data["qrCode"],    # Chuỗi text để tự tạo QR nếu cần
            }
        else:
            print(f"❌ Lỗi VietQR: {res_json.get('desc')}")
            return None
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        return None

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("du_lieu", [])

def parse_price(price_val):
    """
    Xử lý mọi loại đầu vào: "302.000.000", 302000000, hoặc None
    """
    if price_val is None:
        return None
    
    # Nếu đã là số rồi thì trả về luôn, không cần xử lý chuỗi
    if isinstance(price_val, (int, float)):
        return int(price_val)
    
    try:
        # Nếu là chuỗi, ép kiểu str() để chắc chắn rồi mới replace
        clean_str = str(price_val).replace(".", "").replace(",", "").strip()
        # Xử lý trường hợp có chữ "VNĐ" hoặc khoảng trắng
        clean_str = "".join(filter(str.isdigit, clean_str)) 
        return int(clean_str) if clean_str else None
    except Exception:
        return None


def normalize_data():
    data = load_data()
    cars = []

    for item in data:
        images = item.get("hinh_anh", [])
        colors = item.get("mau_sac", [])
        specs = item.get("thong_so", {})
        price = parse_price(item.get("gia"))

        cars.append({
            "name": item.get("ten_xe"),
            "type": item.get("loai_xe"),
            "price": price,
            "range": item.get("quang_duong"),
            "desc": item.get("mo_ta"),
            
            # Thông số kỹ thuật chi tiết
            "specs": {
                "battery": specs.get("Pin"),
                "power": specs.get("Công suất"),
                "top_speed": specs.get("Tốc độ tối đa"),
                "dimensions": specs.get("Kích thước")
            },
            
            # Xử lý mảng
            "hinh_anh": images[-1] if images else None, 
            "mau_sac": colors,
            
            # Metadata bổ sung
            "url": item.get("url"),
            "raw": item 
        })

    return cars


# =========================
# HELPER
# =========================
def format_currency(amount: int) -> str:
    if not amount:
        return "N/A"
    return f"{amount:,.0f}".replace(",", ".") + "đ"

def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "").strip()

def create_vnpay_link(order_id: str, amount: int):
    vnp_Url = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    vnp_TmnCode = "DEMOV210" # Mã test mặc định của VNPay
    vnp_HashSecret = "SECRETKEY" # Thay bằng Secret Key thật của bạn

    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": vnp_TmnCode,
        "vnp_Amount": str(amount * 100), # Phải là chuỗi
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": order_id,
        "vnp_OrderInfo": f"Thanh toan don hang: {order_id}",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_IpAddr": "127.0.0.1",
        "vnp_ReturnUrl": "http://localhost:8000/vnpay-return",
        "vnp_CreateDate": datetime.now().strftime('%Y%m%d%H%M%S'),
    }

    # 1. Sắp xếp params theo alphabet (Bắt buộc)
    sorted_params = sorted(params.items())

    # 2. Tạo query string để gửi đi (có encode)
    query_string = urllib.parse.urlencode(sorted_params)

    # 3. Tạo chuỗi dữ liệu để băm (dùng quote_plus để giống định dạng VNPay yêu cầu)
    hash_data = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

    # 4. HASH chuẩn HMAC-SHA512 (Đây là chỗ bạn bị lỗi)
    secure_hash = hmac.new(
        vnp_HashSecret.encode('utf-8'),
        hash_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()

    payment_url = f"{vnp_Url}?{query_string}&vnp_SecureHash={secure_hash}"

    return payment_url

# =========================
# TOOL 1: TÌM XE THEO GIÁ
# =========================
@tool
def search_cars_by_price(max_price: int) -> str:
    """
    Tìm xe VinFast theo ngân sách tối đa.
    """
    cars = normalize_data()

    results = [
        c for c in cars 
        if parse_price(c.get("price")) is not None and parse_price(c.get("price")) <= max_price
    ]

    if not results:
        return "Không tìm thấy xe phù hợp với ngân sách."

    results.sort(key=lambda x: x["price"])

    lines = [f"Xe dưới {format_currency(max_price)}:"]
    for c in results:
        lines.append(f"- {c['name']}: {format_currency(c['price'])}")

    return "\n".join(lines)


# =========================
# TOOL 2: TÌM THEO LOẠI
# =========================
@tool
def search_by_type(car_type: str) -> str:
    """
    Tìm xe theo loại: oto_dien hoặc xe_may_dien
    """
    cars = normalize_data()

    results = [c for c in cars if c["type"] == car_type]

    if not results:
        return f"Không có xe loại {car_type}"

    lines = [f"Danh sách {car_type}:"]
    for c in results:
        lines.append(f"- {c['name']} ({format_currency(c['price'])})")

    return "\n".join(lines)


# =========================
# TOOL 3: RECOMMEND XE
# =========================
@tool
def recommend_car(budget: int, purpose: str) -> str:
    """
    Gợi ý xe tốt nhất dựa trên ngân sách và mục đích sử dụng.

    Parameters:
    budget (int): Ngân sách tối đa
    purpose (str): Mục đích sử dụng (di_pho, gia_dinh, dich_vu, hoc_sinh)

    Returns:
    str: Thông tin xe gợi ý
    """
    cars = normalize_data()

    # =========================
    # 1. Lọc theo ngân sách
    # =========================
    candidates = []
    for c in cars:
        price = c.get("price")
        if price and price <= budget:
            c["_price"] = price
            candidates.append(c)

    if not candidates:
        return "❌ Không có xe phù hợp với ngân sách."

    # =========================
    # 2. Logic chọn xe
    # =========================
    try:
        if purpose == "di_pho":
            best = min(candidates, key=lambda x: x["_price"])

        elif purpose == "gia_dinh":
            autos = [c for c in candidates if c.get("type") == "oto_dien"]  
            target = autos if autos else candidates
            best = max(target, key=lambda x: len(x.get("desc") or ""))  

        elif purpose == "dich_vu":
            best = max(candidates, key=lambda x: (x.get("range")))  

        elif purpose == "hoc_sinh":
            bikes = [c for c in candidates if c.get("type") == "xe_may_dien"]  
            best = min(bikes, key=lambda x: x["_price"]) if bikes else candidates[0]

        else:
            best = candidates[0]

    except Exception as e:
        return f"❌ Lỗi xử lý: {str(e)}"

    # =========================
    # 3. Output
    # =========================
    return (
        f"🚗 **{best.get('name')}**\n"
        f"💰 Giá: {format_currency(best.get('price'))}\n"
        f"🔋 Quãng đường: {best.get('range')}\n"
        f"📝 {best.get('desc')}\n"
        f"🎨 Màu: {', '.join(best.get('mau_sac', [])) or 'N/A'}\n"
        f"🔗 {best.get('url')}\n"
        f"🖼️ {best.get('hinh_anh')}\n"
    )
# =========================
# TOOL 4: SO SÁNH XE
# =========================
@tool
def compare_cars(car1: str, car2: str) -> str:
    """
    So sánh 2 xe VinFast.
    :param car1: Tên xe 1
    :param car2: Tên xe 2
    :return: Chuỗi so sánh 2 xe
    """
    data = normalize_data()

    def clean_name(name):
        return re.sub(r'[^a-z0-9]', '', str(name).lower())

    def format_currency(amount):
        return f"{amount:,.0f}".replace(",", ".") + "đ" if amount else "N/A"

    norm_car1 = clean_name(car1)
    norm_car2 = clean_name(car2)

    car_obj1 = next((c for c in data if clean_name(c.get("name")) == norm_car1), None)
    car_obj2 = next((c for c in data if clean_name(c.get("name")) == norm_car2), None)

    if not car_obj1 or not car_obj2:
        return "❌ Không tìm thấy 1 trong 2 xe. Thử: VF3, VF5, VF8..."

    def get_spec(car, key):
        return car.get("specs", {}).get(key) or "N/A"

    comparison = [
        ("💰 Giá bán", format_currency(car_obj1['price']), format_currency(car_obj2['price'])),
        ("🔋 Quãng đường", car_obj1['range'], car_obj2['range']),
        ("⚡ Công suất", get_spec(car_obj1, "power"), get_spec(car_obj2, "power")),
        ("🚀 Tốc độ tối đa", get_spec(car_obj1, "top_speed"), get_spec(car_obj2, "top_speed")),
        ("🔋 Pin", get_spec(car_obj1, "battery"), get_spec(car_obj2, "battery")),
        ("📏 Kích thước", get_spec(car_obj1, "dimensions"), get_spec(car_obj2, "dimensions")),
    ]

    res = f"📊 **SO SÁNH: {car_obj1['name']} vs {car_obj2['name']}**\n\n"

    for label, v1, v2 in comparison:
        res += f"{label}\n"
        res += f"  • {car_obj1['name']}: {v1}\n"
        res += f"  • {car_obj2['name']}: {v2}\n\n"

    res += f"🖼️ Ảnh:\n"
    res += f"- {car_obj1['hinh_anh']}\n"
    res += f"- {car_obj2['hinh_anh']}\n"

    return res

ORDER_DB_PATH = "orders.csv"

@tool
def place_order_and_notify(customer_name: str, email: str, car_model: str):
    """
    Ghi nhận thông tin đặt cọc xe vào hệ thống (CSV) và gửi email xác nhận cho khách hàng.
    """

    # --- 1. Lưu thông tin vào file CSV ---
    file_exists = os.path.isfile(ORDER_DB_PATH)
    
    try:
        with open(ORDER_DB_PATH, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            
            # Nếu file mới, tạo dòng tiêu đề (Header)
            if not file_exists:
                writer.writerow(["Thời gian", "Tên khách hàng", "Email", "Dòng xe"])
            
            # Ghi dữ liệu khách hàng
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, customer_name, email, car_model])
            
        print(f"✅ Đã ghi nhận đơn hàng của {customer_name} vào {ORDER_DB_PATH}")

    except Exception as e:
        return f"❌ Lỗi khi lưu dữ liệu: {str(e)}"

    amount = 10000000  # 10 triệu cọc
    content = f"{customer_name}_{car_model}"

    qr_data = create_vietqr_payment(amount, content)

    if not qr_data:
        return "❌ Không tạo được QR thanh toán"
    
    qr_base64 = qr_data['qr_code']
    if "," in qr_base64:
        qr_base64 = qr_base64.split(",")[1]
    
    qr_bytes = base64.b64decode(qr_base64)
    qr_buffer = io.BytesIO(qr_bytes)

    # --- 2. Gửi email xác nhận ---
    subject = f"Xác nhận đặt cọc xe {car_model} - VinFast"

    html_content = f"""
    <h2>Chào {customer_name}</h2>
    <p>Cảm ơn bạn đã tin tưởng lựa chọn VinFast làm người bạn đồng hành.</p>
    </br>
    <p Hệ thống đã ghi nhận yêu cầu đặt cọc cho dòng xe: {car_model}.
        Chúng tôi sẽ sớm liên hệ với bạn qua email {email} để hoàn tất thủ tục.</p>

   <p><b>Số tiền:</b> {amount:,} VNĐ</p>

    <p><b>Nội dung chuyển khoản:</b> {content}</p>

    <p>Quét QR bên dưới:</p>
    <img src="cid:qrcode" width="250" style="display:block;"/>

    <p>Hoặc chuyển khoản thủ công:</p>
    <ul>
        <li>Ngân hàng: MB Bank</li>
        <li>Số TK: 9704220000000000</li>
        <li>Nội dung: {content}</li>
    </ul>

    <p>Trân trọng,<br>VinFast Advisor 🚗</p>
    """

    result = send_email(email, subject, html_content, qr_buffer=qr_buffer)

    if result is True:
        return f"✅ Đã lưu thông tin và gửi email xác nhận tới {email} cho xe {car_model}."
    else:
        return f"⚠️ Đã lưu thông tin vào hệ thống nhưng gửi email thất bại: {result}"

if __name__ == "__main__":
    res = place_order_and_notify.invoke({
        "customer_name": "Kien",
        "email": "kien20205089@gmail.com",
        "car_model": "VF8"
    })
    print(res)
