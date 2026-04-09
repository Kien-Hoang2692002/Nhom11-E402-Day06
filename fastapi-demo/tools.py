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


def normalize_name(name: str):
    import unicodedata
    n = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().replace(" ", "")

def normalize_data():
    data = load_data()
    cars = []
    for item in data:
        images = item.get("hinh_anh", [])
        colors = item.get("mau_sac", [])
        specs = item.get("thong_so", {})
        price = parse_price(item.get("gia"))
        images = item.get("hinh_anh", [])
        ten_xe = item.get("ten_xe", "")
        car_name_short = ten_xe.lower().replace(" ", "")
        
        all_candidates = []
        if images and isinstance(images, list):
            all_candidates = [
                img for img in images 
                if not any(x in img.lower() for x in ["logo", "icon", "header", "menu", "footer", "avatar", ".svg"])
            ]
            if "vf3" not in car_name_short:
                all_candidates = [img for img in all_candidates if "vf3" not in img.lower()]

        image_url = None
        if all_candidates:
            own_images = [img for img in all_candidates if car_name_short in img.lower()]
            if own_images:
                exterior_keywords = ['exterior', 'main', 'hero', 'lead', 'banner', 'overview']
                best = [img for img in own_images if any(kw in img.lower() for kw in exterior_keywords)]
                not_best = ['interior', 'noi-that', 'feature', 'spec', 'detail', 'khuyen-mai']
                filtered_best = [img for img in (best if best else own_images) 
                                if not any(x in img.lower() for x in not_best)]
                image_url = filtered_best[0] if filtered_best else own_images[0]
            else:
                image_url = all_candidates[0]
        else:
            image_url = images[-1] if images else None

        cars.append({
            "id": item.get("id", car_name_short),
            "name": ten_xe,
            "type": item.get("loai_xe"),
            "price": price,
            "range": item.get("quang_duong"),
            "desc": item.get("mo_ta"),
            "seats": item.get("thong_so", {}).get("Số chỗ ngồi"),
            "img": item.get("hinh_anh", [""])[0] if item.get("hinh_anh") else "",
            "image": image_url,
            "all_images": all_candidates[:12],
            "raw": item
        })
    return cars

def format_currency(amount: int) -> str:
    if not amount: return "N/A"
    return f"{amount:,.0f}".replace(",", ".") + "đ"

@tool
def analyze_user_budget(text: str) -> dict:
    """
    Phân tích ngân sách và độ rõ ràng của ngân sách từ câu nói của người dùng.
    """
    lower_text = text.lower()
    matches = re.findall(r'\d+', lower_text)
    budget = None
    if matches:
        num = int(matches[0])
        if 'triệu' in lower_text or 'tr' in lower_text: num *= 1000000
        elif 'tỷ' in lower_text: num *= 1000000000
        elif num < 10000: num *= 1000000
        budget = num
    is_clear = False
    if budget:
        if any(w in lower_text for w in ['thuế', 'lăn bánh', 'pin', 'đã gồm', 'trọn gói', 'chưa bao gồm', 'rồi']):
            is_clear = True
        if budget >= 1000000000:
            is_clear = True
    return {"budget_amount": budget, "is_clear": is_clear}

