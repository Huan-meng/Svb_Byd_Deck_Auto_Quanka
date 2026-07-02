import os
import time
import re
import csv
import requests
from io import BytesIO
from PIL import Image

# 1. 定义职业映射
CLASS_MAPPING = {
    0: "中立",
    1: "妖精",
    2: "皇家",
    3: "法师",
    4: "龙族",
    5: "梦魇",
    6: "主教",
    7: "超越者",
}

API_URL = "https://shadowverse-wb.com/web/CardList/cardList?include_token=1"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "lang": "chs",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "referer": "https://shadowverse-wb.com/chs/deck/cardslist/",
}

SAVE_DIR = "SV_WB_Cards"
CSV_FILE = os.path.join(SAVE_DIR, "SV_WB_Cards.csv")


def build_card_dictionary():
    """爬取并保存全卡牌字典到 CSV"""
    print("================ 开始更新本地卡牌数据库 ================")
    card_db = {}

    for cls_id in range(8):
        offset = 0
        page_num = 1
        print(f"正在爬取职业 {cls_id} 的卡牌数据...")

        while True:
            params = {
                "offset": offset,
                "class": cls_id,
                "cost": "0,1,2,3,4,5,6,7,8,9,10",
            }

            try:
                response = requests.get(
                    API_URL, headers=HEADERS, params=params, timeout=10
                )
                response.raise_for_status()
                json_data = response.json()
            except Exception as e:
                print(f"  [!] 请求失败: {e}")
                break

            data_block = json_data.get("data", {})
            card_details = data_block.get("card_details", {})
            sort_card_id_list = data_block.get("sort_card_id_list", [])

            if not sort_card_id_list:
                break

            for card_id in sort_card_id_list:
                card_info = card_details.get(str(card_id))
                if not card_info:
                    continue

                common_info = card_info.get("common", {})
                name = common_info.get("name", f"未知卡牌_{card_id}")
                cost = common_info.get("cost", 0)

                card_db[str(card_id)] = {"name": name, "cost": cost}

                style_list = card_info.get("style_card_list", [])
                if isinstance(style_list, list):
                    for idx, style in enumerate(style_list, start=1):
                        style_name = style.get("name", "").strip()
                        if not style_name:
                            style_name = name
                        card_db[f"{card_id}@{idx}"] = {"name": style_name, "cost": cost}

            offset += len(sort_card_id_list)
            page_num += 1
            time.sleep(0.5)

    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(CSV_FILE, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["card_id", "cost", "name"])
        for cid, info in card_db.items():
            writer.writerow([cid, info["cost"], info["name"]])

    print(f"✅ 数据库更新完毕！共记录 {len(card_db)} 张卡牌，已保存至 {CSV_FILE}\n")


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\/:*?"<>|]', "_", str(name))


