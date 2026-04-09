from langchain_core.tools import tool
import json
import os
import re

DATA_PATH = os.path.join(os.path.dirname(__file__), "vinfast_data.json")

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("du_lieu", [])

def parse_price(price_str):
    if not price_str: return None
    try: return int(price_str.replace(".", ""))
    except: return None

def normalize_name(name: str):
    import unicodedata
    n = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().replace(" ", "")

def normalize_data():
    data = load_data()
    cars = []
    for item in data:
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

@tool
def search_cars_by_price(max_price: int) -> str:
    """Tìm xe dưới mức giá tối đa"""
    cars = normalize_data()
    results = [c for c in cars if c["price"] and c["price"] <= max_price]
    if not results: return "Không tìm thấy xe phù hợp."
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

@tool
def compare_cars(car1: str, car2: str) -> str:
    """So sánh 2 xe."""
    cars = normalize_data()
    car_obj1 = next((c for c in cars if normalize_name(c["name"]) == normalize_name(car1)), None)
    car_obj2 = next((c for c in cars if normalize_name(c["name"]) == normalize_name(car2)), None)
    if not car_obj1 or not car_obj2: return f"Không tìm thấy thông tin để so sánh."
    def get_info(c):
        img_line = f"\n[IMAGE] {c['image']}" if c.get('image') else ""
        return f"🚗 {c['name']}\n💰 Giá: {format_currency(c['price'])}\n🔋 Quãng đường: {c.get('range', 'N/A')}\n🪑 Số chỗ: {c.get('seats', 'N/A')}\n{img_line}"
    return f"=== So sánh xe ===\n\n{get_info(car_obj1)}\n\n{get_info(car_obj2)}"

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
