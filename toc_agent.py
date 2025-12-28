"""
title: TOC Agent (Triple-Key Ultimate)
author: NCKU Student & Gemini
description: Optimized with 3 API Keys for perfect parallel processing.
requirements: python-statemachine, requests, pydantic
version: 9.0.0 (Instant Intent Reflex)
"""

import os
import requests
import json
import datetime
import time
import re
import concurrent.futures
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from statemachine import StateMachine, State

GLOBAL_USER_STATES = {}


# ==========================================
# 🔑 金鑰管理系統 (三 Key 完美輪詢)
# ==========================================
class KeyManager:
    KEYS = [
        "253b609e99624ea28f7f036e9d4d363b2ad71b853b3fd7b986b12be2b014ff69",
        "ea00b6195cbab7342f1e99824c0d4808c087438d0061fb07b8ab39186b1db778",
        "2ef233a5993082e09a4533e76c0e8cb2614388ea27cb35b25de9b4d91891a78e",
    ]
    _index = 0

    @classmethod
    def get_headers(cls):
        current_key = cls.KEYS[cls._index]
        cls._index = (cls._index + 1) % len(cls.KEYS)
        return {
            "Authorization": f"Bearer {current_key}",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }


# ==========================================
# 🧠 記憶系統
# ==========================================
class MemorySystem:
    FILE_PATH = "./toc_memory.json"

    @staticmethod
    def load_memory():
        if not os.path.exists(MemorySystem.FILE_PATH):
            return []
        try:
            with open(MemorySystem.FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    @staticmethod
    def save_memory(content: str):
        memories = MemorySystem.load_memory()
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content,
        }
        memories.append(entry)
        try:
            with open(MemorySystem.FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
            return f"✅ 已記錄：{content}"
        except Exception as e:
            return f"❌ 寫入失敗：{e}"

    @staticmethod
    def get_context_string():
        memories = MemorySystem.load_memory()
        if not memories:
            return "目前沒有任何記憶。"
        recent = memories[-15:]
        context = "【使用者的記憶庫】:\n"
        for mem in recent:
            context += f"- [{mem['timestamp']}] {mem['content']}\n"
        return context


class ZoneMemory:
    @staticmethod
    def handle(action: str, content: str):
        if action == "SAVE":
            yield MemorySystem.save_memory(content)
        elif action == "QUERY":
            context = MemorySystem.get_context_string()
            prompt = (
                f"You are a helpful assistant with access to user memory.\n"
                f"{context}\n\nUser Question: {content}\n"
                f"If the answer is not in the memory, say '我記得的資料裡沒有提到這件事'.\nAnswer:"
            )
            yield from Tools._call_smart(prompt)


# ==========================================
# 🧱 基礎建設
# ==========================================
class Tools:
    API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
    MODEL_NAME = "gpt-oss:20b"

    @staticmethod
    def _call_stream_generator(
        prompt: str, temperature: float = 0.7
    ) -> Generator[str, None, None]:
        response = None
        try:
            headers = KeyManager.get_headers()
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "temperature": temperature,
                "max_tokens": 1500,
            }
            response = requests.post(
                Tools.API_URL,
                headers=headers,
                json=payload,
                stream=True,
                timeout=(10, 180),
            )
            if response.status_code != 200:
                return

            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        json_str = decoded.replace("data: ", "")
                        if json_str == "[DONE]":
                            response.close()
                            break
                        try:
                            data = json.loads(json_str)
                            content = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if content:
                                yield content
                        except:
                            pass
        except:
            pass
        finally:
            if response:
                response.close()

    @staticmethod
    def _call_block(prompt: str, temperature: float = 0.7) -> str:
        try:
            headers = KeyManager.get_headers()
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": temperature,
            }
            res = requests.post(
                Tools.API_URL, headers=headers, json=payload, timeout=180
            )
            if res.status_code == 200:
                return res.json().get("message", {}).get("content", "").strip()
            return f"Error: {res.status_code}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _call_smart(prompt: str) -> Generator[str, None, None]:
        stream_gen = Tools._call_stream_generator(prompt)
        has_content = False
        try:
            for chunk in stream_gen:
                has_content = True
                yield chunk
        except:
            pass

        if not has_content:
            yield " (轉為穩定模式...)\n"
            yield Tools._call_block(prompt)

    @staticmethod
    def analyze_intent_only(user_msg: str) -> str:
        """
        🚀 v9.0 關鍵優化：先用 Keyword 判斷，沒結果才問 LLM。
        這能讓「我想去...」這類開頭直接跳過一次 API 呼叫。
        """
        msg = user_msg.strip()

        # 1. 光速關鍵字判斷 (優先於 LLM)
        if any(k in msg for k in ["天氣", "氣溫", "預報"]):
            return "WEATHER"
        if any(k in msg for k in ["記住", "紀錄", "記憶"]):
            return "MEMORY_SAVE"
        if any(k in msg for k in ["查詢", "回憶", "搜索"]):
            return "MEMORY_QUERY"

        # 旅遊關鍵字神經反射
        travel_keywords = ["旅遊", "旅行", "行程", "一日遊", "二日遊", "好玩", "日遊"]
        exclude_words = [
            "去年",
            "過去",
            "失去",
            "去除",
            "回去",
            "下去",
            "上去",
            "進去",
            "出去",
        ]

        has_travel_keyword = any(k in msg for k in travel_keywords)
        # 判斷「去」的邏輯：排除不相關的詞，且後面要有接東西
        has_valid_go = False
        if "去" in msg and not any(bad in msg for bad in exclude_words):
            try:
                idx = msg.index("去")
                if idx < len(msg) - 1:
                    suffix = msg[idx + 1 :].strip()
                    # 確保後面不是標點符號，且長度足夠 (避免 '去死' 等單字誤判)
                    if len(suffix) >= 2 and suffix[0] not in ["，", "。", "！", "?"]:
                        has_valid_go = True
            except:
                pass

        if has_travel_keyword or has_valid_go:
            return "TRAVEL"

        # 2. 如果關鍵字看不出來，才問 LLM (兜底)
        prompt = (
            f"Classify the user intent into one category.\n"
            f"Options: TRAVEL, WEATHER, MEMORY_SAVE, MEMORY_QUERY, TRASH\n"
            f"Rules:\n"
            f"- '我想去玩', '規劃行程', '去台南' -> TRAVEL\n"
            f"- '今天天氣', '台南下雨嗎' -> WEATHER\n"
            f"- '幫我寫下來', '筆記:明天開會', '我喜歡吃蘋果' -> MEMORY_SAVE\n"
            f"- '我剛剛說了什麼?', '我喜歡吃什麼?', '幫我回想' -> MEMORY_QUERY\n"
            f"- '你好', '講笑話' -> TRASH\n"
            f"Output ONLY the category name.\n\n"
            f"User: '{msg}'\nResult:"
        )
        res = Tools._call_block(prompt).strip()

        valid_intents = ["TRAVEL", "WEATHER", "MEMORY_SAVE", "MEMORY_QUERY", "TRASH"]
        for intent in valid_intents:
            if intent in res:
                return intent

        return "TRASH"

    @staticmethod
    def try_local_parse(msg: str) -> dict:
        """
        ⚡ 光速解析 - 嚴格版
        """
        result = {}
        msg_clean = msg.replace(" ", "")

        today = datetime.datetime.now()
        if "明天" in msg_clean:
            result["date"] = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        elif "後天" in msg_clean:
            result["date"] = (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        elif "今天" in msg_clean:
            result["date"] = today.strftime("%Y-%m-%d")

        # 2. 解析天數 (嚴格限制：必須有 '天')
        digit_match = re.search(r"(\d+)\s*天", msg_clean)
        if digit_match:
            try:
                val = int(digit_match.group(1))
                if val < 30:
                    result["duration"] = val
            except:
                pass

        cn_map = {
            "一": 1,
            "二": 2,
            "兩": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        for k, v in cn_map.items():
            if (k + "天") in msg_clean:
                result["duration"] = v
                break

        return result

    @staticmethod
    def extract_travel_info(msg: str, current_data: dict) -> dict:
        local_res = Tools.try_local_parse(msg)

        if current_data.get("date") and not current_data.get("duration"):
            if "duration" in local_res:
                return local_res

        if current_data.get("dest") and not current_data.get("date"):
            if "date" in local_res:
                return local_res

        prompt = (
            f"Extract 'dest', 'date', 'duration' (int or null) JSON from: '{msg}'\n"
            f"Current Data: {current_data}\n"
            f"Rule: If duration is not explicitly mentioned (like '3 days'), value must be null.\n"
            f"JSON:"
        )
        res = Tools._call_block(prompt)
        try:
            start, end = res.find("{"), res.rfind("}") + 1
            if start != -1:
                llm_res = json.loads(res[start:end])
                if "date" in local_res:
                    llm_res["date"] = local_res["date"]
                if "duration" in local_res:
                    llm_res["duration"] = local_res["duration"]
                return llm_res
        except:
            pass
        return local_res

    @staticmethod
    def extract_weather_info(msg: str) -> dict:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        prompt = (
            f"Extract City and Date from user input.\n"
            f"Current Date: {today}\n"
            f"User Input: '{msg}'\n\n"
            f"Rules:\n"
            f"1. City: Translate to English if possible (e.g. '台南'->'Tainan').\n"
            f"2. Date: Convert to 'YYYY-MM-DD'.\n"
            f"   - '明天' -> Calculate based on Current Date.\n"
            f"   - '今天', '現在', 'Now' -> Return 'today'.\n"
            f"   - If no date is mentioned -> Return 'today'.\n"
            f'3. Output JSON: {{ "city": "...", "date": "..." }}\n'
            f"JSON:"
        )
        res = Tools._call_block(prompt).strip()
        try:
            start = res.find("{")
            end = res.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(res[start:end])
        except:
            pass
        return {"city": None, "date": "today"}

    @staticmethod
    def get_weather(city: str, target_date: str = "today") -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}

            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json"
            geo = requests.get(geo_url, headers=headers, timeout=5).json()
            if "results" not in geo:
                return f"找不到 '{city}'"
            loc = geo["results"][0]
            lat, lng = loc["latitude"], loc["longitude"]

            if target_date != "today":
                try:
                    target_dt = datetime.datetime.strptime(
                        target_date, "%Y-%m-%d"
                    ).date()
                    today_dt = datetime.datetime.now().date()
                    delta_days = (target_dt - today_dt).days

                    if delta_days < 0:
                        return (
                            f"❌ 無法查詢過去的天氣 ({target_date})，時光機尚未發明。"
                        )
                    if delta_days > 14:
                        return f"❌ 預報太遠了 ({target_date})！我只能查詢未來 14 天內的天氣。"
                except ValueError:
                    pass

            if target_date == "today":
                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&"
                    f"current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m&"
                    f"timezone=auto"
                )
                data = requests.get(weather_url, headers=headers, timeout=5).json()
                current = data.get("current", {})

                temp = current.get("temperature_2m", "N/A")
                feel = current.get("apparent_temperature", "N/A")
                humid = current.get("relative_humidity_2m", "N/A")
                code = current.get("weather_code", 0)
                status = Tools._get_weather_status(code)

                return (
                    f"📍 **{loc['name']} 即時天氣**\n"
                    f"☁️ 概況: {status}\n"
                    f"🌡️ 氣溫: {temp}°C (體感 {feel}°C)\n"
                    f"💧 濕度: {humid}%\n"
                )
            else:
                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&"
                    f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
                    f"start_date={target_date}&end_date={target_date}&"
                    f"timezone=auto"
                )
                data = requests.get(weather_url, headers=headers, timeout=5).json()
                if "daily" not in data or not data["daily"]["time"]:
                    return f"❌ 氣象局資料庫沒有 {target_date} 的資料。"

                daily = data["daily"]
                max_temp = daily["temperature_2m_max"][0]
                min_temp = daily["temperature_2m_min"][0]
                rain_prob = daily["precipitation_probability_max"][0]
                code = daily["weather_code"][0]
                status = Tools._get_weather_status(code)

                return (
                    f"🗓️ **{loc['name']} 天氣預報 ({target_date})**\n"
                    f"☁️ 概況: {status}\n"
                    f"🌡️ 氣溫: {min_temp}°C ~ {max_temp}°C\n"
                    f"☔ 降雨機率: {rain_prob}%"
                )

        except Exception as e:
            return f"查詢失敗: {e}"

    @staticmethod
    def _get_weather_status(code: int) -> str:
        if code == 0:
            return "晴朗 ☀️"
        if 1 <= code <= 3:
            return "多雲 ☁️"
        if code in [45, 48]:
            return "有霧 🌫️"
        if 51 <= code <= 67:
            return "下雨 🌧️"
        if 71 <= code <= 77:
            return "下雪 ❄️"
        if 80 <= code <= 82:
            return "陣雨 🌦️"
        if code >= 95:
            return "雷雨 ⛈️"
        return "未知"


