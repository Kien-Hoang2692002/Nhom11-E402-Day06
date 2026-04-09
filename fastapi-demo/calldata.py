"""
╔══════════════════════════════════════════════════════════════════╗
║       VINFAST SCRAPER v3 - URL đã xác minh tháng 4/2026         ║
║  Nguồn: vinfastauto.com + shop.vinfastauto.com                  ║
║  Output: vinfast_data.json + vinfast_data.csv                    ║
╚══════════════════════════════════════════════════════════════════╝

Cài đặt:
    pip install playwright pandas
    playwright install chromium
"""

import asyncio
import json
import csv
import re
from datetime import datetime
from playwright.async_api import async_playwright

# ════════════════════════════════════════════════════════════════
# URL ĐÃ XÁC MINH (cập nhật tháng 4/2026)
# Dùng shop.vinfastauto.com vì ít bị block hơn vinfastauto.com
# ════════════════════════════════════════════════════════════════

XE_DIEN = {
    "VF 3":    "https://shop.vinfastauto.com/vn_vi/dat-coc-xe-dien-vf3.html",
    "VF 5":    "https://shop.vinfastauto.com/vn_vi/dat-coc-xe-dien-vf5.html",
    "VF 6":    "https://shop.vinfastauto.com/vn_vi/dat-coc-xe-dien-vf6.html",
    "VF MPV7": "https://vinfastauto.com/vn_vi/dat-coc-xe-vf-mpv7",
    "VF 7":    "https://shop.vinfastauto.com/vn_vi/dat-coc-xe-dien-vf7.html",
    "VF 8":    "https://shop.vinfastauto.com/vn_vi/dat-coc-xe-vf8.html",
    "VF 9":    "https://shop.vinfastauto.com/vn_vi/dat-coc-xe-vf9.html",
    "Lux A":    "https://shop.vinfastauto.com/vn_vi/o-to-vinfast-lux-a.html",
    "Fadil":   "https://shop.vinfastauto.com/vn_vi/o-to-vinfast-fadil.html",
    "Lux SA":  "https://shop.vinfastauto.com/vn_vi/o-to-vinfast-lux-sa.html",
    "President": "https://shop.vinfastauto.com/vn_vi/o-to-vinfast-president.html",
    "Minio Green": "https://vinfastauto.com/vn_vi/minio-green",
    "Herio Green": "https://vinfastauto.com/vn_vi/herio-green",
    "Nerio Green": "https://shop.vinfastauto.com/vn_vi/nerio-green.html",
    "Limo Green": "https://vinfastauto.com/vn_vi/limo-green",
    
}

# Xe máy điện - dùng URL từ vinfastauto.com (đã xác minh hoạt động)
XE_MAY_DIEN = {
"Verox": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-verox.html",
"Viper": "https://vinfastauto.com/vn_vi/xe-may-dien-vinfast-viper",
"Feliz": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-feliz.html",
"Feliz II": "https://vinfastauto.com/vn_vi/xe-may-dien-vinfast-feliz-II",
"Evo": "https://vinfastauto.com/vn_vi/xe-may-dien-evo",
"Evo Grand": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-evo-grand.html",
"Evo Grand Lite": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-evo-grand-lite.html",
"Evo Lite Neo": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-evo-lite-neo.html",
"Flazz": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-flazz.html",
"Zgoo": "https://shop.vinfastauto.com/vn_vi/xe-may-dien-zgoo.html",
"Amio": "https://vinfastauto.com/vn_vi/xe-may-dien-vinfast-amio",
}

OUTPUT_JSON = "vinfast_data.json"
OUTPUT_CSV  = "vinfast_data.csv"

