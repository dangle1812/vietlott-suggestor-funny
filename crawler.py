import json
import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

DATA_FILE = "data.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def load_existing_data():
    """Tải dữ liệu đã có từ data.json."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc {DATA_FILE}: {e}")
    return {"mega645": [], "power655": []}


def crawl_vietlott_page(game_type, page_index=1):
    """
    Cào dữ liệu danh sách kỳ quay từ trang kết quả Vietlott theo phân trang.
    game_type: '645' hoặc '655'
    """
    url = f"https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong/{game_type}?pageIndex={page_index}"
    results = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.encoding = "utf-8"
        if res.status_code != 200:
            return results

        soup = BeautifulSoup(res.text, "html.parser")
        # Tìm các khối kết quả hoặc bảng kỳ quay
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                text = row.get_text(" ", strip=True)
                # Tìm mã kỳ quay (#01xxx hoặc 01xxx)
                match_id = re.search(r"#?(\d{5})", text)
                match_date = re.search(r"(\d{2}/\d{2}/\d{4})", text)

                balls = []
                for b in row.find_all(["span", "div", "b"]):
                    val = b.get_text(strip=True)
                    if val.isdigit() and len(val) <= 2:
                        balls.append(int(val))

                if match_id and len(balls) >= 6:
                    draw_id = match_id.group(1)
                    draw_date = (
                        match_date.group(1)
                        if match_date
                        else datetime.now().strftime("%d/%m/%Y")
                    )
                    main_nums = sorted(balls[:6])

                    item = {
                        "draw": draw_id,
                        "date": draw_date,
                        "numbers": main_nums,
                    }
                    if game_type == "655" and len(balls) >= 7:
                        item["bonus"] = balls[6]

                    # Tránh thêm trùng trong cùng 1 trang
                    if not any(r["draw"] == draw_id for r in results):
                        results.append(item)

        # Fallback: Quét thẻ bong_tron trực tiếp nếu không nằm trong bảng
        if not results:
            balls = [
                int(s.get_text(strip=True))
                for s in soup.select("span.bong_tron")
                if s.get_text(strip=True).isdigit()
            ]
            match_id = re.search(r"#?(\d{5})", soup.get_text())
            match_date = re.search(r"(\d{2}/\d{2}/\d{4})", soup.get_text())
            if match_id and len(balls) >= 6:
                item = {
                    "draw": match_id.group(1),
                    "date": match_date.group(1)
                    if match_date
                    else datetime.now().strftime("%d/%m/%Y"),
                    "numbers": sorted(balls[:6]),
                }
                if game_type == "655" and len(balls) >= 7:
                    item["bonus"] = balls[6]
                results.append(item)

    except Exception as e:
        print(f"Lỗi cào {game_type} trang {page_index}: {e}")

    return results


def sync_game_data(existing_list, game_type, target_count=200):
    """Đồng bộ và cào ngược lịch sử cho đủ target_count kỳ (mặc định 200)."""
    current_dict = {item["draw"]: item for item in existing_list}
    page = 1
    max_pages = 25  # Mỗi trang ~10 kỳ quay, 20-25 trang là đủ 200 kỳ

    print(f"--- Đang đồng bộ {game_type} (Mục tiêu: {target_count} kỳ) ---")
    while len(current_dict) < target_count and page <= max_pages:
        new_items = crawl_vietlott_page(game_type, page_index=page)
        if not new_items:
            break

        added = 0
        for it in new_items:
            if it["draw"] not in current_dict:
                current_dict[it["draw"]] = it
                added += 1

        print(
            f"Trang {page}: Thêm {added} kỳ mới. Tổng cộng hiện có: {len(current_dict)}"
        )
        if added == 0 and page > 2:
            break
        page += 1

    # Sắp xếp theo mã kỳ quay giảm dần (mới nhất lên đầu)
    sorted_items = sorted(
        list(current_dict.values()),
        key=lambda x: int(x["draw"]) if str(x["draw"]).isdigit() else 0,
        reverse=True,
    )
    # Cắt gọn đúng 200 kỳ gần nhất
    return sorted_items[:target_count]


def main():
    data = load_existing_data()
    data["mega645"] = sync_game_data(
        data.get("mega645", []), "645", target_count=200
    )
    data["power655"] = sync_game_data(
        data.get("power655", []), "655", target_count=200
    )

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(
        f"\nHoàn tất! Đã lưu: {len(data['mega645'])} kỳ Mega 6/45 và {len(data['power655'])} kỳ Power 6/55 vào {DATA_FILE}"
    )


if __name__ == "__main__":
    main()
