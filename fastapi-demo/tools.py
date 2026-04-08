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

        cars.append({
            "name": item.get("ten_xe"),
            "type": item.get("loai_xe"),
            "price": price,
            "range": item.get("quang_duong"),
            "desc": item.get("mo_ta"),
            "seats": item.get("thong_so", {}).get("Số chỗ ngồi"),
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

    return (
        f"Gợi ý cho bạn:\n"
        f"- {best['name']}\n"
        f"Giá: {format_currency(best['price'])}\n"
        f"Mô tả: {best['desc']}"
    )


# =========================
# TOOL 4: SO SÁNH XE
# =========================
@tool
def compare_cars(car1: str, car2: str) -> str:
    """
    So sánh 2 mẫu xe VinFast theo tên.
    Ví dụ: VF6, VF 6, vf6 đều hợp lệ
    """
    data = load_data()

    norm_car1 = normalize_name(car1)
    norm_car2 = normalize_name(car2)

    car_obj1 = None
    car_obj2 = None

    for car in data:
        name_norm = normalize_name(car["ten_xe"])

        if name_norm == norm_car1:
            car_obj1 = car
        if name_norm == norm_car2:
            car_obj2 = car

    if not car_obj1 or not car_obj2:
        return f"Không tìm thấy thông tin để so sánh {car1} và {car2}."

    def get_info(car):
        return (
            f"🚗 {car['ten_xe']}\n"
            f"💰 Giá: {car.get('gia', 'N/A')}\n"
            f"🔋 Quãng đường: {car.get('quang_duong', 'N/A')}\n"
            f"🪑 Số chỗ: {car.get('thong_so', {}).get('Số chỗ ngồi', 'N/A')}\n"
        )

    result = (
        "=== So sánh xe ===\n\n"
        f"{get_info(car_obj1)}\n"
        f"{get_info(car_obj2)}"
    )

    return result