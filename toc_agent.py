"""
title: TOC Agent (Fail-safe Hybrid)
author: NCKU Student
description: FSM Agent with Hybrid Output (Auto-switch to Block mode if Stream fails).
requirements: python-statemachine, requests, pydantic
version: 4.0.0 (Stable)
"""

import os
import requests
import json
import datetime
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from statemachine import StateMachine, State

# 紀錄當前對話的記憶(通常是旅遊)
GLOBAL_USER_STATES = {}

# 記憶系統 (Memory System)
class MemorySystem:
    # 設定日記本的存檔路徑 (相對路徑，避免 WebUI 找不到)
    FILE_PATH = "./toc_memory.json"

    @staticmethod
    def load_memory():
        """讀取日記"""
        if not os.path.exists(MemorySystem.FILE_PATH): return []
        try:
            with open(MemorySystem.FILE_PATH, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    @staticmethod
    def save_memory(content: str):
        """寫日記"""
        memories = MemorySystem.load_memory()

        # 加上時間
        entry = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "content": content}
        memories.append(entry)
        try:
            with open(MemorySystem.FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
            return f"✅ 已記錄：{content}"
        except Exception as e: return f"❌ 寫入失敗：{e}"

    @staticmethod
    def get_context_string():
        """把最近的日記串成字串，讓 AI 閱讀"""
        memories = MemorySystem.load_memory()
        if not memories: return "目前沒有任何記憶。"
        # 只取最後 15 筆，避免塞爆 AI 的腦容量 (Token)
        recent = memories[-15:]
        context = "【使用者的記憶庫】:\n"
        for mem in recent: context += f"- [{mem['timestamp']}] {mem['content']}\n"
        return context

# ==========================================
# 🧠 記憶區 (Zone Memory)
# ==========================================
class ZoneMemory:
    """ 負責處理記憶的存取邏輯 """
    @staticmethod
    def handle(action: str, content: str):
        
        # 情況 A: 寫日記 (SAVE)
        if action == "SAVE":
            result = MemorySystem.save_memory(content)
            yield result

        # 情況 B: 問問題 (QUERY)
        elif action == "QUERY":
            # 先把日記拿出來
            context = MemorySystem.get_context_string()
            
            # 告訴 AI 如何根據日記回答
            prompt = (
                f"You are a helpful assistant with access to the user's memory.\n"
                f"Answer the question based ONLY on the provided memory context.\n"
                f"If the answer is not in the memory, say '我記得的資料裡沒有提到這件事'.\n\n"
                f"{context}\n\n"
                f"User Question: {content}\n"
                f"Answer:"
            )
            yield from Tools._call_smart(prompt)

# 基礎建設 (Tools)
class Tools:
    API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
    API_KEY = "253b609e99624ea28f7f036e9d4d363b2ad71b853b3fd7b986b12be2b014ff69"
    MODEL_NAME = "gpt-oss:20b"

    @staticmethod
    def _call_stream_generator(
        prompt: str, temperature: float = 0.7       #prompt: 輸入, temperature: 創意程度
    ) -> Generator[str, None, None]:
        """基礎串流產生器"""
        try:
            #連線資訊
            headers = {
                "Authorization": f"Bearer {Tools.API_KEY}",
                "Content-Type": "application/json",
                "Connection": "close",
            }

            #Model回傳的設定
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,                                     #有字產出就立刻回傳
                "temperature": temperature,                         #
                "max_tokens": 1500,
            }

            #送出資訊
            response = requests.post(
                Tools.API_URL,
                headers = headers,          #就是上面的headers
                json = payload,             #也是上面的payload
                stream = True,          
                timeout = (10, 120),          #Timeout 設定：(連線, 讀取) 
            )

            if response.status_code != 200: #200: OK
                return  

            #讀取、解析字串
            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        json_str = decoded.replace("data: ", "")
                        if json_str == "[DONE]":
                            break
                        try:
                            data = json.loads(json_str)
                            content = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            """
                            示意圖
                            {
                                "choices": [
                                    {
                                    "delta": {
                                        "content": "測試"  <--
                                    }
                                    }
                                ]
                            }
                            """
                            if content:
                                yield content
                        except:
                            pass
        except:
            return

    @staticmethod #一次讀取 
    def _call_block(prompt: str, temperature: float = 0.7) -> str:
        try:
            headers = {
                "Authorization": f"Bearer {Tools.API_KEY}",
                "Content-Type": "application/json",
                "Connection": "close",
            }
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": temperature,
            }
            res = requests.post(
                Tools.API_URL, headers = headers, 
                json = payload, timeout = 60
            )
            if res.status_code == 200:
                return res.json().get("message", {}).get("content", "").strip()
            return f"Error: API returned {res.status_code}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    #先後呼叫兩種方法
    def _call_smart(prompt: str) -> Generator[str, None, None]:

        # 1. 先嘗試串流
        stream_gen = Tools._call_stream_generator(prompt)
        has_content = False

        try:
            for chunk in stream_gen:
                has_content = True
                yield chunk
        except:
            pass  # 忽略串流錯誤，準備切換

        # 2. 如果串流沒反應，就切換到穩定模式
        if not has_content:
            yield " (串流連線不穩，轉為穩定模式讀取...)\n\n"
            block_content = Tools._call_block(prompt)
            yield block_content

    @staticmethod
    def analyze_intent_only(user_msg: str) -> str:
        """
        🔥 第一步：只做分類 (Router) - 整合了您的安全網邏輯
        """
        msg = user_msg.strip()
        
        # keyword快速判定
        if any(k in msg for k in ["天氣", "氣溫"]): return "WEATHER"
        if any(k in msg for k in ["記住", "紀錄"]): return "MEMORY_SAVE"
        if any(k in msg for k in ["查詢", "回憶"]): return "MEMORY_QUERY"
        
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
            #這些詞都可增刪
            travel_keywords = ["旅遊", "旅行", "行程", "一日遊", "二日遊", "好玩", "日遊"]
            exclude_words = ["去年", "過去", "失去", "去除", "回去", "下去", "上去", "進去", "出去"]

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
                        suffix = msg[idx+1:].strip()
                        if len(suffix) >= 2 and suffix[0] not in ["，", "。", "！", "?"]:
                            return "TRAVEL"
                except:
                    pass

        return cmd_type

    @staticmethod
    def extract_travel_info(msg: str, current_data: dict) -> dict:
        """
        旅遊專用提取器 (Extractor)
        只在確定是 TRAVEL 時呼叫，專注抓地點和日期。
        """
        prompt = (
            f"You are a Travel Assistant. extract information from User Input.\n"
            f"Current known info: {current_data}\n"
            f"User Input: '{msg}'\n\n"
            f"Task: Extract 'dest' (Destination) and 'date' (Date).\n"
            f"Rules:\n"
            f"1. If user mentions a new destination, update 'dest'.\n"
            f"2. If user mentions a time/date, update 'date'.\n"
            f"3. If info is not mentioned, keep it null.\n"
            f"4. Output format: JSON {{ \"dest\": \"...\", \"date\": \"...\" }}\n"
            f"JSON:"
        )
        res = Tools._call_block(prompt)
        try:
            #抓取JSON部分 並回傳dict
            start = res.find('{')
            end = res.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(res[start:end])
        except: pass
        return {}

    @staticmethod
    def get_weather(city: str) -> str:
        try:
            #爬蟲抓取資訊
            headers = {"User-Agent": "Mozilla/5.0"}
            geo = requests.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json",
                headers = headers,
                timeout = 10,
            ).json()
            if "results" not in geo:
                return f"找不到 '{city}'"
            loc = geo["results"][0]
            w = requests.get(
                f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}&current_weather=true",
                headers = headers,
                timeout = 10,
            ).json()
            return f"📍 {loc['name']}: {w['current_weather']['temperature']}°C"
        except:
            return "天氣查詢失敗"


