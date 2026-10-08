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


def crawl_minhchinh_table(url, game_type):
    """Bóc tách dữ liệu từ bảng thống kê 15 kỳ gần nhất của Minh Chính"""
    results = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.encoding = "utf-8"
        if res.status_code != 200:
            print(f"Không thể kết nối {url} (HTTP {res.status_code})")
            return results

        soup = BeautifulSoup(res.text, "html.parser")

        # Tìm các dòng <tr> trong bảng kết quả
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # 1. Tìm ngày quay (cột đầu tiên)
            date_cell = cells[0].get_text(strip=True)
            match_date = re.search(r"(\d{2}/\d{2}/\d{4})", date_cell)
            if not match_date:
                continue
            date_str = match_date.group(1)

            # 2. Tìm tất cả bóng số trong dòng đó
            # Các bóng số hiển thị 2 chữ số
            balls = []
            for tag in row.find_all(["span", "div", "b", "strong"]):
                val = tag.get_text(strip=True)
                if val.isdigit() and len(val) <= 2:
                    balls.append(int(val))

            limit = 45 if game_type == "mega645" else 55
            # Lọc số hợp lệ theo loại vé
            valid_balls = [b for b in balls if 1 <= b <= limit]

            # Mega 6/45 cần ít nhất 6 bóng, Power 6/55 cần ít nhất 7 bóng (6 số chính + 1 Jackpot 2)
            if game_type == "mega645" and len(valid_balls) >= 6:
                main_nums = sorted(valid_balls[:6])
                results.append(
                    {
                        "draw": date_str.replace("/", ""),  # Định danh theo ngày
                        "date": date_str,
                        "numbers": main_nums,
                    }
                )
            elif game_type == "power655" and len(valid_balls) >= 7:
                main_nums = sorted(valid_balls[:6])
                bonus_num = valid_balls[6]
                results.append(
                    {
                        "draw": date_str.replace("/", ""),
                        "date": date_str,
                        "numbers": main_nums,
                        "bonus": bonus_num,
                    }
                )

    except Exception as e:
        print(f"Lỗi khi cào bảng {game_type}: {e}")

    return results


def main():
    data = load_data()
    updated = False

    # 1. Cào Power 6/55 từ bảng 15 kỳ
    print("Đang cào bảng Power 6/55...")
    power_list = crawl_minhchinh_table(
        "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-power-655.html",
        "power655",
    )
    if power_list:
        existing_dates = [x.get("date") for x in data.get("power655", [])]
        for item in power_list:
            if item["date"] not in existing_dates:
                data.setdefault("power655", []).append(item)
                updated = True
                print(f"Thêm Power 6/55 ngày {item['date']}: {item['numbers']}")

    # 2. Cào Mega 6/45 từ bảng tương tự
    print("Đang cào bảng Mega 6/45...")
    mega_list = crawl_minhchinh_table(
        "https://www.minhchinh.com/xo-so-dien-toan-mega-6-45.html", "mega645"
    )
    if mega_list:
        existing_dates = [x.get("date") for x in data.get("mega645", [])]
        for item in mega_list:
            if item["date"] not in existing_dates:
                data.setdefault("mega645", []).append(item)
                updated = True
                print(f"Thêm Mega 6/45 ngày {item['date']}: {item['numbers']}")

    # Sắp xếp ngày mới nhất lên đầu và giữ lại 200 kỳ gần nhất
    def sort_by_date(items):
        return sorted(
            items,
            key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"),
            reverse=True,
        )[:200]

    if data.get("power655"):
        data["power655"] = sort_by_date(data["power655"])
    if data.get("mega645"):
        data["mega645"] = sort_by_date(data["mega645"])

    if updated or not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Đã cập nhật file data.json thành công!")
    else:
        print("Dữ liệu đã đầy đủ, không có kỳ mới.")


if __name__ == "__main__":
    main()
