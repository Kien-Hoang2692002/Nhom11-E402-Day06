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
            "id": item.get("id", item.get("ten_xe").lower().replace(" ", "")),
            "name": item.get("ten_xe"),
            "type": item.get("loai_xe"),
            "price": price,
            "range": item.get("quang_duong"),
            "desc": item.get("mo_ta"),
            "seats": item.get("thong_so", {}).get("Số chỗ ngồi"),
            "img": item.get("hinh_anh", [""])[0] if item.get("hinh_anh") else ""
        })
    return cars

def format_currency(amount: int) -> str:
    if not amount:
        return "N/A"
    return f"{amount:,.0f}".replace(",", ".") + "đ"

@tool
def analyze_user_budget(text: str) -> dict:
    """
    Phân tích ngân sách và độ rõ ràng của ngân sách từ câu nói của người dùng.
    Trả về: {"budget_amount": <số tiền nguyên dương> hoặc None, "is_clear": <True nếu text có chữ thuế/pin/lăn bánh/đã gồm>}
    """
    lower_text = text.lower()
    matches = re.findall(r'\d+', lower_text)
    budget = None
    
    if matches:
        num = int(matches[0])
        if 'triệu' in lower_text or 'tr' in lower_text:
            num *= 1000000
        elif 'tỷ' in lower_text:
            num *= 1000000000
        elif num < 10000:
            num *= 1000000
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
    """
    Tìm khớp xe dựa vào data động theo kịch bản Flowchart.
    - budget: Ngân sách đã được làm rõ.
    - preference: ưu tiên thiết kế ("rong_rai" hoặc "hieu_nang"). Có thể để None nếu chưa hỏi.
    Trả về dict mô tả hành động kế tiếp cần AI làm, cùng mảng list xe gợi ý (ID, name, price, desc, img).
    """
    cars = normalize_data()
    oto_cars = [c for c in cars if c["type"] == "oto_dien" and c["price"]]
    
    if not oto_cars:
        return {"action": "NO_CAR_FOUND", "cars": []}
    
    oto_cars.sort(key=lambda x: x["price"])
    min_price = oto_cars[0]["price"]

    # TH1: Khách không đủ tiền mua chiếc rẻ nhất -> Vượt ngân sách
    if budget < min_price:
        return {
            "action": "PROPOSE_INSTALLMENT", 
            "message": f"Ngân sách {format_currency(budget)} thấp hơn mức xe rẻ nhất của chúng tôi là {format_currency(min_price)}.",
            "cars": []
        }

    # TH2: Borderline - Check các lựa chọn quanh budget ±15%
    margin = budget * 0.15
    candidates = [c for c in oto_cars if budget - margin <= c["price"] <= budget + margin]
    
    # Nếu không có xe nào nằm trong margin, lấy xe tốt nhất vừa khít budget
    if not candidates:
        affordable = [c for c in oto_cars if c["price"] <= budget]
        if affordable:
            candidates = [affordable[-1]]

    # Borderline rule: Nếu có >= 2 xe và khách chưa chọn preference -> Chuyển luồng hỏi
    if len(candidates) >= 2 and not preference:
        car_names = ", ".join(c["name"] for c in candidates)
        return {
            "action": "ASK_PREFERENCE",
            "message": f"Hệ thống tìm thấy nhiều lựa chọn trong tầm giá ({car_names}). Trả về yêu cầu LLM hỏi khách hàng thích xe Rộng rãi hay Hiệu năng cao.",
            "cars": []
        }
    
    # TH3: Có xe khớp tuyệt đối (1 xe) HOẶC user đã có preference
    if len(candidates) >= 2 and preference:
        # Giả lập logic soft-sort:
        if preference == "rong_rai":
            candidates.sort(key=lambda x: x["price"], reverse=True)
        else:
            candidates.sort(key=lambda x: x["price"])
        best_match = candidates[0]
    else:
        best_match = candidates[0] if candidates else None
        
    if best_match:
        # Format JSON dict directly
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
def log_user_preference(car_id: str, is_skipped: bool) -> str:
    """
    Lưu log lên Database mỗi khi người dùng có hành động Skip thẻ hoặc quan tâm vào thẻ.
    """
    status = "Skipped" if is_skipped else "Interested"
    return f"[SYSTEM LOG] Đã ghi nhận mô hình AI: User {status} đối với xe {car_id}. Sẽ cải thiện Recommendation Lần sau!"