"""Cào kết quả Mega 6/45 và Power 6/55 từ Minh Chính, gộp vào data.json."""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
MAX_DRAWS = 200

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# max_ball: số lớn nhất; main: số bóng chính; bonus: có bóng phụ hay không
GAMES = {
    "mega645": {
        "url": "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-mega-645.html",
        "max_ball": 45,
        "main": 6,
        "bonus": False,
    },
    "power655": {
        "url": "https://www.minhchinh.com/truc-tiep-xo-so-tu-chon-power-655.html",
        "max_ball": 55,
        "main": 6,
        "bonus": True,
    },
}

# id thẻ chứa giá trị Jackpot trên minhchinh.com (lưu ý: id của Mega thực tế là "mega656_GT")
JACKPOT_IDS = {
    "mega645": {"jackpot": "mega656_GT"},
    "power655": {"jackpot": "power655_GT", "jackpot2": "power655_GT2"},
}
MIN_JACKPOT = 1_000_000_000  # dưới mức này coi là đọc sai (Jackpot thấp nhất là 3 tỷ)

DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")
DRAW_ID_RE = re.compile(r"(?:#|Kỳ\s*(?:QSMT)?\s*)(\d{4,6})", re.IGNORECASE)


def make_session():
    """Session có retry cho lỗi mạng / 5xx."""
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def load_data():
    """Tải dữ liệu cũ từ data.json nếu hợp lệ."""
    empty = {"mega645": [], "power655": [], "jackpots": {}}
    if not os.path.exists(DATA_FILE):
        return empty
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Cảnh báo: không đọc được {DATA_FILE}: {e}")
        return empty
    if not isinstance(content, dict):
        return empty
    for key in ("mega645", "power655"):
        if not isinstance(content.get(key), list):
            content[key] = []
    if not isinstance(content.get("jackpots"), dict):
        content["jackpots"] = {}
    return content


def save_data(data):
    """Ghi atomic để tránh hỏng file nếu bị ngắt giữa chừng."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DATA_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, DATA_FILE)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def extract_balls(row):
    """Lấy số từ các thẻ lá (không có thẻ con) để không đếm trùng khi thẻ lồng nhau."""
    balls = []
    for tag in row.find_all(["span", "div", "b", "strong"]):
        if tag.find(["span", "div", "b", "strong"]):
            continue
        text = tag.get_text(strip=True)
        if text.isdigit() and len(text) <= 2:
            balls.append(int(text))
    return balls


def parse_row(row, game_type):
    """Trả về dict kết quả của 1 dòng, hoặc None nếu dòng không hợp lệ."""
    cfg = GAMES[game_type]
    cells = row.find_all(["td", "th"])
    if len(cells) < 2:
        return None

    head_text = " ".join(c.get_text(" ", strip=True) for c in cells[:2])
    m_date = DATE_RE.search(cells[0].get_text(strip=True))
    if not m_date:
        return None
    date_str = m_date.group(1)
    try:
        datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        return None

    balls = extract_balls(row)
    need = cfg["main"] + (1 if cfg["bonus"] else 0)
    if len(balls) < need:
        return None
    balls = balls[:need]
    if any(not 1 <= b <= cfg["max_ball"] for b in balls):
        return None

    main_nums = balls[: cfg["main"]]
    if len(set(main_nums)) != cfg["main"]:
        return None  # 6 số chính phải khác nhau

    m_id = DRAW_ID_RE.search(head_text)
    item = {
        "draw": m_id.group(1) if m_id else date_str.replace("/", ""),
        "date": date_str,
        "numbers": sorted(main_nums),
    }
    if cfg["bonus"]:
        item["bonus"] = balls[cfg["main"]]
    return item


def parse_draws(soup, game_type):
    """Đọc các kỳ quay trong bảng kết quả."""
    results, seen = [], set()
    for row in soup.find_all("tr"):
        item = parse_row(row, game_type)
        if item and item["date"] not in seen:
            seen.add(item["date"])
            results.append(item)
    return results


def parse_money(text):
    """'40,971,513,000' -> 40971513000"""
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits else None


def parse_jackpots(soup, game_type):
    """Đọc giá trị Jackpot hiện tại. Ưu tiên theo id, dự phòng theo thứ tự trong khối giatri_jackpot."""
    live = soup.select(".giatri_jackpot .gtblive")
    found = {}
    for idx, (key, el_id) in enumerate(JACKPOT_IDS[game_type].items()):
        el = soup.find(id=el_id)
        if el is None and idx < len(live):
            el = live[idx]
        if el is None:
            continue
        value = parse_money(el.get_text())
        if value and value >= MIN_JACKPOT:
            found[key] = value
    return found


def fetch_game(session, game_type):
    """Tải trang một lần, trả về (danh sách kỳ quay, dict jackpot)."""
    cfg = GAMES[game_type]
    try:
        res = session.get(cfg["url"], timeout=25)
        res.raise_for_status()
        res.encoding = "utf-8"
    except requests.RequestException as e:
        print(f"Lỗi kết nối {game_type}: {e}")
        return [], {}
    soup = BeautifulSoup(res.text, "html.parser")
    return parse_draws(soup, game_type), parse_jackpots(soup, game_type)


def update_jackpots(data, game_type, new_values):
    """Chỉ ghi lại (kèm mốc thời gian) khi giá trị thực sự đổi, để tránh commit thừa."""
    if not new_values:
        return
    store = data.setdefault("jackpots", {})
    old = store.get(game_type, {})
    old_values = {k: v for k, v in old.items() if k != "updated"}
    if new_values != old_values:
        store[game_type] = {
            **new_values,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }


def merge_and_sort(existing_items, new_items, max_limit=MAX_DRAWS):
    """Gộp theo ngày (bản mới ghi đè), sắp xếp mới nhất trước, giữ tối đa max_limit kỳ."""
    merged = {}
    for item in existing_items:
        try:
            datetime.strptime(item["date"], "%d/%m/%Y")
        except (KeyError, TypeError, ValueError):
            continue  # bỏ dòng hỏng trong file cũ
        merged[item["date"]] = item
    for item in new_items:
        merged[item["date"]] = item

    ordered = sorted(
        merged.values(),
        key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"),
        reverse=True,
    )
    return ordered[:max_limit]


def main():
    data = load_data()
    old_snapshot = json.dumps(data, sort_keys=True, ensure_ascii=False)
    session = make_session()
    fetched_any = False

    for game_type in GAMES:
        print(f"--- Đang cào {game_type} ---")
        items, jackpots = fetch_game(session, game_type)
        print(f"Tìm thấy {len(items)} kỳ, jackpot: {jackpots or 'không đọc được'}.")
        if items:
            data[game_type] = merge_and_sort(data.get(game_type, []), items)
        update_jackpots(data, game_type, jackpots)
        if items or jackpots:
            fetched_any = True

    if not fetched_any:
        print("=> Không lấy được dữ liệu mới.")
        return 1

    if json.dumps(data, sort_keys=True, ensure_ascii=False) == old_snapshot:
        print("=> Không có thay đổi, giữ nguyên data.json.")
        return 0

    save_data(data)
    print("=> Cập nhật data.json thành công!")
    for game_type in GAMES:
        print(f"Tổng số kỳ {game_type}: {len(data[game_type])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
