import json
import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

DATA_FILE = "data.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"mega645": [], "power655": []}


def crawl_minhchinh(url, game_type):
    """Bóc tách kết quả Vietlott từ minhchinh.com"""
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.encoding = "utf-8"
        if res.status_code != 200:
            print(f"Không thể kết nối {url} (HTTP {res.status_code})")
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Bóc tách các bóng số
        # Minh Chính thường dùng class .bong_tron hoặc các thẻ chứa số kết quả
        balls = []
        ball_tags = soup.select(".bong_tron, .so_bong, .qua_bong")
        for tag in ball_tags:
            val = tag.get_text(strip=True)
            if val.isdigit() and len(val) <= 2:
                balls.append(int(val))

        # Nếu không có class riêng, tìm qua regex trực tiếp trong khối kết quả
        if len(balls) < 6:
            text_box = soup.get_text(" ", strip=True)
            raw_nums = re.findall(r"\b\d{2}\b", text_box)
            # Lọc các số hợp lệ
            limit = 45 if game_type == "mega645" else 55
            candidates = [int(x) for x in raw_nums if 1 <= int(x) <= limit]
            if len(candidates) >= 6:
                balls = candidates[: (7 if game_type == "power655" else 6)]

        if len(balls) < 6:
            print(f"Không bóc đủ bóng số cho {game_type}")
            return None

        # 2. Tìm kỳ quay và ngày quay
        full_text = soup.get_text(" ", strip=True)
        m_draw = re.search(r"Kỳ\s*(?:quay)?\s*#?(\d+)", full_text, re.I)
        m_date = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", full_text)

        draw_id = m_draw.group(1).zfill(5) if m_draw else "00000"
        date_str = (
            m_date.group(1) if m_date else datetime.now().strftime("%d/%m/%Y")
        )

        item = {
            "draw": draw_id,
            "date": date_str,
            "numbers": sorted(balls[:6]),
        }

        # Nếu là Power 6/55 và có bóng thứ 7 (Jackpot 2)
        if game_type == "power655" and len(balls) >= 7:
            item["bonus"] = balls[6]

        return item

    except Exception as e:
        print(f"Lỗi khi cào Minh Chính ({game_type}): {e}")
        return None


def main():
    data = load_data()
    updated = False

    # 1. Cào Mega 6/45
    mega_item = crawl_minhchinh(
        "https://www.minhchinh.com/xo-so-dien-toan-mega-6-45.html", "mega645"
    )
    if mega_item:
        existing = [x.get("draw") for x in data.get("mega645", [])]
        if mega_item["draw"] not in existing:
            data.setdefault("mega645", []).insert(0, mega_item)
            data["mega645"] = data["mega645"][:200]
            updated = True
            print(
                f"Thành công: Mega 6/45 kỳ #{mega_item['draw']} -> {mega_item['numbers']}"
            )

    # 2. Cào Power 6/55
    power_item = crawl_minhchinh(
        "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-power-655.html",
        "power655",
    )
    if power_item:
        existing = [x.get("draw") for x in data.get("power655", [])]
        if power_item["draw"] not in existing:
            data.setdefault("power655", []).insert(0, power_item)
            data["power655"] = data["power655"][:200]
            updated = True
            print(
                f"Thành công: Power 6/55 kỳ #{power_item['draw']} -> {power_item['numbers']}"
            )

    if updated:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Đã cập nhật data.json thành công!")
    else:
        print("Dữ liệu đã ở kỳ mới nhất, không có gì thay đổi.")


if __name__ == "__main__":
    main()
