"""
title: TOC Agent (Fail-safe Hybrid)
author: NCKU Student
description: FSM Agent with Hybrid Output (Auto-switch to Block mode if Stream fails).
requirements: python-statemachine, requests, pydantic
version: 4.0.0 (Stable)
"""

import requests
import json
import datetime
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from statemachine import StateMachine, State

# ==========================================
# 🔒 全域記憶體 (Global Memory)
# ==========================================
GLOBAL_USER_STATES = {}

# ==========================================
# 🧱 基礎建設 (Tools)
# ==========================================
class Tools:
    API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
    API_KEY = "253b609e99624ea28f7f036e9d4d363b2ad71b853b3fd7b986b12be2b014ff69"
    MODEL_NAME = "gpt-oss:20b"

    @staticmethod
    def _call_stream_generator(prompt: str, temperature: float = 0.7) -> Generator[str, None, None]:
        """ 基礎串流產生器 """
        try:
            headers = {
                "Authorization": f"Bearer {Tools.API_KEY}",
                "Content-Type": "application/json",
                "Connection": "close"
            }
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "temperature": temperature,
                "max_tokens": 1500,
            }
            # Timeout 設定：連線 5秒，讀取 60秒
            response = requests.post(Tools.API_URL, headers=headers, json=payload, stream=True, timeout=(5, 60))

            if response.status_code != 200:
                return # 失敗直接結束，讓外層切換 fallback

            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        json_str = decoded.replace("data: ", "")
                        if json_str == "[DONE]": break
                        try:
                            data = json.loads(json_str)
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content: yield content
                        except: pass
        except:
            return

    @staticmethod
    def _call_block(prompt: str, temperature: float = 0.7) -> str:
        """ 穩定版一次讀取 (Fallback) """
        try:
            headers = {"Authorization": f"Bearer {Tools.API_KEY}", "Content-Type": "application/json", "Connection": "close"}
            payload = {"model": Tools.MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "stream": False, "temperature": temperature}
            res = requests.post(Tools.API_URL, headers=headers, json=payload, timeout=20)
            if res.status_code == 200: return res.json().get("message", {}).get("content", "").strip()
            return f"Error: API returned {res.status_code}"
        except Exception as e: return f"Error: {e}"

    @staticmethod
    def _call_smart(prompt: str) -> Generator[str, None, None]:
        """ 🔥 雙重保險呼叫法 """
        
        # 1. 先嘗試串流
        stream_gen = Tools._call_stream_generator(prompt)
        has_content = False
        
        try:
            for chunk in stream_gen:
                has_content = True
                yield chunk
        except:
            pass # 忽略串流錯誤，準備切換

        # 2. 如果串流完全沒反應 (連一個字都沒吐出來)，就切換到穩定模式
        if not has_content:
            yield " (⚠️ 串流連線不穩，轉為穩定模式讀取...)\n\n"
            block_content = Tools._call_block(prompt)
            yield block_content

    @staticmethod
    def analyze_intent(user_msg: str) -> dict:
        msg = user_msg.strip()
        
        # 1. 關鍵字快篩
        if any(k in msg for k in ["天氣", "氣溫"]): return {"type": "WEATHER", "p1": msg[:2], "p2": None}
        if any(k in msg for k in ["記住", "紀錄"]): return {"type": "MEMORY_SAVE", "p1": msg, "p2": None}
        if any(k in msg for k in ["查詢", "回憶"]): return {"type": "MEMORY_QUERY", "p1": msg, "p2": None}
        
        # 2. LLM 分析 (使用 Block 模式確保準確)
        prompt = (
            f"Classify intent. Output format: TYPE|Param1|Param2\n"
            f"Rules:\n"
            f"1. TRAVEL: User wants to go somewhere. Format: TRAVEL|Dest|Date\n"
            f"   - '想去台中' -> TRAVEL|Taichung|None\n"
            f"   - '明天去台北' -> TRAVEL|Taipei|Tomorrow\n"
            f"   - '規劃行程' -> TRAVEL|None|None\n"
            f"2. WEATHER: Format: WEATHER|City|None\n"
            f"3. OTHERS: Format: TRASH|None|None\n"
            f"User input: '{msg}'\nResult:"
        )
        res = Tools._call_block(prompt, temperature=0.1)
        
        try:
            parts = res.split("|")
            cmd_type = parts[0].strip()
            p1 = parts[1].strip() if len(parts) > 1 and parts[1].strip() not in ["None", "null"] else None
            p2 = parts[2].strip() if len(parts) > 2 and parts[2].strip() not in ["None", "null"] else None
        except:
            cmd_type = "TRASH"; p1 = None; p2 = None

        if cmd_type == "TRASH" and ("去" in msg or "旅遊" in msg):
            cmd_type = "TRAVEL"
            if "去" in msg and len(msg) > msg.index("去")+1:
                try: p1 = msg.split("去")[1][:2]
                except: pass

        return {"type": cmd_type, "p1": p1, "p2": p2}

    @staticmethod
    def get_weather(city: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json", headers=headers, timeout=5).json()
            if "results" not in geo: return f"找不到 '{city}'"
            loc = geo["results"][0]
            w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}&current_weather=true", headers=headers, timeout=5).json()
            return f"📍 {loc['name']}: {w['current_weather']['temperature']}°C"
        except: return "天氣查詢失敗"

