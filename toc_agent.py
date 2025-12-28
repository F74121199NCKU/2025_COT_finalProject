"""
title: TOC Agent (Triple-Key Ultimate)
author: NCKU Student & Gemini
description: Optimized with 3 API Keys for perfect parallel processing.
requirements: python-statemachine, requests, pydantic
version: 8.1.0 (Triple Key)
"""

import os
import requests
import json
import datetime
import time
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
        "2ef233a5993082e09a4533e76c0e8cb2614388ea27cb35b25de9b4d91891a78e",  # 新增的第三組 Key
    ]
    _index = 0

    @classmethod
    def get_headers(cls):
        # 輪詢邏輯：0 -> 1 -> 2 -> 0 ...
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
            headers = KeyManager.get_headers()  # 自動輪詢 Key
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
                timeout=(5, 60),
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
                Tools.API_URL, headers=headers, json=payload, timeout=60
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
        🔥 第一步：只做分類 (Router) - 整合了您的安全網邏輯
        """
        msg = user_msg.strip()

        # keyword快速判定
        if any(k in msg for k in ["天氣", "氣溫", "預報"]):
            return "WEATHER"
        if any(k in msg for k in ["記住", "紀錄", "記憶"]):
            return "MEMORY_SAVE"
        if any(k in msg for k in ["查詢", "回憶", "搜索"]):
            return "MEMORY_QUERY"

        # LLM分類
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

        # 防呆
        cmd_type = "TRASH"
        valid_intents = ["TRAVEL", "WEATHER", "MEMORY_SAVE", "MEMORY_QUERY", "TRASH"]
        for intent in valid_intents:
            if intent in res:
                cmd_type = intent
                break

        # 安全網
        if cmd_type == "TRASH":
            # 這些詞都可增刪
            travel_keywords = [
                "旅遊",
                "旅行",
                "行程",
                "一日遊",
                "二日遊",
                "好玩",
                "日遊",
            ]
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
            has_valid_go = "去" in msg and not any(bad in msg for bad in exclude_words)

            if has_travel_keyword:
                return "TRAVEL"

            elif has_valid_go:
                # 檢查 "去" 的用法
                try:
                    idx = msg.index("去")
                    # 確保 "去" 不是最後一個字，且後面接的不是符號
                    if idx < len(msg) - 1:
                        suffix = msg[idx + 1 :].strip()
                        if len(suffix) >= 2 and suffix[0] not in [
                            "，",
                            "。",
                            "！",
                            "?",
                        ]:
                            return "TRAVEL"
                except:
                    pass

        return cmd_type

    @staticmethod
    def extract_travel_info(msg: str, current_data: dict) -> dict:
        prompt = (
            f"Extract 'dest' and 'date' JSON from: '{msg}'\n"
            f"Current: {current_data}\nJSON:"
        )
        res = Tools._call_block(prompt)
        try:
            start, end = res.find("{"), res.rfind("}") + 1
            if start != -1:
                return json.loads(res[start:end])
        except:
            pass
        return {}

    @staticmethod
    def extract_weather_info(msg: str) -> dict:
        """
        ☁️ 升級版：天氣資訊提取器
        同時抓取「地點」與「日期 (YYYY-MM-DD)」。
        """
        # 取得今天的日期，讓 AI 有參考座標
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
            f"3. Output JSON: {{ \"city\": \"...\", \"date\": \"...\" }}\n"
            f"JSON:"
        )
        res = Tools._call_block(prompt).strip()
        try:
            start = res.find('{')
            end = res.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(res[start:end])
        except: pass
        return {"city": None, "date": "today"}

    @staticmethod
    def get_weather(city: str, target_date: str = "today") -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}

            # 1. 查座標 (這段沒變)
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json"
            geo = requests.get(geo_url, headers=headers, timeout=5).json()
            if "results" not in geo: return f"找不到 '{city}'"
            loc = geo["results"][0]
            lat, lng = loc["latitude"], loc["longitude"]

            # ==========================================
            # 📅 日期檢查防呆 (新增的部分！)
            # ==========================================
            if target_date != "today":
                try:
                    # 把文字日期 (2026-01-02) 轉成電腦時間物件
                    target_dt = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
                    today_dt = datetime.datetime.now().date()
                    
                    # 計算差距天數
                    delta_days = (target_dt - today_dt).days

                    # 防呆 1: 查過去
                    if delta_days < 0:
                        return f"❌ 無法查詢過去的天氣 ({target_date})，時光機尚未發明。"
                    
                    # 防呆 2: 查太遠 (Open-Meteo 免費版限制約 14-16 天)
                    if delta_days > 14:
                        return f"❌ 預報太遠了 ({target_date})！我只能查詢未來 14 天內的天氣。"
                
                except ValueError:
                    # 如果日期格式怪怪的，就當作沒事繼續試試看
                    pass

            # ==========================================
            # 🌤️ 查詢邏輯 (保持原本架構)
            # ==========================================
            
            # 情況 A: 查現在/今天
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

            # 情況 B: 查特定日期
            else:
                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&"
                    f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
                    f"start_date={target_date}&end_date={target_date}&"
                    f"timezone=auto"
                )
                data = requests.get(weather_url, headers=headers, timeout=5).json()
                
                # 這裡也要防呆：如果 API 沒回傳 daily 資料，代表真的查不到
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
        """小幫手：把數字轉文字"""
        if code == 0: return "晴朗 ☀️"
        if 1 <= code <= 3: return "多雲 ☁️"
        if code in [45, 48]: return "有霧 🌫️"
        if 51 <= code <= 67: return "下雨 🌧️"
        if 71 <= code <= 77: return "下雪 ❄️"
        if 80 <= code <= 82: return "陣雨 🌦️"
        if code >= 95: return "雷雨 ⛈️"
        return "未知"

# ==========================================
# 🗺️ 旅遊 FSM (維持高效能平行 + 心跳)
# ==========================================
class ZoneTravel(StateMachine):
    idle = State("idle", value="idle", initial=True)
    collecting_dest = State("collecting_dest", value="collecting_dest")
    collecting_date = State("collecting_date", value="collecting_date")
    processing = State("processing", value="processing")

    start_plan = idle.to(collecting_dest)
    got_dest = collecting_dest.to(collecting_date)
    got_date = collecting_date.to(processing)
    finish = processing.to(idle)

    def safe_reset(self):
        if self.current_state != self.idle:
            self.current_state = self.idle

    def __init__(self):
        self.trip_data = {"dest": None, "date": None}
        super().__init__()

    def on_enter_collecting_dest(self):
        yield "👋 旅遊模式啟動！請問想去哪裡玩？"

    def on_enter_collecting_date(self):
        dest = self.trip_data["dest"]
        yield f"✅ 目的地：{dest}。請問 **什麼時候** 出發？"

    def on_enter_processing(self):
        dest = self.trip_data["dest"]
        date = self.trip_data["date"]
        yield f"✅ 日期：{date}\n🚀 正在**平行運算**為您規劃 {dest} 的行程...\n"

        p1 = f"請只規劃 {date} 去 {dest} 的『上午』行程。簡單推薦1-2個景點與特色早餐。請用繁體中文。"
        p2 = f"請只規劃 {date} 去 {dest} 的『午餐與下午』行程。推薦特色午餐與午後景點。請用繁體中文。"
        p3 = f"請只規劃 {date} 去 {dest} 的『晚餐與晚上』行程。推薦夜市或夜景。請用繁體中文。"

        def wait_with_heartbeat(future):
            while not future.done():
                time.sleep(0.5)
                yield " ."  # 心跳機制：每 0.5 秒發送訊號防止斷線
            yield "\n"
            yield future.result()

        # 🔥 因為現在有 3 個 Key，剛好對應這裡的 3 個 Workers
        # 每個執行緒都會分配到一個獨立的 Key，效率最大化！
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            f1 = executor.submit(Tools._call_block, p1)
            f2 = executor.submit(Tools._call_block, p2)
            f3 = executor.submit(Tools._call_block, p3)

            yield "\n### 🌅 上午行程\n"
            yield from wait_with_heartbeat(f1)

            yield "\n\n### ☀️ 下午行程\n"
            yield from wait_with_heartbeat(f2)

            yield "\n\n### 🌙 晚上行程\n"
            yield from wait_with_heartbeat(f3)

        yield "\n\n🎉 規劃完成！祝您旅途愉快！"


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

            intent_type = Tools.analyze_intent_only(msg)
            fsm = ZoneTravel()

            if user_id in GLOBAL_USER_STATES:
                saved = GLOBAL_USER_STATES[user_id]
                fsm.trip_data = saved["data"]
                for s in fsm.states:
                    if s.name == saved["state"]:
                        fsm.current_state = s
                        break

            is_travel_active = fsm.current_state != fsm.idle
            is_new_travel = intent_type == "TRAVEL"

            if is_travel_active or is_new_travel:
                if msg.lower() in ["取消", "退出", "reset"]:
                    fsm.safe_reset()
                    if user_id in GLOBAL_USER_STATES:
                        del GLOBAL_USER_STATES[user_id]
                    yield "🛑 已重置。"
                    return

                if is_new_travel and not is_travel_active:
                    fsm.start_plan()

                yield "🔍 分析旅遊資訊中...\n"
                extracted = Tools.extract_travel_info(msg, fsm.trip_data)

                if extracted.get("dest"):
                    fsm.trip_data["dest"] = extracted["dest"]
                if extracted.get("date"):
                    fsm.trip_data["date"] = extracted["date"]

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

                else:
                    fsm.current_state = fsm.processing
                    yield from fsm.on_enter_processing()
                    fsm.finish()
                    if user_id in GLOBAL_USER_STATES:
                        del GLOBAL_USER_STATES[user_id]
                return

            # 處理天氣
            if intent_type == "WEATHER":
                yield "☁️ 分析天氣需求中...\n"
                
                # 1. 呼叫新的提取器 (抓地點 + 日期)
                info = Tools.extract_weather_info(msg)
                city = info.get("city")
                date = info.get("date")

                if city and city != "None":
                    # 顯示一點提示訊息，讓使用者知道我們有聽懂日期
                    date_display = "現在" if date == "today" else date
                    yield f"🔍 正在查詢 **{city}** - **{date_display}** 的天氣...\n"
                    
                    # 2. 呼叫新的查詢函式
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