# ==========================================
# 🗺️ 旅遊 FSM (維持高效能平行 + 心跳 + 多天數)
# ==========================================
class ZoneTravel(StateMachine):
    idle = State("idle", value="idle", initial=True)
    collecting_dest = State("collecting_dest", value="collecting_dest")
    collecting_date = State("collecting_date", value="collecting_date")
    collecting_duration = State("collecting_duration", value="collecting_duration")
    processing = State("processing", value="processing")

    start_plan = idle.to(collecting_dest)
    got_dest = collecting_dest.to(collecting_date)
    got_date = collecting_date.to(collecting_duration)
    got_duration = collecting_duration.to(processing)
    finish = processing.to(idle)

    def safe_reset(self):
        if self.current_state != self.idle:
            self.current_state = self.idle

    def __init__(self):
        self.trip_data = {"dest": None, "date": None, "duration": None}
        super().__init__()

    def on_enter_collecting_dest(self):
        yield "👋 旅遊模式啟動！請問想去哪裡玩？"

    def on_enter_collecting_date(self):
        dest = self.trip_data["dest"]
        yield f"✅ 目的地：{dest}。請問 **什麼時候** 出發？"

    def on_enter_collecting_duration(self):
        date = self.trip_data["date"]
        yield f"✅ 出發日期：{date}。請問 **要玩幾天**？"

    def on_enter_processing(self):
        dest = self.trip_data["dest"]
        start_date_str = self.trip_data["date"]

        try:
            total_days = int(self.trip_data.get("duration", 1))
            if total_days < 1:
                total_days = 1
        except:
            total_days = 1

        yield f"🚀 正在為您規劃 {dest} 的 {total_days} 天行程 (正在確認每日天氣...)\n"

        def wait_with_heartbeat(future):
            while not future.done():
                time.sleep(0.5)
                yield " ."
            yield "\n"
            try:
                yield future.result()
            except Exception as e:
                yield f"⚠️ 生成失敗: {e}"

        current_date = None
        try:
            current_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        except:
            pass

        for day_i in range(1, total_days + 1):

            day_label = f"第 {day_i} 天"
            target_date_str = start_date_str

            if current_date:
                target_dt = current_date + datetime.timedelta(days=day_i - 1)
                target_date_str = target_dt.strftime("%Y-%m-%d")
                day_label += f" ({target_date_str})"
            elif day_i == 1:
                day_label += f" ({start_date_str})"

            # 🔥 自動天氣查詢
            weather_note = ""
            try:
                w_report = Tools.get_weather(dest, target_date_str)
                if "概況" in w_report:
                    weather_note = f"(注意：當天氣象預報顯示為『{w_report}』，請根據天氣狀況調整行程，例如雨天安排室內活動)"
            except:
                pass

            yield f"\n\n## 🗓️ {day_label} 行程規劃\n"

            p1 = f"請規劃 {dest} {day_label} 的『上午』行程。簡單推薦1-2個景點與特色早餐。請用繁體中文。{weather_note}"
            p2 = f"請規劃 {dest} {day_label} 的『午餐與下午』行程。推薦特色午餐與午後景點。請用繁體中文。{weather_note}"
            p3 = f"請規劃 {dest} {day_label} 的『晚餐與晚上』行程。推薦夜市或夜景。請用繁體中文。{weather_note}"

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                f1 = executor.submit(Tools._call_block, p1)
                f2 = executor.submit(Tools._call_block, p2)
                f3 = executor.submit(Tools._call_block, p3)

                yield f"### 🌅 {day_label} 上午"
                yield from wait_with_heartbeat(f1)

                yield f"\n### ☀️ {day_label} 下午"
                yield from wait_with_heartbeat(f2)

                yield f"\n### 🌙 {day_label} 晚上"
                yield from wait_with_heartbeat(f3)

        yield "\n\n🎉 所有行程規劃完成！祝您旅途愉快！"


