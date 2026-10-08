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
    ),
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
}


def load_existing_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    return content
        except Exception:
            pass
    return {"mega645": [], "power655": []}


def crawl_atrungroi(url, game_type):
    """Cào kết quả từ nguồn mở không chặn IP quốc tế của GitHub Actions"""
    results = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=25)
        res.encoding = "utf-8"
        if res.status_code != 200:
            print(f"Không thể truy cập {url} (HTTP {res.status_code})")
            return results

        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        if game_type == "mega645":
            matches = re.finditer(
                r"Kỳ quay(?: thưởng)?\s*#?(\d+)[^\d]+?(\d{1,2}/\d{1,2}/\d{4})[^\d]+?(\d{12})\b",
                text,
            )
            for m in matches:
                draw_id = m.group(1).zfill(5)
                date_str = m.group(2)
                raw_nums = m.group(3)
                numbers = sorted(
                    [int(raw_nums[i : i + 2]) for i in range(0, 12, 2)]
                )

                if (
                    len(numbers) == 6
                    and all(1 <= x <= 45 for x in numbers)
                    and not any(r["draw"] == draw_id for r in results)
                ):
                    results.append(
                        {"draw": draw_id, "date": date_str, "numbers": numbers}
                    )

        else:
            matches = re.finditer(
                r"Kỳ quay(?: thưởng)?\s*#?(\d+)[^\d]+?(\d{1,2}/\d{1,2}/\d{4})[^\d]+?(\d{14})\b",
                text,
            )
            for m in matches:
                draw_id = m.group(1).zfill(5)
                date_str = m.group(2)
                raw_nums = m.group(3)
                main_nums = sorted(
                    [int(raw_nums[i : i + 2]) for i in range(0, 12, 2)]
                )
                bonus = int(raw_nums[12:14])

                if (
                    len(main_nums) == 6
                    and all(1 <= x <= 55 for x in main_nums)
                    and not any(r["draw"] == draw_id for r in results)
                ):
                    results.append(
                        {
                            "draw": draw_id,
                            "date": date_str,
                            "numbers": main_nums,
                            "bonus": bonus,
                        }
                    )

    except Exception as e:
        print(f"Lỗi khi cào {game_type}: {e}")

    return results


def merge_records(existing, new_items):
    merged = {item["draw"]: item for item in existing}
    for item in new_items:
        merged[item["draw"]] = item
    return sorted(
        list(merged.values()),
        key=lambda x: int(x["draw"]) if str(x["draw"]).isdigit() else 0,
        reverse=True,
    )[:200]


def main():
    data = load_existing_data()

    print("--- Đang cào Mega 6/45 ---")
    mega_crawled = crawl_atrungroi(
        "https://atrungroi.com/xstc-xo-so-tu-chon-mega-645-vietlott.html",
        "mega645",
    )
    print(f"Tìm thấy {len(mega_crawled)} kỳ Mega 6/45")

    print("--- Đang cào Power 6/55 ---")
    power_crawled = crawl_atrungroi(
        "https://atrungroi.com/xo-so-power-6-55-vietlott.html",
        "power655",
    )
    print(f"Tìm thấy {len(power_crawled)} kỳ Power 6/55")

    if mega_crawled:
        data["mega645"] = merge_records(data.get("mega645", []), mega_crawled)
    if power_crawled:
        data["power655"] = merge_records(data.get("power655", []), power_crawled)

    if data["mega645"] or data["power655"]:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Đã cập nhật thành công data.json!")
    else:
        print("Không có dữ liệu mới, giữ nguyên file cũ.")


if __name__ == "__main__":
    main()