# ==========================================
# 🗺️ 旅遊 FSM
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
        # 🔥 先確認收到指令
        yield f"✅ 日期：{date}\n🚀 正在為您規劃 {dest} 的行程...\n\n"
        
        # 🔥 使用雙重保險呼叫
        yield from Tools._call_smart(f"請為我去 {dest} 規劃一日遊，日期 {date}。繁體中文，附景點推薦。")

# ==========================================
# 🎛️ 核心 (Pipe)
# ==========================================
class Pipe:
    class Valves(BaseModel): pass
    def __init__(self):
        self.type = "manifold"
        self.id = "toc_agent"
        self.name = "TOC Agent"

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        try:
            msg = body.get("messages", [])[-1].get("content", "").strip()
            user_id = body.get("user", {}).get("id", "default_user")

            yield "Wait...\n"

            intent = Tools.analyze_intent(msg)
            cmd_type = intent["type"]
            p1 = intent["p1"] # 地點
            p2 = intent["p2"] # 日期

            # 恢復狀態
            fsm = ZoneTravel()
            if user_id in GLOBAL_USER_STATES:
                saved = GLOBAL_USER_STATES[user_id]
                fsm.trip_data = saved["data"]
                for s in fsm.states:
                    if s.value == saved["state"]:
                        fsm.current_state = s
                        break

            # 判斷新指令
            is_new_command = (cmd_type == "TRAVEL" and p1 is not None)
            if is_new_command:
                fsm.safe_reset() 

            # A. 處理進行中狀態
            if fsm.current_state != fsm.idle and not is_new_command:
                if msg.lower() in ["取消", "退出", "reset"]:
                    fsm.safe_reset()
                    if user_id in GLOBAL_USER_STATES: del GLOBAL_USER_STATES[user_id]
                    yield "🛑 已重置。"
                    return

                if fsm.current_state == fsm.collecting_dest:
                    fsm.trip_data["dest"] = msg
                    fsm.got_dest()
                    GLOBAL_USER_STATES[user_id] = {"state": "collecting_date", "data": fsm.trip_data}
                    yield f"✅ 收到：{msg}\n"
                    yield from fsm.on_enter_collecting_date()
                    return

                elif fsm.current_state == fsm.collecting_date:
                    if "去" in msg and len(msg) < 10: pass 
                    else:
                        fsm.trip_data["date"] = msg
                        fsm.got_date()
                        yield from fsm.on_enter_processing()
                        fsm.finish()
                        if user_id in GLOBAL_USER_STATES: del GLOBAL_USER_STATES[user_id]
                        return

            # B. 處理新指令 / Idle
            if cmd_type == "TRAVEL":
                yield "✈️ 切換至 [旅遊區]\n"
                fsm.start_plan()
                
                if p1 is None:
                    yield from fsm.on_enter_collecting_dest()
                    GLOBAL_USER_STATES[user_id] = {"state": "collecting_dest", "data": fsm.trip_data}
                else:
                    fsm.trip_data["dest"] = p1
                    fsm.got_dest()
                    
                    if p2 is not None:
                        fsm.trip_data["date"] = p2
                        fsm.got_date()
                        yield from fsm.on_enter_processing()
                        fsm.finish()
                        if user_id in GLOBAL_USER_STATES: del GLOBAL_USER_STATES[user_id]
                    else:
                        yield from fsm.on_enter_collecting_date()
                        GLOBAL_USER_STATES[user_id] = {"state": "collecting_date", "data": fsm.trip_data}

            elif cmd_type == "WEATHER":
                yield "☁️ 查詢天氣中...\n"
                if p1: yield Tools.get_weather(p1)
                else: yield "請提供城市名稱"

            else:
                yield from Tools._call_smart(f"User: {msg}\nReply:")

        except Exception as e:
            yield f"⚠️ Error: {e}"