from langchain_core.tools import tool
import json
import os

# =========================
# LOAD DATA JSON
# =========================
DATA_PATH = os.path.join(os.path.dirname(__file__), "vinfast_data.json")

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("du_lieu", [])

def parse_price(price_str):
    """
    "302.000.000" -> 302000000
    """
    if not price_str:
        return None
    try:
        return int(price_str.replace(".", ""))
    except:
        return None


def normalize_data():
    data = load_data()
    cars = []

    for item in data:
        price = parse_price(item.get("gia"))
        images = item.get("hinh_anh", [])
        ten_xe = item.get("ten_xe", "")
        car_name_short = ten_xe.lower().replace(" ", "")
        
        # 1. Lọc rác (logo, menu, svg...)
        all_candidates = []
        if images and isinstance(images, list):
            all_candidates = [
                img for img in images 
                if not any(x in img.lower() for x in ["logo", "icon", "header", "menu", "footer", "avatar", ".svg"])
            ]
            
            # 2. Xử lý trường hợp bị dính ảnh VF3
            if "vf3" not in car_name_short:
                all_candidates = [img for img in all_candidates if "vf3" not in img.lower()]

        # 3. Chọn ảnh đại diện (phải là ảnh ngoại thất của chính xe đó)
        image_url = None
        if all_candidates:
            # Danh sách ảnh của chính xe này (chứa tên xe)
            own_images = [img for img in all_candidates if car_name_short in img.lower()]
            
            if own_images:
                # Ưu tiên các từ khóa "ngoại thất": exterior, main, hero, lead, banner
                exterior_keywords = ['exterior', 'main', 'hero', 'lead', 'banner', 'overview']
                best = [img for img in own_images if any(kw in img.lower() for kw in exterior_keywords)]
                
                # Loại trừ các từ khóa "nội thất" hoặc "tính năng"
                not_best = ['interior', 'noi-that', 'feature', 'spec', 'detail', 'khuyen-mai']
                filtered_best = [img for img in (best if best else own_images) 
                                if not any(x in img.lower() for x in not_best)]
                
                image_url = filtered_best[0] if filtered_best else own_images[0]
            else:
                image_url = all_candidates[0]
        else:
            image_url = images[-1] if images else None

        cars.append({
            "name": ten_xe,
            "type": item.get("loai_xe"),
            "price": price,
            "range": item.get("quang_duong"),
            "desc": item.get("mo_ta"),
            "seats": item.get("thong_so", {}).get("Số chỗ ngồi"),
            "image": image_url,
            "all_images": all_candidates[:12], # Tăng lên 12 ảnh để xem được nhiều hơn
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

# =========================
# TOOL 1: TÌM XE THEO GIÁ
# =========================
@tool
def search_cars_by_price(max_price: int) -> str:
    """
    Tìm xe VinFast theo ngân sách tối đa.
    """
    cars = normalize_data()

    results = [c for c in cars if c["price"] and c["price"] <= max_price]

    if not results:
        return "Không tìm thấy xe phù hợp với ngân sách."

    results.sort(key=lambda x: x["price"])

    lines = [f"Xe dưới {format_currency(max_price)}:"]
    for i, c in enumerate(results):
        line = f"- {c['name']}: {format_currency(c['price'])}"
        if i == 0 and c.get("image"):
            line += f" [IMAGE] {c['image']}"
        lines.append(line)

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
    for i, c in enumerate(results):
        lines.append(f"- {c['name']} ({format_currency(c['price'])})")

    return "\n".join(lines)


# =========================
# TOOL 3: RECOMMEND XE
# =========================
@tool
def recommend_car(budget: int, purpose: str) -> str:
    """
    Gợi ý xe dựa trên ngân sách và mục đích.
    purpose: di_pho | gia_dinh | dich_vu | hoc_sinh
    """
    cars = normalize_data()

    candidates = [c for c in cars if c["price"] and c["price"] <= budget]

    if not candidates:
        return "Không có xe phù hợp ngân sách."

    # Logic gợi ý
    if purpose == "di_pho":
        best = min(candidates, key=lambda x: x["price"])
    elif purpose == "gia_dinh":
        best = max(candidates, key=lambda x: int(x["seats"].split()[0]) if x["seats"] else 4)
    elif purpose == "dich_vu":
        best = max(candidates, key=lambda x: int(x["range"].split()[0]) if x["range"] else 0)
    else:
        best = candidates[0]

    res = (
        f"Gợi ý cho bạn:\n"
        f"- {best['name']}\n"
        f"Giá: {format_currency(best['price'])}\n"
        f"Mô tả: {best['desc']}"
    )
    
    if best.get("image"):
        res += f"\n[IMAGE] {best['image']}"
        
    return res


# =========================
# TOOL 4: SO SÁNH XE
# =========================
@tool
def compare_cars(car1: str, car2: str) -> str:
    """
    So sánh 2 mẫu xe VinFast theo tên.
    Ví dụ: VF6, VF 6, vf6 đều hợp lệ
    """
    cars = normalize_data()

    norm_car1 = normalize_name(car1)
    norm_car2 = normalize_name(car2)

    car_obj1 = None
    car_obj2 = None

    for car in cars:
        name_norm = normalize_name(car["name"])

        if name_norm == norm_car1:
            car_obj1 = car
        if name_norm == norm_car2:
            car_obj2 = car

    if not car_obj1 or not car_obj2:
        return f"Không tìm thấy thông tin để so sánh {car1} và {car2}."

    def get_info(c):
        img_line = f"\n[IMAGE] {c['image']}" if c.get('image') else ""
        return (
            f"🚗 {c['name']}\n"
            f"💰 Giá: {format_currency(c['price'])}\n"
            f"🔋 Quãng đường: {c.get('range', 'N/A')}\n"
            f"🪑 Số chỗ: {c.get('seats', 'N/A')}\n"
            f"{img_line}"
        )

    result = (
        "=== So sánh xe ===\n\n"
        f"{get_info(car_obj1)}\n"
        f"{get_info(car_obj2)}"
    )

    return result

# =========================
# TOOL 5: CHI TIẾT XE
# =========================
@tool
def get_car_details(name: str) -> str:
    """
    Lấy thông tin chi tiết và bộ sưu tập ảnh (ngoại thất, nội thất) của một mẫu xe.
    """
    cars = normalize_data()
    norm_query = normalize_name(name)
    
    selected = None
    for car in cars:
        if normalize_name(car["name"]) == norm_query:
            selected = car
            break
            
    if not selected:
        return f"Không tìm thấy thông tin chi tiết cho xe {name}."
        
    lines = [
        f"🔍 CHI TIẾT XE: {selected['name']}",
        f"💰 Giá niêm yết: {format_currency(selected['price'])}",
        f"🛣️ Quãng đường: {selected.get('range', 'N/A')}",
        f"🪑 Chỗ ngồi: {selected.get('seats', 'N/A')}",
        f"📝 Mô tả: {selected['desc']}",
        "\n📸 Bộ sưu tập hình ảnh:"
    ]
    
    for img in selected.get("all_images", []):
        lines.append(f"[IMAGE] {img}")
        
    return "\n".join(lines)


# =========================
# TOOL 6: TRA CỨU TRỰC TIẾP (LIVE SEARCH)
# =========================
@tool
async def search_vinfast_live(query: str) -> str:
    """
    Truy vấn thông tin trực tiếp từ website shop.vinfastauto.com. 
    Dùng khi cần thông tin mới nhất hoặc khi không tìm thấy xe trong dữ liệu cũ.
    """
    from playwright.async_api import async_playwright
    
    url = f"https://shop.vinfastauto.com/vn_vi/search?q={query}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Lấy danh sách xe từ kết quả tìm kiếm
            cards = await page.query_selector_all(".product-item")
            if not cards:
                text = await page.inner_text("body")
                return f"Kết quả trực tiếp cho '{query}': {text[:400]}..."

            results = []
            for card in cards[:2]: 
                name = await card.query_selector(".product-name")
                price = await card.query_selector(".product-price")
                img = await card.query_selector("img")
                
                name_txt = await name.inner_text() if name else "N/A"
                price_txt = await price.inner_text() if price else "N/A"
                img_src = await img.get_attribute("src") if img else ""
                
                res = f"- {name_txt}: {price_txt}"
                if img_src:
                    res += f" [IMAGE] {img_src}"
                results.append(res)
            
            await browser.close()
            return "Dữ liệu cập nhật mới nhất từ website VinFast:\n" + "\n".join(results)
            
        except Exception as e:
            await browser.close()
            return f"Lỗi truy cập trực tiếp: {str(e)}. Vui lòng xem thông tin từ dữ liệu hệ thống."