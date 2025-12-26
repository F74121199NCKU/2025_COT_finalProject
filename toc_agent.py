"""
title: TOC Agent (WebUI Pipe)
author: NCKU Student
description: A FSM-based travel agent running directly in WebUI.
requirements: python-statemachine, requests, pydantic
version: 1.0.0
"""

import os
import requests
import json
import datetime
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel

# 系統會自動讀取上方的 requirements 並安裝
from statemachine import StateMachine, State


# ==========================================
# 🧱 基礎建設 (Tools & Memory)
# ==========================================
class MemorySystem:
    # 修改路徑：使用相對路徑，避免 WebUI 容器找不到 /app/pipelines 資料夾
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
            return f"✅ 已寫入日記：{content}"
        except Exception as e:
            return f"❌ 寫入失敗：{e}"

    @staticmethod
    def get_context_string():
        memories = MemorySystem.load_memory()
        if not memories:
            return "目前沒有任何日記或記憶。"
        recent = memories[-15:]
        context = "【使用者的個人記憶資料庫】:\n"
        for mem in recent:
            context += f"- [{mem['timestamp']}] {mem['content']}\n"
        return context


class Tools:
    # 學校 API 設定
    API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
    API_KEY = "253b609e99624ea28f7f036e9d4d363b2ad71b853b3fd7b986b12be2b014ff69"
    MODEL_NAME = "gpt-oss:20b"

    @staticmethod
    def _call_school_api(prompt: str, temperature: float = 0.1) -> str:
        try:
            headers = {
                "Authorization": f"Bearer {Tools.API_KEY}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": temperature,
                "max_tokens": 100,
                "stop": ["\n", "Result:"],
            }

            print(f"📡 [System] 呼叫學校模型中 (Timeout=300s)...")
            # 注意：WebUI 本身也有 Timeout 機制，如果這邊太久可能會被前端斷開
            response = requests.post(
                Tools.API_URL, headers=headers, data=json.dumps(payload), timeout=120
            )

            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    content = resp_json.get("message", {}).get("content", "")
                    return content.strip()
                except:
                    return "Error: JSON 解析失敗"

            return "Error: API 連線失敗"

        except Exception as e:
            return f"Error: {e}"

    # 注意：這行 def 前面要有空格，跟上面的 _call_school_api 對齊
    @staticmethod
    def init_intent_analysis(user_msg: str) -> str:
        msg = user_msg.strip()
        print(f"🤖 [Init] 正在請求 AI 分析意圖: {msg}")

        # 強制要求將城市名稱轉換為英文
        prompt = (
            f"You are a command classifier. Classify the user intent.\n"
            f"Output ONLY the command string code.\n\n"
            f"Rules:\n"
            f"1. Weather -> Output: CMD:WEATHER|<City in English>\n"
            f"   (IMPORTANT: Always translate city name to English. e.g., '台南' -> 'Tainan', '台北' -> 'Taipei')\n\n"
            f"2. Save Memory -> Output: CMD:MEMORY_SAVE|<Content>\n"
            f"3. Query Memory -> Output: CMD:MEMORY_QUERY|<Question>\n"
            f"4. Travel -> Output: CMD:TRAVEL\n"
            f"5. Chat/Other -> Output: CMD:TRASH\n\n"
            f"User Message: '{msg}'\n"
            f"Result:"
        )

        # 呼叫 API
        result = Tools._call_school_api(prompt, temperature=0.1)

        # --- 後處理 ---
        if "CMD:" in result:
            lines = result.split("\n")
            for line in lines:
                if "CMD:" in line:
                    return line.strip()

        return "CMD:TRASH"

    @staticmethod
    def get_weather(city: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {"name": city, "count": 1, "format": "json"}
            geo_res = requests.get(geo_url, params=params, headers=headers, timeout=5)
            geo_data = geo_res.json()
            if "results" not in geo_data:
                return f"找不到城市 '{city}'。"
            res = geo_data["results"][0]
            lat, lon, name = res["latitude"], res["longitude"], res["name"]
            w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=precipitation_probability_max&timezone=auto"
            w_data = requests.get(w_url, headers=headers, timeout=5).json()
            curr = w_data["current_weather"]
            rain = w_data.get("daily", {}).get("precipitation_probability_max", [0])[0]
            return f"📍 {name} 天氣: 溫度 {curr['temperature']}°C, 風速 {curr['windspeed']} km/h, 降雨機率 {rain}%"
        except Exception as e:
            return f"Weather Error: {e}"

    @staticmethod
    def chat_with_school(msg):
        context = MemorySystem.get_context_string()
        prompt = f"{context}\n\n使用者說：{msg}\n請回答："
        return Tools._call_school_api(prompt, temperature=0.7)


# ==========================================
# 🏞️ 區域實作 (Zones)
# ==========================================


class ZoneMemory:
    @staticmethod
    def handle(action: str, content: str):
        if action == "SAVE":
            return MemorySystem.save_memory(content)
        elif action == "QUERY":
            context = MemorySystem.get_context_string()
            prompt = f"根據記憶回答：{content}\n記憶庫：{context}"
            return Tools._call_school_api(prompt)
        return "記憶區發生錯誤"


class ZoneWeather:
    @staticmethod
    def handle(param: str):
        return Tools.get_weather(param)


class ZoneTrash:
    @staticmethod
    def handle(msg: str):
        return Tools.chat_with_school(msg)


class ZoneTravel(StateMachine):
    idle = State("Idle", initial=True)
    collecting_dest = State("Collecting Destination")
    collecting_date = State("Collecting Date")
    processing = State("Processing")

    start_plan = idle.to(collecting_dest)
    got_dest = collecting_dest.to(collecting_date)
    got_date = collecting_date.to(processing)
    finish = processing.to(idle)
    reset = collecting_dest.to(idle) | collecting_date.to(idle) | processing.to(idle)

    def __init__(self):
        self.trip_data = {"dest": None, "date": None}
        super().__init__()

    def on_enter_collecting_dest(self):
        return "👋 您好！我是您的 AI 旅遊助理。請問這趟旅程想去哪裡？(FSM 啟動)"

    def on_enter_collecting_date(self):
        dest = self.trip_data["dest"]
        weather_hint = Tools.get_weather(dest)
        return f"好的，目的地是 {dest}。\n(系統資訊: {weather_hint})\n\n請問您預計什麼時候出發？"

    def on_enter_processing(self):
        dest = self.trip_data["dest"]
        date = self.trip_data["date"]
        prompt = f"請為我去 {dest} 旅行規劃一日遊行程，日期是 {date}。請提供詳細景點與美食建議，並用繁體中文回答。"
        plan = Tools.chat_with_school(prompt)
        return f"✅ 行程規劃完成！\n\n{plan}"


# ==========================================
# 🎛️ 核心 (WebUI Pipe)
# ==========================================
# 🔥 關鍵修改：類別名稱改為 Pipe，這樣 WebUI 才會把它當作模型
class Pipe:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.type = "manifold"  # 告訴 WebUI 這是一個 Manifold 模型
        self.id = "toc_agent"
        self.name = "TOC Agent"  # 這會顯示在模型列表選單中
        self.user_machines = {}

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        try:
            # WebUI Functions 傳進來的格式是 body dict，訊息在 body['messages']
            user_message = body.get("messages", [])[-1].get("content", "").strip()

            # 這裡我們手動 yield 思考狀態
            yield "Wait..."
            yield "\r"

            # 每個使用者 (或對話) 的獨立 ID
            chat_id = (
                "default_user"  # 在 Functions 模式下暫時用單一 ID，若要區分可用 user_id
            )

            if chat_id not in self.user_machines:
                self.user_machines[chat_id] = ZoneTravel()

            fsm = self.user_machines[chat_id]
            msg = user_message

            # =================================================
            # 🔄 旅遊子循環
            # =================================================
            if fsm.current_state != fsm.idle:
                if msg.lower() in ["取消", "退出", "算了", "不玩了"]:
                    fsm.reset()
                    yield "🛑 [選擇器]：已將您從旅遊區拉回，重置完成。"
                    return

                if fsm.current_state == fsm.collecting_dest:
                    fsm.trip_data["dest"] = msg
                    fsm.got_dest()
                    yield fsm.on_enter_collecting_date()
                elif fsm.current_state == fsm.collecting_date:
                    fsm.trip_data["date"] = msg
                    fsm.got_date()
                    yield f"✅ [旅遊區]：收到日期，正在生成計畫...\n\n"
                    yield fsm.on_enter_processing()
                    fsm.finish()
                return

            # =================================================
            # 🏁 Init 階段
            # =================================================
            yield "🤔 [Init]：正在分析意圖...\n"
            intent_raw = Tools.init_intent_analysis(msg)
            print(f"Init Output: {intent_raw}")

            # =================================================
            # 🔀 選擇器階段
            # =================================================

            cmd_type = "TRASH"
            param = msg

            if intent_raw.startswith("CMD:"):
                parts = intent_raw.replace("CMD:", "").split("|")
                cmd_type = parts[0].strip()
                if len(parts) > 1:
                    param = parts[1].strip()

            if cmd_type == "TRAVEL":
                yield "✈️ [選擇器]：切換至 [旅遊區]\n"
                fsm.start_plan()
                yield fsm.on_enter_collecting_dest()

            elif cmd_type == "MEMORY_SAVE":
                yield "💾 [選擇器]：切換至 [記憶區]\n"
                yield ZoneMemory.handle("SAVE", param)

            elif cmd_type == "MEMORY_QUERY":
                yield "🧠 [選擇器]：切換至 [記憶區]\n"
                yield ZoneMemory.handle("QUERY", param)

            elif cmd_type == "WEATHER":
                yield f"🌦️ [選擇器]：切換至 [天氣區]\n"
                yield ZoneWeather.handle(param)

            else:
                yield "💬 [選擇器]：無法識別特定指令，切換至 [垃圾區(聊天)]\n"
                yield ZoneTrash.handle(msg)

        except Exception as e:
            yield f"⚠️ 系統錯誤: {e}"