# ════════════════════════════════════════════════════════════════
# TRÍCH XUẤT DỮ LIỆU BẰNG REGEX TỪ INNERTEXT
# ════════════════════════════════════════════════════════════════
def extract(text: str) -> dict:
    def find(patterns):
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    # Giá tiền
    gia = find([
        r'Giá[^\d]*([\d]{2,4}[\.,]\d{3}[\.,]\d{3})\s*(?:VNĐ|đồng|đ)',
        r'([\d]{2,4}[\.,]\d{3}[\.,]\d{3})\s*(?:VNĐ|đồng|đ)',
        r'([\d]{2,3}[\.,]\d{3})\s*triệu',
    ])

    # Quãng đường
    quang_duong = find([
        r'(\d{2,4})\s*km[/ ](?:lần sạc|một lần|charge)',
        r'(?:lên tới|đến|tới|di chuyển)\s*(?:khoảng\s*)?(\d{2,4})\s*km',
        r'(\d{2,4})\s*km\s*(?:sau|cho|trong)',
    ])
    if quang_duong:
        quang_duong += " km"

    # Pin
    pin = find([r'([\d]+[.,]?\d*)\s*kWh', r'([\d]+[.,]\d+)\s*kWh'])
    if pin:
        pin += " kWh"

    # Công suất động cơ
    cong_suat = find([r'công suất[^\d]*([\d.]+)\s*[Ww]', r'([\d.,]+)\s*[Ww]\b(?!\s*h)'])
    if cong_suat:
        # Chuẩn hóa W -> kW nếu >= 1000
        try:
            val = float(cong_suat.replace('.','').replace(',','.'))
            cong_suat = f"{val/1000:.1f} kW" if val >= 1000 else f"{val} W"
        except:
            cong_suat += " W"

    # Tốc độ tối đa
    toc_do = find([r'tốc độ tối đa[^\d]*([\d]+)\s*km/h', r'([\d]+)\s*km/h'])
    if toc_do:
        toc_do += " km/h"

    # Tăng tốc
    tang_toc = find([r'0[-–]50[^\d]*([\d.]+)\s*giây', r'0[-–]100[^\d]*([\d.]+)\s*giây'])
    if tang_toc:
        tang_toc += " giây"

    # Kích thước
    kich_thuoc = find([r'(\d[\d.]+\s*[xX×]\s*\d[\d.]+\s*[xX×]\s*\d[\d.]+)\s*mm'])
    if kich_thuoc:
        kich_thuoc += " mm"

    # Bảo hành
    bao_hanh = find([r'bảo hành[^\d]*([\d]+)\s*năm'])
    if bao_hanh:
        bao_hanh += " năm"

    # Thời gian sạc
    sac = find([r'sạc[^\d]*([\d]+)\s*(?:giờ|tiếng)', r'([\d]+)\s*(?:giờ|tiếng)[^\n]*sạc'])
    if sac:
        sac += " giờ"

    # Chỗ ngồi
    cho_ngoi = find([r'(\d)\s*(?:chỗ ngồi|chỗ|seats?)'])
    if cho_ngoi:
        cho_ngoi += " chỗ"

    # Màu sắc (xuất hiện trong text)
    mau_keywords = ['đen', 'trắng', 'đỏ', 'xanh', 'bạc', 'xám', 'vàng', 'cam', 'tím', 'hồng', 'nâu', 'be']
    mau_found = set()
    for kw in mau_keywords:
        for m in re.finditer(rf'\b{kw}(?:\s+\w+)?\b', text, re.IGNORECASE):
            mau_found.add(m.group(0).strip().lower())
    mau_sac = list(mau_found)[:8]

    # Gộp thông số kỹ thuật
    thong_so = {k: v for k, v in {
        "Pin":             pin,
        "Công suất":       cong_suat,
        "Quãng đường":     quang_duong,
        "Tốc độ tối đa":   toc_do,
        "Tăng tốc 0-50":   tang_toc,
        "Kích thước":      kich_thuoc,
        "Số chỗ ngồi":     cho_ngoi,
        "Thời gian sạc":   sac,
        "Bảo hành":        bao_hanh,
    }.items() if v}

    # Mô tả: lấy 2 dòng đầu có nghĩa
    lines = [l.strip() for l in text.split('\n') if 30 < len(l.strip()) < 300]
    mo_ta = ' '.join(lines[:2]) if lines else None

    return {
        "gia": gia,
        "quang_duong": quang_duong,
        "thong_so": thong_so,
        "mau_sac": mau_sac,
        "mo_ta": mo_ta,
    }