@tool
def execute_matching_logic(budget: int, preference: str = None) -> dict:
    """Tìm khớp xe dựa vào data động theo kịch bản Flowchart."""
    cars = normalize_data()
    oto_cars = [c for c in cars if c["type"] == "oto_dien" and c["price"]]
    if not oto_cars:
        return {"action": "NO_CAR_FOUND", "cars": []}
    
    oto_cars.sort(key=lambda x: x["price"])
    min_price = oto_cars[0]["price"]

    if budget < min_price:
        return {
            "action": "PROPOSE_INSTALLMENT", 
            "message": f"Ngân sách {format_currency(budget)} thấp hơn mức xe rẻ nhất là {format_currency(min_price)}.",
            "cars": []
        }

    margin = budget * 0.15
    candidates = [c for c in oto_cars if budget - margin <= c["price"] <= budget + margin]
    if not candidates:
        affordable = [c for c in oto_cars if c["price"] <= budget]
        if affordable: candidates = [affordable[-1]]

    if len(candidates) >= 2 and not preference:
        car_names = ", ".join(c["name"] for c in candidates)
        return {
            "action": "ASK_PREFERENCE",
            "message": f"Tìm thấy ({car_names}). Trả về yêu cầu LLM hỏi khách.",
            "cars": []
        }
    
    if len(candidates) >= 2 and preference:
        if preference == "rong_rai": candidates.sort(key=lambda x: x["price"], reverse=True)
        else: candidates.sort(key=lambda x: x["price"])
        best_match = candidates[0]
    else:
        best_match = candidates[0] if candidates else None
        
    if best_match:
        return {
            "action": "RECOMMEND_CARD",
            "message": f"Trả về xe phù hợp nhất.",
            "cars": [{
                "id": best_match["id"],
                "name": best_match["name"],
                "price": format_currency(best_match["price"]),
                "desc": best_match["desc"],
                "specs": f"Số chỗ: {best_match['seats']} | Tầm hoạt động: {best_match['range']}"
            }]
        }
    return {"action": "NO_CAR_FOUND", "cars": []}

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
    """Tìm xe dưới mức giá tối đa"""
    cars = normalize_data()

    results = [
        c for c in cars 
        if parse_price(c.get("price")) is not None and parse_price(c.get("price")) <= max_price
    ]

    if not results:
        return "Không tìm thấy xe phù hợp với ngân sách."

    results.sort(key=lambda x: x["price"])
    lines = [f"Xe dưới {format_currency(max_price)}:"]
    for i, c in enumerate(results):
        line = f"- {c['name']}: {format_currency(c['price'])}"
        if i == 0 and c.get("image"): line += f" [IMAGE] {c['image']}"
        lines.append(line)
    return "\n".join(lines)

@tool
def search_by_type(car_type: str) -> str:
    """Tìm xe theo loại: oto_dien hoặc xe_may_dien"""
    cars = normalize_data()
    results = [c for c in cars if c["type"] == car_type]
    if not results: return f"Không có xe loại {car_type}"
    lines = [f"Danh sách {car_type}:"]
    for c in results: lines.append(f"- {c['name']} ({format_currency(c['price'])})")
    return "\n".join(lines)

# @tool
# def recommend_car(budget: int, purpose: str) -> str:
#     """
#     Gợi ý xe tốt nhất dựa trên ngân sách và mục đích sử dụng.

#     Parameters:
#     budget (int): Ngân sách tối đa
#     purpose (str): Mục đích sử dụng (di_pho, gia_dinh, dich_vu, hoc_sinh)

#     Returns:
#     str: Thông tin xe gợi ý
#     """
#     cars = normalize_data()

#     # =========================
#     # 1. Lọc theo ngân sách
#     # =========================
#     candidates = []
#     for c in cars:
#         price = c.get("price")
#         if price and price <= budget:
#             c["_price"] = price
#             candidates.append(c)

#     if not candidates:
#         return "❌ Không có xe phù hợp với ngân sách."

#     # =========================
#     # 2. Logic chọn xe
#     # =========================
#     try:
#         if purpose == "di_pho":
#             best = min(candidates, key=lambda x: x["_price"])

#         elif purpose == "gia_dinh":
#             autos = [c for c in candidates if c.get("type") == "oto_dien"]  
#             target = autos if autos else candidates
#             best = max(target, key=lambda x: len(x.get("desc") or ""))  

#         elif purpose == "dich_vu":
#             best = max(candidates, key=lambda x: (x.get("range")))  

#         elif purpose == "hoc_sinh":
#             bikes = [c for c in candidates if c.get("type") == "xe_may_dien"]  
#             best = min(bikes, key=lambda x: x["_price"]) if bikes else candidates[0]

#         else:
#             best = candidates[0]

#     except Exception as e:
#         return f"❌ Lỗi xử lý: {str(e)}"