# ==========================================
# 🎛️ 核心 (Pipe)
# ==========================================
class Pipe:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.type = "manifold"
        self.id = "toc_agent"
        self.name = "TOC Agent (Triple Key)"

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        try:
            msg = body.get("messages", [])[-1].get("content", "").strip()
            user_id = body.get("user", {}).get("id", "default_user")

            yield "Wait...\n\n"
            yield "🤔 正在讀取訊息...\n"

            fsm = ZoneTravel()
            saved_state_found = False

            if user_id in GLOBAL_USER_STATES:
                saved = GLOBAL_USER_STATES[user_id]
                fsm.trip_data = saved["data"]
                for s in fsm.states:
                    if s.name == saved["state"]:
                        fsm.current_state = s
                        saved_state_found = True
                        break

            is_travel_active = fsm.current_state != fsm.idle

            if is_travel_active:
                intent_type = "TRAVEL"
                yield "⚡ (檢測到對話進行中，加速處理...)\n"
            else:
                intent_type = Tools.analyze_intent_only(msg)

            if is_travel_active or intent_type == "TRAVEL":
                if msg.lower() in ["取消", "退出", "reset"]:
                    fsm.safe_reset()
                    if user_id in GLOBAL_USER_STATES:
                        del GLOBAL_USER_STATES[user_id]
                    yield "🛑 已重置。"
                    return

                if not is_travel_active:
                    fsm.start_plan()

                # 🔥 本地解析狀態顯示
                is_local_success = False
                local_res = Tools.try_local_parse(msg)

                if fsm.current_state == fsm.collecting_date and local_res.get("date"):
                    is_local_success = True
                    yield "⚡ (光速本地解析成功)\n"
                elif fsm.current_state == fsm.collecting_duration and local_res.get(
                    "duration"
                ):
                    is_local_success = True
                    yield "⚡ (光速本地解析成功)\n"

                if not is_local_success:
                    yield "🔍 分析旅遊資訊中...\n"

                extracted = Tools.extract_travel_info(msg, fsm.trip_data)

                if extracted.get("dest"):
                    fsm.trip_data["dest"] = extracted["dest"]
                if extracted.get("date"):
                    fsm.trip_data["date"] = extracted["date"]
                if extracted.get("duration") is not None:
                    fsm.trip_data["duration"] = extracted["duration"]

                if not fsm.trip_data["dest"]:
                    fsm.current_state = fsm.collecting_dest
                    GLOBAL_USER_STATES[user_id] = {
                        "state": "collecting_dest",
                        "data": fsm.trip_data,
                    }
                    yield "👋 旅遊模式：請問想去 **哪裡** 玩？"

                elif not fsm.trip_data["date"]:
                    fsm.current_state = fsm.collecting_date
                    GLOBAL_USER_STATES[user_id] = {
                        "state": "collecting_date",
                        "data": fsm.trip_data,
                    }
                    dest = fsm.trip_data["dest"]
                    yield f"✅ 目的地：**{dest}**。\n請問 **什麼時候** 出發？"

                elif fsm.trip_data["duration"] is None:
                    fsm.current_state = fsm.collecting_duration
                    GLOBAL_USER_STATES[user_id] = {
                        "state": "collecting_duration",
                        "data": fsm.trip_data,
                    }
                    date = fsm.trip_data["date"]
                    yield f"✅ 出發日期：**{date}**。\n請問這次旅行要安排 **幾天**？"

                else:
                    fsm.current_state = fsm.processing
                    yield from fsm.on_enter_processing()
                    fsm.finish()
                    if user_id in GLOBAL_USER_STATES:
                        del GLOBAL_USER_STATES[user_id]
                return

            if intent_type == "WEATHER":
                yield "☁️ 分析天氣需求中...\n"
                info = Tools.extract_weather_info(msg)
                city = info.get("city")
                date = info.get("date")

                if city and city != "None":
                    date_display = "現在" if date == "today" else date
                    yield f"🔍 正在查詢 **{city}** - **{date_display}** 的天氣...\n"
                    report = Tools.get_weather(city, date)
                    yield report
                else:
                    yield "⚠️ 找不到城市名稱，請再試一次 (例如：台北明天的天氣)。"
            elif intent_type == "MEMORY_SAVE":
                yield "💾 寫入中...\n"
                yield from ZoneMemory.handle("SAVE", msg)
            elif intent_type == "MEMORY_QUERY":
                yield "🧠 搜尋中...\n"
                yield from ZoneMemory.handle("QUERY", msg)
            else:
                yield from Tools._call_smart(f"User: {msg}\nReply:")

        except Exception as e:
            yield f"⚠️ Error: {e}"