# 旅遊 FSM
class ZoneTravel(StateMachine):
    #定義狀態
    idle = State("idle", value = "idle", initial = True)
    collecting_dest = State("collecting_dest", value = "collecting_dest")
    collecting_date = State("collecting_date", value = "collecting_date")
    processing = State("processing", value = "processing")

    #狀態轉換
    start_plan = idle.to(collecting_dest)
    got_dest = collecting_dest.to(collecting_date)
    got_date = collecting_date.to(processing)
    finish = processing.to(idle)

    #返回IDLE
    def safe_reset(self):
        if self.current_state != self.idle:
            self.current_state = self.idle

    def __init__(self):
        self.trip_data = {"dest": None, "date": None}
        super().__init__()
    
    #on_enter_狀態名 進入該狀態後會自動執行
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
        yield from Tools._call_smart(
            f"請為我去 {dest} 規劃一日遊，日期 {date}。繁體中文，附景點推薦。"
        )


# 核心 (Pipe)
class Pipe:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.type = "manifold"
        self.id = "toc_agent"
        self.name = "TOC Agent (Smart)"

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        try:
            # 接收訊息
            msg = body.get("messages", [])[-1].get("content", "").strip()
            user_id = body.get("user", {}).get("id", "default_user")

            yield "Wait...\n"

            # 分析指令
            intent_type = Tools.analyze_intent_only(msg)
            
            # 查詢記憶
            fsm = ZoneTravel()
            if user_id in GLOBAL_USER_STATES:
                saved = GLOBAL_USER_STATES[user_id]
                fsm.trip_data = saved["data"]

                # 強制切換回上次的狀態
                for s in fsm.states:
                    if s.name == saved["state"]:
                        fsm.current_state = s
                        break
            
            # 旅遊邏輯 (State-Aware Logic)
            
            # 判斷是否要處理旅遊 (包含新指令 TRAVEL 或 正在旅遊狀態中)
            is_travel_active = (fsm.current_state != fsm.idle)
            is_new_travel = (intent_type == "TRAVEL")

            if is_travel_active or is_new_travel:
                # 處理取消指令
                if msg.lower() in ["取消", "退出", "reset", "結束", "中止"]:
                    fsm.safe_reset()
                    if user_id in GLOBAL_USER_STATES: del GLOBAL_USER_STATES[user_id]
                    yield "🛑 已重置。"
                    return

                # 如果是新任務，重置 FSM 開始
                if is_new_travel and not is_travel_active:
                    fsm.start_plan()
                
                # 呼叫二樓專員 (Extractor) - 專心抓資料
                extracted = Tools.extract_travel_info(msg, fsm.trip_data)
                
                # 更新資料 (如果有抓到的話)
                if extracted.get("dest"): fsm.trip_data["dest"] = extracted["dest"]
                if extracted.get("date"): fsm.trip_data["date"] = extracted["date"]

                # 狀態跳轉邏輯 (資料驅動)
                # 看資料缺什麼就問什麼
                
                # 缺地點
                if not fsm.trip_data["dest"]:
                    fsm.current_state = fsm.collecting_dest # 手動對齊狀態
                    GLOBAL_USER_STATES[user_id] = {"state": "collecting_dest", "data": fsm.trip_data}
                    yield "👋 旅遊模式：請問想去 **哪裡** 玩？"
                
                # 缺日期
                elif not fsm.trip_data["date"]:
                    fsm.current_state = fsm.collecting_date
                    GLOBAL_USER_STATES[user_id] = {"state": "collecting_date", "data": fsm.trip_data}
                    dest = fsm.trip_data["dest"]
                    yield f"✅ 目的地：**{dest}**。\n請問 **什麼時候** 出發？"
                
                # 資料都齊了
                else:
                    fsm.current_state = fsm.processing
                    yield from fsm.on_enter_processing()
                    fsm.finish() # 完成後重置
                    if user_id in GLOBAL_USER_STATES: del GLOBAL_USER_STATES[user_id]
                
                return
            
            # 其他功能 (天氣 / 記憶 / 閒聊)
            if intent_type == "WEATHER":
                yield "☁️ 查詢天氣中...\n"
                yield from Tools._call_smart(f"請幫我查一下這個地方的天氣：{msg}")
            
            # 處理儲存記憶
            elif intent_type == "MEMORY_SAVE":
                yield "💾 正在寫入日記...\n"
                # 呼叫記憶區 (ZoneMemory) 的 handle 函式
                # 這裡直接把整句話 (msg) 存進去
                yield from ZoneMemory.handle("SAVE", msg)

            # 處理查詢記憶
            elif intent_type == "MEMORY_QUERY":
                yield "🧠 正在搜尋記憶庫...\n"
                # 呼叫記憶區幫忙回想
                yield from ZoneMemory.handle("QUERY", msg)
            
            else:
                # TRASH 或其他
                yield from Tools._call_smart(f"User: {msg}\nReply:")

        except Exception as e:
            yield f"⚠️ Error: {e}"