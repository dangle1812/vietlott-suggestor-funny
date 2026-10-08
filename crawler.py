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
    """Tải dữ liệu cũ từ data.json nếu tồn tại"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    return content
        except Exception:
            pass
    return {"mega645": [], "power655": []}


def parse_minhchinh_table(url, game_type):
    """
    Bóc tách bảng thống kê 15 kỳ gần nhất từ Minh Chính
    game_type: 'mega645' (lấy 6 số <= 45) hoặc 'power655' (lấy 6 số <= 55 + 1 bonus)
    """
    results = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=25)
        res.encoding = "utf-8"
        if res.status_code != 200:
            print(f"Không thể kết nối đến {url} (Mã HTTP: {res.status_code})")
            return results

        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr")

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # 1. Tìm ngày quay ở ô đầu tiên
            first_cell_text = cells[0].get_text(strip=True)
            match_date = re.search(r"(\d{2}/\d{2}/\d{4})", first_cell_text)
            if not match_date:
                continue
            date_str = match_date.group(1)

            # 2. Tìm tất cả các bóng số trong dòng
            balls = []
            for tag in row.find_all(["span", "div", "b", "strong"]):
                text_val = tag.get_text(strip=True)
                if text_val.isdigit() and len(text_val) <= 2:
                    balls.append(int(text_val))

            max_ball_val = 45 if game_type == "mega645" else 55
            valid_balls = [b for b in balls if 1 <= b <= max_ball_val]

            # Xử lý theo loại hình xổ số
            if game_type == "mega645" and len(valid_balls) >= 6:
                main_nums = sorted(valid_balls[:6])
                # Tránh trùng lặp ngày trong cùng một bảng
                if not any(r["date"] == date_str for r in results):
                    results.append(
                        {
                            "draw": date_str.replace("/", ""),
                            "date": date_str,
                            "numbers": main_nums,
                        }
                    )
            elif game_type == "power655" and len(valid_balls) >= 7:
                main_nums = sorted(valid_balls[:6])
                bonus_num = valid_balls[6]
                if not any(r["date"] == date_str for r in results):
                    results.append(
                        {
                            "draw": date_str.replace("/", ""),
                            "date": date_str,
                            "numbers": main_nums,
                            "bonus": bonus_num,
                        }
                    )

    except Exception as e:
        print(f"Lỗi khi cào dữ liệu {game_type}: {e}")

    return results


def merge_and_sort(existing_items, new_items, max_limit=200):
    """Gộp dữ liệu cũ và mới theo ngày, sắp xếp giảm dần và giữ tối đa 200 kỳ"""
    merged_dict = {item["date"]: item for item in existing_items}
    for item in new_items:
        merged_dict[item["date"]] = item

    # Sắp xếp ngày mới nhất lên đầu
    sorted_items = sorted(
        list(merged_dict.values()),
        key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"),
        reverse=True,
    )
    return sorted_items[:max_limit]


def main():
    data = load_data()

    # 1. Cào bảng 15 kỳ của Mega 6/45
    print("--- Đang cào bảng Mega 6/45 ---")
    mega_list = parse_minhchinh_table(
        "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-mega-645.html",
        "mega645",
    )
    print(f"Tìm thấy {len(mega_list)} kỳ Mega 6/45 từ Minh Chính.")

    # 2. Cào bảng 15 kỳ của Power 6/55
    print("--- Đang cào bảng Power 6/55 ---")
    power_list = parse_minhchinh_table(
        "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-power-655.html",
        "power655",
    )
    print(f"Tìm thấy {len(power_list)} kỳ Power 6/55 từ Minh Chính.")

    # Cập nhật và lưu lại
    if mega_list:
        data["mega645"] = merge_and_sort(data.get("mega645", []), mega_list)
    if power_list:
        data["power655"] = merge_and_sort(data.get("power655", []), power_list)

    if mega_list or power_list:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n=> Cập nhật file data.json thành công!")
        print(f"Tổng số kỳ Mega 6/45 hiện có: {len(data['mega645'])}")
        print(f"Tổng số kỳ Power 6/55 hiện có: {len(data['power655'])}")
    else:
        print("\n=> Không lấy được dữ liệu mới.")


if __name__ == "__main__":
    main()