# ════════════════════════════════════════════════════════════════
# CÀO MỘT TRANG
# ════════════════════════════════════════════════════════════════
async def scrape_one(page, ten_xe: str, url: str, loai: str) -> dict:
    print(f"  🔍 [{loai}] {ten_xe}")
    print(f"     URL: {url}")

    result = {
        "ten_xe": ten_xe,
        "loai_xe": loai,
        "url": url,
        "thoi_gian": datetime.now().isoformat(),
        "gia": None,
        "quang_duong": None,
        "mo_ta": None,
        "thong_so": {},
        "mau_sac": [],
        "hinh_anh": [],
        "trang_thai": "chưa load",
    }

    # Bắt API JSON
    api_hits = []
    async def on_resp(r):
        if "json" in r.headers.get("content-type",""):
            try:
                body = await r.json()
                api_hits.append(r.url)
            except:
                pass
    page.on("response", on_resp)

    # Load trang
    try:
        await page.goto(url, wait_until="commit", timeout=25000)
        await page.wait_for_timeout(6000)
    except Exception as e:
        print(f"     ⚠️  Lỗi load: {e}")
        result["trang_thai"] = f"lỗi: {e}"
        page.remove_listener("response", on_resp)
        return result

    # Kiểm tra trang có load không
    body_ok = await page.evaluate("() => !!document.body && document.body.innerText.length > 100")
    if not body_ok:
        print(f"     ❌ Trang trống / bị block")
        result["trang_thai"] = "bị block"
        page.remove_listener("response", on_resp)
        return result

    # Lấy text
    try:
        text = await page.inner_text("body")
    except:
        text = ""

    # Trích xuất dữ liệu
    extracted = extract(text)
    result.update(extracted)

    # Lấy ảnh thông minh
    try:
        # Truyền ten_xe vào Evaluate để lọc ảnh chính xác hơn
        imgs = await page.evaluate("""
            (carName) => {
                const results = [];
                const name = carName.toLowerCase().replace(/\s/g, '');
                
                const allImgs = Array.from(document.images).map(i => ({
                    src: i.src,
                    alt: i.alt.toLowerCase(),
                    width: i.naturalWidth,
                    height: i.naturalHeight
                }));
                
                const prioritized = [];
                const others = [];
                
                for (const img of allImgs) {
                    const src = img.src;
                    if (!src.startsWith('http') || src.includes('data:')) continue;
                    
                    const s = src.toLowerCase();
                    const alt = img.alt.toLowerCase();
                    
                    // Bỏ qua rác: logo, icon, header, menu, footer, svg
                    if (s.includes('logo') || s.includes('icon') || s.includes('header') || 
                        s.includes('menu') || s.includes('footer') || s.includes('.svg')) continue;
                    
                    // Ưu tiên 1: Chứa từ khóa ngoại thất quan trọng + tên xe
                    const isExterior = s.includes('banner') || s.includes('lead') || s.includes('hero') || 
                                     s.includes('main') || s.includes('exterior') || s.includes('overview');
                                     
                    if (isExterior && (s.includes(name) || alt.includes(name))) {
                        prioritized.unshift(src); // Đưa lên hàng đầu tuyệt đối
                    } else if (s.includes(name) || alt.includes(name)) {
                        prioritized.push(src); // Ưu tiên loại 2
                    } else if (s.includes('vinfast') || s.includes('vf')) {
                        others.push(src);
                    }
                }
                // Trả về list unique, prioritized trước
                return [...new Set([...prioritized, ...others])].slice(0, 12);
            }
        """, ten_xe)
        result["hinh_anh"] = imgs
    except:
        pass

    result["trang_thai"] = "ok"
    page.remove_listener("response", on_resp)

    # In kết quả
    icon = "✅" if result.get("gia") or result.get("thong_so") else "⚠️ "
    print(f"     {icon} Giá: {result.get('gia') or 'N/A'} | "
          f"Thông số: {len(result['thong_so'])} | "
          f"Ảnh: {len(result['hinh_anh'])}")
    return result