#     # =========================
#     # 3. Output
#     # =========================
#     return (
#         f"🚗 **{best.get('name')}**\n"
#         f"💰 Giá: {format_currency(best.get('price'))}\n"
#         f"🔋 Quãng đường: {best.get('range')}\n"
#         f"📝 {best.get('desc')}\n"
#         f"🎨 Màu: {', '.join(best.get('mau_sac', [])) or 'N/A'}\n"
#         f"🔗 {best.get('url')}\n"
#         f"🖼️ {best.get('hinh_anh')}\n"
#     )
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

@tool
def recommend_car(budget: int, purpose: str) -> str:
    """Gợi ý xe dựa trên ngân sách và mục đích (di_pho | gia_dinh)."""
    cars = normalize_data()
    candidates = [c for c in cars if c["price"] and c["price"] <= budget]
    if not candidates: return "Không tìm thấy xe phù hợp."
    candidates.sort(key=lambda x: x["price"], reverse=(purpose == "gia_dinh"))
    best = candidates[0]
    res = f"Gợi ý: {best['name']} - Giá: {format_currency(best['price'])}\nMô tả: {best['desc']}"
    if best.get("image"): res += f"\n[IMAGE] {best['image']}"
    return res

# @tool
# def compare_cars(car1: str, car2: str) -> str:
#     """So sánh 2 xe."""
#     cars = normalize_data()
#     car_obj1 = next((c for c in cars if normalize_name(c["name"]) == normalize_name(car1)), None)
#     car_obj2 = next((c for c in cars if normalize_name(c["name"]) == normalize_name(car2)), None)
#     if not car_obj1 or not car_obj2: return f"Không tìm thấy thông tin để so sánh."
#     def get_info(c):
#         img_line = f"\n[IMAGE] {c['image']}" if c.get('image') else ""
#         return f"🚗 {c['name']}\n💰 Giá: {format_currency(c['price'])}\n🔋 Quãng đường: {c.get('range', 'N/A')}\n🪑 Số chỗ: {c.get('seats', 'N/A')}\n{img_line}"
#     return f"=== So sánh xe ===\n\n{get_info(car_obj1)}\n\n{get_info(car_obj2)}"

@tool
def log_user_preference(car_id: str, is_skipped: bool) -> str:
    """Lưu log lên Database mỗi khi người dùng có hành động."""
    status = "Skipped" if is_skipped else "Interested"
    return f"[SYSTEM LOG] Đã ghi nhận mô hình AI: User {status} đối với xe {car_id}."

@tool
def get_car_details(name: str) -> str:
    """Lấy thông tin chi tiết và bộ sưu tập ảnh của một mẫu xe."""
    cars = normalize_data()
    selected = next((c for c in cars if normalize_name(c["name"]) == normalize_name(name)), None)
    if not selected: return "Không tìm thấy thông tin chi tiết."
    lines = [f"🔍 CHI TIẾT XE: {selected['name']}", f"💰 Giá niêm yết: {format_currency(selected['price'])}", f"📝 Mô tả: {selected['desc']}", "\n📸 Bộ sưu tập hình ảnh:"]
    for img in selected.get("all_images", []): lines.append(f"[IMAGE] {img}")
    return "\n".join(lines)

@tool
async def search_vinfast_live(query: str) -> str:
    """Truy vấn thông tin trực tiếp từ website shop.vinfastauto.com."""
    from playwright.async_api import async_playwright
    url = f"https://shop.vinfastauto.com/vn_vi/search?q={query}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            cards = await page.query_selector_all(".product-item")
            if not cards:
                text = await page.inner_text("body")
                return f"Kết quả: {text[:400]}..."
            results = []
            for card in cards[:2]:
                name = await card.query_selector(".product-name")
                price = await card.query_selector(".product-price")
                img = await card.query_selector("img")
                res = f"- {await name.inner_text() if name else 'N/A'}: {await price.inner_text() if price else 'N/A'}"
                img_src = await img.get_attribute("src") if img else ""
                if img_src: res += f" [IMAGE] {img_src}"
                results.append(res)
            await browser.close()
            return "Dữ liệu website:\n" + "\n".join(results)
        except Exception as e:
            await browser.close()
            return f"Lỗi: {str(e)}"