def download_and_convert_to_webp(img_url, save_path):
    """下载 PNG 图片并在内存中直接转换为 WEBP 保存"""
    if os.path.exists(save_path):
        print(f"  [-] 已存在跳过: {os.path.basename(save_path)}")
        return
    try:
        # 下载图片到内存
        response = requests.get(img_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            # 使用 PIL 读取内存中的二进制图片数据
            image = Image.open(BytesIO(response.content))

            # 转换为 WebP 格式并保存 (quality=90 能在体积和画质间取得极佳平衡，且支持透明通道)
            image.save(save_path, "WEBP", quality=90)

            print(f"  [+] 成功下载并转换: {os.path.basename(save_path)}")
        else:
            print(f"  [!] 下载失败，状态码 {response.status_code}: {img_url}")
    except Exception as e:
        print(f"  [!] 请求/转换出错: {e}")


def main():
    os.makedirs(SAVE_DIR, exist_ok=True)

    build_card_dictionary()

    for cls_id, cls_name in CLASS_MAPPING.items():
        print(f"\n================ 开始爬取职业: {cls_name} ================")
        class_dir = os.path.join(SAVE_DIR, cls_name)
        os.makedirs(class_dir, exist_ok=True)

        offset = 0
        page_num = 1

        while True:
            print(
                f"--> 正在请求 {cls_name} 的第 {page_num} 页数据 (offset={offset})..."
            )

            params = {
                "offset": offset,
                "class": cls_id,
                "cost": "0,1,2,3,4,5,6,7,8,9,10",
                # "card_set":10007 增量更新则取消注释
            }

            try:
                response = requests.get(
                    API_URL, headers=HEADERS, params=params, timeout=10
                )
                response.raise_for_status()
                json_data = response.json()
            except Exception as e:
                print(f"请求失败: {e}")
                break

            data_block = json_data.get("data", {})
            card_details = data_block.get("card_details", {})
            sort_card_id_list = data_block.get("sort_card_id_list", [])

            if not sort_card_id_list:
                print(f"[{cls_name}] 职业数据已到底，抓取完毕。")
                break

            for card_id in sort_card_id_list:
                card_info = card_details.get(str(card_id))
                # print(card_info)
                if not card_info:
                    continue

                # 获取数据块
                common_info = card_info.get("common", {})
                evo_info = card_info.get("evo", {})
                style_list = card_info.get("style_card_list", [])

                # --- 提取核心数值信息 ---
                card_name = common_info.get("name", f"未知卡牌_{card_id}")
                # safe_name = sanitize_filename(card_name)
                safe_name = sanitize_filename(card_id)

                cost = common_info.get("cost", 0)
                atk = common_info.get("atk", 0)
                life = common_info.get("life", 0)
                card_type = common_info.get("type", 1)  # 1 为随从

                # --- 检测爆能强化 ---
                skill_text = common_info.get("skill_text", "")
                burst_matches = re.findall(r"爆能强化</color>_(\d+)", skill_text)
                if burst_matches:
                    cost_str = f"{cost}@{'@'.join(burst_matches)}"
                else:
                    cost_str = str(cost)

                base_hash = common_info.get("card_image_hash")
                has_evo = isinstance(evo_info, dict) and "card_image_hash" in evo_info

                # --- 1. 基础卡图命名 ---
                if base_hash:
                    if card_type == 1:
                        filename = f"{cost_str}_{safe_name}_{atk}_{life}.webp"
                    else:
                        filename = f"{cost_str}_{safe_name}.webp"

                    img_url = f"https://shadowverse-wb.com/uploads/card_image/chs/card/{base_hash}.png"
                    download_and_convert_to_webp(
                        img_url, os.path.join(class_dir, filename)
                    )

                # --- 2. 进化后卡图命名 ---
                if has_evo:
                    evo_hash = evo_info.get("card_image_hash")
                    if evo_hash:
                        evo_filename = f"{cost_str}_{safe_name}_evo.webp"
                        evo_url = f"https://shadowverse-wb.com/uploads/card_image/chs/card/{evo_hash}.png"
                        download_and_convert_to_webp(
                            evo_url, os.path.join(class_dir, evo_filename)
                        )

                # --- 3. 异画卡图命名 (智能判断) ---
                if isinstance(style_list, list) and len(style_list) > 0:
                    for idx, style in enumerate(style_list, start=1):
                        style_hash = style.get("hash")
                        style_evo_hash = style.get("evo_hash")

                        # 核心逻辑：判断异画名字
                        raw_style_name = style.get("name", "").strip()

                        # 如果 JSON 中没有配名字，或者名字和原卡完全一样
                        # if not raw_style_name or raw_style_name == card_name:
                        #     # 为防止个别卡牌有多张同名异画导致覆盖，如果有多个则加上序号
                        #     suffix = "(异画)" if len(style_list) == 1 else f"(异画{idx})"
                        #     style_safe_name = f"{safe_name}{suffix}"
                        # else:
                        #     # 异画有自己的专属名字 (例如联动皮肤卡)
                        #     #style_safe_name = sanitize_filename(raw_style_name)
                        #     style_safe_name = sanitize_filename(card_id)

                        style_safe_name = f"{safe_name}@{idx}"
                        # 下载异画进化前
                        if style_hash:
                            if card_type == 1:
                                style_filename = (
                                    f"{cost_str}_{style_safe_name}_{atk}_{life}.webp"
                                )
                            else:
                                style_filename = f"{cost_str}_{style_safe_name}.webp"

                            style_url = f"https://shadowverse-wb.com/uploads/card_image/chs/card/{style_hash}.png"
                            download_and_convert_to_webp(
                                style_url, os.path.join(class_dir, style_filename)
                            )

                        # 下载异画进化后
                        if style_evo_hash:
                            style_evo_filename = (
                                f"{cost_str}_{style_safe_name}_evo.webp"
                            )
                            style_evo_url = f"https://shadowverse-wb.com/uploads/card_image/chs/card/{style_evo_hash}.png"
                            download_and_convert_to_webp(
                                style_evo_url,
                                os.path.join(class_dir, style_evo_filename),
                            )

            # 翻页
            offset += len(sort_card_id_list)
            page_num += 1

            time.sleep(1)  # 礼貌延迟，保护服务器


if __name__ == "__main__":
    main()