# ════════════════════════════════════════════════════════════════
# LƯU FILE
# ════════════════════════════════════════════════════════════════
def save_json(data):
    out = {"tong_so_xe": len(data), "thoi_gian": datetime.now().isoformat(), "du_lieu": data}
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON → {OUTPUT_JSON}")

def save_csv(data):
    if not data:
        return
    rows = []
    for xe in data:
        row = {
            "loai_xe":     xe.get("loai_xe",""),
            "ten_xe":      xe.get("ten_xe",""),
            "gia":         xe.get("gia",""),
            "quang_duong": xe.get("quang_duong",""),
            "mo_ta":       (xe.get("mo_ta") or "")[:300],
            "mau_sac":     " | ".join(xe.get("mau_sac",[])),
            "hinh_anh":    xe.get("hinh_anh",[""])[0] if xe.get("hinh_anh") else "",
            "url":         xe.get("url",""),
            "trang_thai":  xe.get("trang_thai",""),
            "thoi_gian":   xe.get("thoi_gian",""),
        }
        for k, v in (xe.get("thong_so") or {}).items():
            row[f"spec_{k}"] = v
        rows.append(row)

    all_keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=all_keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k,"") for k in all_keys})
    print(f"💾 CSV  → {OUTPUT_CSV}")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
async def main():
    print("=" * 65)
    print("  🚗 VINFAST SCRAPER v3 — URL đã xác minh tháng 4/2026")
    print("=" * 65)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            extra_http_headers={
                "Accept-Language": "vi-VN,vi;q=0.9",
                "Referer": "https://vinfastauto.com/vn_vi",
            },
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()

        # ── Ô tô điện ──
        print(f"\n{'─'*65}")
        print("  📂 Ô TÔ ĐIỆN (VF Series)")
        print(f"{'─'*65}")
        for ten, url in XE_DIEN.items():
            r = await scrape_one(page, ten, url, "oto_dien")
            results.append(r)
            await asyncio.sleep(2)

        # ── Xe máy điện ──
        print(f"\n{'─'*65}")
        print("  📂 XE MÁY ĐIỆN (dòng 2025-2026)")
        print(f"{'─'*65}")
        for ten, url in XE_MAY_DIEN.items():
            r = await scrape_one(page, ten, url, "xe_may_dien")
            results.append(r)
            await asyncio.sleep(2)

        await browser.close()

    # Lưu
    save_json(results)
    save_csv(results)

    # Tổng kết
    ok  = [x for x in results if x.get("trang_thai") == "ok"]
    err = [x for x in results if x.get("trang_thai") != "ok"]
    co_du_lieu = [x for x in ok if x.get("gia") or x.get("thong_so")]

    print("\n" + "=" * 65)
    print(f"  ✅ Load OK: {len(ok)}/{len(results)} xe")
    print(f"  📊 Có dữ liệu: {len(co_du_lieu)}/{len(results)} xe")
    print()
    for xe in results:
        icon = "✅" if xe.get("gia") else ("⚠️ " if xe.get("trang_thai")=="ok" else "❌")
        print(f"  {icon} [{xe['loai_xe']}] {xe['ten_xe']} | "
              f"Giá: {xe.get('gia') or 'N/A'} | "
              f"Trạng thái: {xe.get('trang_thai')}")

    if err:
        print(f"\n⚠️  {len(err)} trang bị lỗi/block. Thử:")
        print("   → Đổi headless=True sang headless=False")
        print("   → Dùng VPN rồi chạy lại")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())