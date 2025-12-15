import requests
import json
import datetime
import random
import math

class Tools:
    def __init__(self):
        pass

    def get_weather(self, city: str) -> str:
        """
        查詢某個城市的即時天氣 (使用 Open-Meteo API，解決 Docker 連線問題)。
        :param city: 城市英文名稱 (例如: "Tainan", "Taipei")
        """
        try:
            print(f"   [系統] 正在查詢 {city} 的經緯度...")
            # 1. 偽裝 Header (避免被擋)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # 2. 先查經緯度 (Geocoding)
            # 使用 verify=False 跳過 SSL 驗證，確保 Docker 內一定能連
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
            geo_res = requests.get(geo_url, headers=headers, verify=False, timeout=10)
            geo_data = geo_res.json()

            if "results" not in geo_data:
                return f"找不到城市: {city}，請嘗試使用英文名稱 (如 Tainan)。"

            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            city_name = geo_data["results"][0]["name"]

            # 3. 再查天氣
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather_res = requests.get(weather_url, headers=headers, verify=False, timeout=10)
            weather_data = weather_res.json()

            if "current_weather" in weather_data:
                temp = weather_data["current_weather"]["temperature"]
                wind = weather_data["current_weather"]["windspeed"]
                return f"Weather in {city_name}: Temperature {temp}°C, Wind Speed {wind} km/h"
            else:
                return "無法取得氣象資料"

        except Exception as e:
            return f"API 連線錯誤: {str(e)}"
    def get_crypto_price(self, coin_name: str) -> str:
        """
        查詢加密貨幣的即時美金價格。
        :param coin_name: 貨幣英文名稱 (例如: "bitcoin")
        """
        try:
            coin_id = coin_name.lower()
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = response.json()
            if coin_id in data:
                return f"{coin_name} 目前價格: {data[coin_id]['usd']} USD"
            return f"找不到 {coin_name}"
        except:
            return "價格查詢失敗"

    def get_wikipedia_summary(self, keyword: str) -> str:
        """
        查詢維基百科摘要。
        :param keyword: 搜尋關鍵字
        """
        try:
            search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={keyword}&format=json"
            search_res = requests.get(search_url).json()
            if "query" in search_res and "search" in search_res["query"]:
                results = search_res["query"]["search"]
                if len(results) > 0:
                    best_title = results[0]["title"]
                    summary_url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{best_title}"
                    summary_res = requests.get(summary_url)
                    if summary_res.status_code == 200:
                        data = summary_res.json()
                        return f"維基百科 ({best_title}): {data.get('extract', '無摘要')}"
            return "搜尋不到結果"
        except Exception as e:
            return f"維基百科錯誤: {e}"

    def calculate_expression(self, expression: str) -> str:
        """
        執行數學運算。
        :param expression: 數學算式 (例如: "23*45")
        """
        try:
            allowed_names = {"math": math, "abs": abs, "round": round}
            result = eval(expression, {"__builtins__": None}, allowed_names)
            return f"計算結果: {result}"
        except Exception as e:
            return f"計算錯誤: {e}"

    def get_current_time(self) -> str:
        """
        查詢現在時間。
        """
        now = datetime.datetime.now()
        return f"現在時間: {now.strftime('%Y-%m-%d %H:%M:%S')}"

    def roll_dice(self) -> str:
        """
        擲骰子。
        """
        return f"骰子結果: {random.randint(1, 6)} 點"