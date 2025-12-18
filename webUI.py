import requests
import json
import datetime
import random
import math
import xml.etree.ElementTree as ET


class Tools:
    def __init__(self):
        pass

    # --- 1. 天氣 (升級版：支援中文 + 台灣優先 + 真實降雨機率) ---
    def get_weather(self, city: str) -> str:
        """
        Get current weather and rain chance for a city.
        Supports Chinese and English city names.
        :param city: City name (e.g. "Taipei", "台北", "Tainan").
        """
        try:
            print(f"[System] Getting weather for {city}...")
            headers = {"User-Agent": "Mozilla/5.0"}

            # 1. 查經緯度 (中文相容 + 台灣優先)
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {"name": city, "count": 5, "format": "json"}

            geo_res = requests.get(
                geo_url, params=params, headers=headers, verify=False, timeout=5
            )
            geo_data = geo_res.json()

            if "results" not in geo_data:
                return f"Error: City '{city}' not found."

            # --- 台灣優先演算法 ---
            target_result = geo_data["results"][0]
            for res in geo_data["results"]:
                if res.get("country_code") == "TW":
                    target_result = res
                    break
            # --------------------

            lat = target_result["latitude"]
            lon = target_result["longitude"]
            city_name = target_result["name"]
            country = target_result.get("country", "Unknown")

            # 2. 查天氣 (關鍵修改：新增 daily=precipitation_probability_max)
            # timezone=auto 很重要，這樣才能抓到當地正確日期的降雨機率
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current_weather=true"
                f"&daily=precipitation_probability_max"
                f"&timezone=auto"
            )

            weather_res = requests.get(
                weather_url, headers=headers, verify=False, timeout=5
            )
            w_data = weather_res.json()

            # 解析目前天氣
            current = w_data["current_weather"]

            # 解析降雨機率 (抓今天的第一筆資料)
            if "daily" in w_data and "precipitation_probability_max" in w_data["daily"]:
                rain_prob = w_data["daily"]["precipitation_probability_max"][0]
                rain_msg = f"Rain Chance: {rain_prob}%"
            else:
                rain_msg = "Rain Chance: Unknown"

            # WMO 代碼翻譯
            wmo_code = current["weathercode"]
            condition = "Clear"
            if wmo_code in [1, 2, 3]:
                condition = "Cloudy (多雲)"
            elif wmo_code in [45, 48]:
                condition = "Foggy (有霧)"
            elif wmo_code in [51, 53, 55, 61, 63, 65]:
                condition = "Rainy (下雨)"
            elif wmo_code >= 80:
                condition = "Storm/Showers (雷雨/陣雨)"

            return (
                f"Weather in {city_name}, {country}: "
                f"{condition} (Code {wmo_code}), "
                f"Temp: {current['temperature']}°C, "
                f"Wind: {current['windspeed']} km/h, "
                f"{rain_msg}"
            )  # 這裡把降雨機率加進去回傳字串

        except Exception as e:
            return f"Weather API Error: {str(e)}"

    # --- 2. 虛擬貨幣 (維持：強制轉英文幣名) ---
    def get_crypto_price(self, coin_name: str) -> str:
        """
        Get cryptocurrency price and 24h change.

        IMPORTANT: The API requires the English ID of the cryptocurrency.
        If the user asks for "比特幣", you MUST pass "bitcoin".
        If the user asks for "以太幣", you MUST pass "ethereum".

        :param coin_name: The English ID of the cryptocurrency (lowercase).
        """
        try:
            coin_id = coin_name.lower()
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            data = res.json()

            if coin_id in data:
                price = data[coin_id]["usd"]
                change = data[coin_id].get("usd_24h_change", 0)
                change_str = f"{change:+.2f}%"
                return f"{coin_name.title()}: ${price:,} USD (24h Change: {change_str})"
            return f"Error: '{coin_name}' not found. Try English ID (e.g., bitcoin)."
        except Exception as e:
            return f"Crypto API Error: {str(e)}"

    # --- 3. 新聞 (維持中文搜尋，前 5 則) ---
    def get_news(self, query: str) -> str:
        """
        Search for latest news headlines from Google News.
        This function supports Chinese keywords directly.

        :param query: Keywords to search (e.g., "Taiwan", "Technology").
        """
        try:
            url = f"https://news.google.com/rss/search?q={query}+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers, timeout=5)

            if res.status_code != 200:
                return f"Google News Error: {res.status_code}"

            root = ET.fromstring(res.content)
            items = root.findall("./channel/item")

            if not items:
                return "Google News found no results."

            news_output = f"【Latest News for '{query}'】\n"
            for i, item in enumerate(items[:5], 1):
                title = item.find("title").text
                pubDate = item.find("pubDate").text
                news_output += f"{i}. {title} ({pubDate})\n"

            return news_output

        except Exception as e:
            return f"News Tool Error: {str(e)}"

    # --- 4. 維基百科 (維持模糊搜尋) ---
    def get_wikipedia_summary(self, keyword: str) -> str:
        """
        Search Wikipedia summary.
        Supports both Chinese and English keywords.
        :param keyword: The search term.
        """
        try:
            search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={keyword}&format=json"
            search_res = requests.get(search_url, timeout=5).json()
            if "query" in search_res and "search" in search_res["query"]:
                results = search_res["query"]["search"]
                if len(results) > 0:
                    title = results[0]["title"]
                    summary_url = (
                        f"https://zh.wikipedia.org/api/rest_v1/page/summary/{title}"
                    )
                    summary_res = requests.get(summary_url, timeout=5)
                    if summary_res.status_code == 200:
                        return f"Wiki ({title}): {summary_res.json().get('extract', 'No summary')}"
            return "Wiki: No result found."
        except Exception as e:
            return f"Wiki Error: {e}"

    # --- 5. 安全數學計算機 ---
    def calculate_expression(self, expression: str) -> str:
        """
        Calculate math expression.
        :param expression: Math string (e.g., "23 * 45").
        """
        try:
            safe_dict = {
                "__builtins__": None,
                "math": math,
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
            }
            for name in dir(math):
                if not name.startswith("__"):
                    safe_dict[name] = getattr(math, name)
            result = eval(expression, safe_dict)
            return f"Result: {result}"
        except Exception as e:
            return f"Math Error: {e}"

    # --- 6. 時間與骰子 ---
    # --- 6. 時間 (修正版：強制鎖定台灣時區 UTC+8) ---
    def get_current_time(self) -> str:
        """Get current time in Taiwan (UTC+8)."""
        # 1. 取得標準 UTC 時間
        utc_now = datetime.datetime.now(datetime.timezone.utc)

        # 2. 手動加 8 小時
        tw_time = utc_now + datetime.timedelta(hours=8)

        return f"現在時間 (台灣): {tw_time.strftime('%Y-%m-%d %H:%M:%S')}"

    def roll_dice(self) -> str:
        """Roll a 6-sided dice."""
        return f"Dice Result: {random.randint(1, 6)}"
        
    # --- 7. 查詢MLB選手的數據 ---
    def get_mlb_stats(self, player_name: str) -> str:
        """
        Get current batting stats (AVG, HR, OPS) for an MLB player.
        Uses the official public MLB Stats API (No Key required).
        
        :param player_name: Player's name (English preferred, e.g., "Shohei Ohtani", "Aaron Judge").
        """
        try:
            print(f"[System] Searching MLB stats for '{player_name}'...")
            
            search_url = "https://statsapi.mlb.com/api/v1/people/search"
            params = {"names": player_name, "active": "true"} # 只找現役球員
            
            res = requests.get(search_url, params=params, timeout=5)
            data = res.json()
            
            if "people" not in data or len(data["people"]) == 0:
                return f"Error: MLB Player '{player_name}' not found. Try full English name (e.g., 'Shohei Ohtani')."

            player = data["people"][0]
            player_id = player["id"]
            full_name = player["fullName"]
            team_name = "Free Agent" # 預設自由球員
            
            current_team_link = player.get("currentTeam", {}).get("link", "")
            if current_team_link:
                 pass

            stats_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
            stats_params = {
                "hydrate": "stats(group=[hitting],type=[season])"
            }
            
            stats_res = requests.get(stats_url, params=stats_params, timeout=5)
            stats_data = stats_res.json()
            try:
                stats_container = stats_data["people"][0]["stats"]
                
                hitting_stats = None
                for group in stats_container:
                    if group["group"]["displayName"] == "hitting" and "splits" in group:
                        if len(group["splits"]) > 0:
                            hitting_stats = group["splits"][-1]
                            break
                
                if hitting_stats:
                    season = hitting_stats.get("season", "Unknown")
                    stat_body = hitting_stats["stat"]
                    
                    avg = stat_body.get("avg", ".---")  # 打擊率
                    hr = stat_body.get("homeRuns", 0)   # 全壘打
                    ops = stat_body.get("ops", ".---")  # 整體攻擊指數
                    hits = stat_body.get("hits", 0)     # 安打數
                    games = stat_body.get("gamesPlayed", 0)

                    return (
                        f"⚾ MLB Stats: {full_name} ({season} Season)\n"
                        f"----------------------------------\n"
                        f"📊 Batting Average (AVG): {avg}\n"
                        f"🚀 Home Runs (HR): {hr}\n"
                        f"💪 OPS: {ops}\n"
                        f"⚾ Hits: {hits} in {games} games\n"
                        f"(Source: official statsapi.mlb.com)"
                    )
                else:
                    return f"No hitting stats found for {full_name} (Might be a Pitcher or inactive)."

            except (KeyError, IndexError):
                return f"Error parsing stats for {full_name}. Structure changed or no data."

        except Exception as e:
            return f"MLB Tool Error: {str(e)}"


