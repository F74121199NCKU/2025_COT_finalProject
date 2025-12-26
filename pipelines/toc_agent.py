"""
title: TOC Ultimate Agent
author: NCKU Student
description: A FSM-based travel agent
requirements: python-statemachine, requests, pydantic
"""
import os
import requests
import json
import datetime
from typing import List, Union, Generator, Iterator, Optional
from pydantic import BaseModel
from statemachine import StateMachine, State  # type: ignore

# ==========================================
# 🛠️ Tools (工具層 - 保持純淨的靜態方法)
# ==========================================
class Tools:
    API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
    API_KEY = "253b609e99624ea28f7f036e9d4d363b2ad71b853b3fd7b986b12be2b014ff69"
    MODEL_NAME = "gpt-oss:20b"
    MEMORY_PATH = "/app/pipelines/memory.json"

    @staticmethod
    def _call_llm(prompt: str, temperature: float = 0.3, stop: List[str] = None) -> str:
        """ 統一的 LLM 呼叫介面 """
        try:
            headers = {"Authorization": f"Bearer {Tools.API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": temperature,
                "max_tokens": 800, # 增加 token 上限，因為行程表會很長
                "stop": stop if stop else ["Result:", "User:"] # 移除 \n\n 以免回答被截斷
            }
            res = requests.post(Tools.API_URL, headers=headers, json=payload, timeout=120)
            if res.status_code == 200:
                return res.json().get('message', {}).get('content', '').strip()
            return f"Error: API {res.status_code}"
        except Exception as e:
            return f"Exception: {str(e)}"

    @staticmethod
    def analyze_intent(user_msg: str) -> dict:
        """ 意圖分析 (JSON 格式) """
        prompt = (
            f"Classify user intent into JSON format.\n"
            f"Categories: TRAVEL, WEATHER, MEMORY_SAVE, MEMORY_QUERY, CHAT.\n"
            f"Format: {{\"intent\": \"CATEGORY\", \"param\": \"extracted_info_or_null\"}}\n\n"
            f"User: '我想去日本玩'\nJSON: {{\"intent\": \"TRAVEL\", \"param\": \"日本\"}}\n"
            f"User: '記住我的電話0912'\nJSON: {{\"intent\": \"MEMORY_SAVE\", \"param\": \"電話0912\"}}\n"
            f"User: '{user_msg}'\nJSON:"
        )
        result = Tools._call_llm(prompt, temperature=0.1)
        try:
            start = result.find('{')
            end = result.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(result[start:end])
            return {"intent": "CHAT", "param": None}
        except:
            return {"intent": "CHAT", "param": None}

    @staticmethod
    def get_weather(city: str) -> str:
        """ 天氣查詢 """
        try:
            geo_res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json", timeout=5).json()
            if "results" not in geo_res: return f"找不到城市 '{city}'"
            loc = geo_res["results"][0]
            w_res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}&current_weather=true", timeout=5).json()
            curr = w_res["current_weather"]
            return f"📍 {loc['name']} 現況: {curr['temperature']}°C, 風速 {curr['windspeed']} km/h"
        except Exception as e: return f"查詢失敗: {e}"

    @staticmethod
    def memory_op(action: str, content: str = "") -> str:
        """ 記憶讀寫 """
        memories = []
        if os.path.exists(Tools.MEMORY_PATH):
            try:
                with open(Tools.MEMORY_PATH, 'r', encoding='utf-8') as f: memories = json.load(f)
            except: memories = []
        
        if action == "SAVE":
            memories.append({"time": datetime.datetime.now().strftime("%Y-%m-%d"), "content": content})
            try:
                with open(Tools.MEMORY_PATH, 'w', encoding='utf-8') as f: json.dump(memories, f, ensure_ascii=False)
                return f"✅ 已記錄：{content}"
            except Exception as e: return f"❌ 儲存失敗: {e}"
            
        elif action == "QUERY":
            if not memories: return "記憶庫目前是空的。"
            context = "\n".join([f"- {m['content']}" for m in memories[-10:]])
            return Tools._call_llm(f"Based on memories:\n{context}\nUser asks: {content}\nAnswer (Traditional Chinese):", temperature=0.7)
        return "Unknown Action"

# ==========================================
# 🤖 Agent States (狀態機層)
# ==========================================

class BaseAgent(StateMachine):
    def __init__(self):
        self.context = {} 
        super().__init__()

# ------------------------------------------
# 1️⃣ 天氣 Agent (保持不變)
# ------------------------------------------
class WeatherAgent(BaseAgent):
    idle = State("Idle", initial=True)
    collecting_city = State("Collecting City")
    processing = State("Processing")

    start = idle.to(collecting_city)
    got_city = collecting_city.to(processing)
    finish = processing.to(idle)

    def on_enter_collecting_city(self):
        if self.context.get("param"):
            self.got_city()
            return
        return "🌦️ 您想查詢哪個城市的天氣？"

    def on_enter_processing(self):
        city = self.context.get("param") or self.context.get("last_input")
        result = Tools.get_weather(city)
        self.finish()
        return f"{result}\n(查詢完畢)"

# ------------------------------------------
# 2️⃣ 記憶 Agent (保持不變)
# ------------------------------------------
class MemoryAgent(BaseAgent):
    idle = State("Idle", initial=True)
    identifying_mode = State("Identifying Mode")
    collecting_content = State("Collecting Content")
    processing = State("Processing")

    start = idle.to(identifying_mode)
    set_mode = identifying_mode.to(collecting_content)
    got_content = collecting_content.to(processing)
    finish = processing.to(idle)

    def on_enter_identifying_mode(self):
        intent = self.context.get("intent", "")
        self.context["mode"] = "QUERY" if "QUERY" in intent else "SAVE"
        if self.context.get("param"):
            self.context["content"] = self.context.get("param")
            self.set_mode()
            self.got_content()
            return
        self.set_mode()
        action = "記錄" if self.context["mode"] == "SAVE" else "查詢"
        return f"🧠 好的，請告訴我您想{action}什麼內容？"

    def on_enter_processing(self):
        mode = self.context.get("mode")
        content = self.context.get("content") or self.context.get("last_input")
        result = Tools.memory_op(mode, content)
        self.finish()
        return result

# ------------------------------------------
# 3️⃣ 旅遊 Agent (🔥🔥🔥 大幅升級版)
# ------------------------------------------
class TravelAgent(BaseAgent):
    # 定義更完整的狀態流程
    idle = State("Idle", initial=True)
    collecting_dest = State("Collecting Destination")
    collecting_date = State("Collecting Date")
    collecting_who = State("Collecting Companions") # 新增：跟誰去
    collecting_budget = State("Collecting Budget")  # 新增：預算
    collecting_style = State("Collecting Style")
    processing = State("Processing")

    # 定義轉換路徑
    start = idle.to(collecting_dest)
    got_dest = collecting_dest.to(collecting_date)
    got_date = collecting_date.to(collecting_who)   # date -> who
    got_who = collecting_who.to(collecting_budget)  # who -> budget
    got_budget = collecting_budget.to(collecting_style) # budget -> style
    got_style = collecting_style.to(processing)     # style -> processing
    finish = processing.to(idle)

    def on_enter_collecting_dest(self):
        if self.context.get("param"):
            self.context["dest"] = self.context.get("param")
            self.got_dest()
            return 
        return "✈️ 旅遊模式啟動！請問這趟旅程想去哪裡？"

    def on_enter_collecting_date(self):
        dest = self.context.get("dest") or self.context.get("last_input")
        self.context["dest"] = dest
        # 這裡可以偷查天氣
        weather = Tools.get_weather(dest)
        self.context["weather_info"] = weather
        return f"好的，去 {dest} ({weather})。\n請問預計什麼時候出發？"

    def on_enter_collecting_who(self):
        self.context["date"] = self.context.get("last_input")
        return "了解。請問這次是「誰」要一起去？\n(例如：一個人背包客、情侶約會、帶兩個小孩的家庭、跟一群朋友)"

    def on_enter_collecting_budget(self):
        self.context["who"] = self.context.get("last_input")
        return "收到。請問您的「預算」考量是？\n(例如：無上限豪華團、高CP值為主、窮遊省錢模式)"

    def on_enter_collecting_style(self):
        self.context["budget"] = self.context.get("last_input")
        return "最後確認一下，您偏好的「旅遊風格」是？\n(例如：古蹟巡禮、瘋狂吃美食、戶外大自然、輕鬆漫遊)"

    def on_enter_processing(self):
        # 收集所有資訊
        style = self.context.get("last_input")
        dest = self.context["dest"]
        date = self.context["date"]
        who = self.context["who"]
        budget = self.context["budget"]
        weather = self.context.get("weather_info", "未知")

        # 構建終極 Prompt
        prompt = (
            f"請扮演專業導遊，為我規劃去 {dest} 的一日遊行程。\n"
            f"【旅遊參數】\n"
            f"- 日期：{date}\n"
            f"- 旅伴：{who}\n"
            f"- 預算：{budget}\n"
            f"- 風格：{style}\n"
            f"- 當地天氣參考：{weather}\n\n"
            f"【回答要求】\n"
            f"1. 請用繁體中文回答。\n"
            f"2. 行程表需包含時間節點、景點名稱、推薦活動。\n"
            f"3. 針對每個景點，請附上 Google Maps 搜尋連結 (格式: [景點名](https://www.google.com/maps/search/?api=1&query=景點名))\n"
            f"4. 請根據天氣和旅伴，在最後附上一個「智慧打包清單」(例如有雨要帶傘、有小孩要帶推車)。\n"
            f"5. 如果天氣不佳，請優先安排室內備案。"
        )
        
        yield f"正在為您規劃 {dest} 的行程...\n"
        yield f"考慮因素：{who}、{budget}...\n"
        yield f"正在查詢 {dest} 景點與打包建議...\n"
        
        plan = Tools._call_llm(prompt, temperature=0.7)
        self.finish()
        return f"✅ 行程規劃完成！\n\n{plan}"

# ------------------------------------------
# 4️⃣ 聊天 Agent
# ------------------------------------------
class ChatAgent(BaseAgent):
    idle = State("Idle", initial=True)
    def handle(self, msg):
        return Tools._call_llm(f"User says: {msg}\nReply politely in Traditional Chinese:", temperature=0.7)

# ==========================================
# 🎛️ Pipeline (總指揮官)
# ==========================================
class Pipeline:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.agents = {} 

    def pipe(self, user_message: str, model_id: str, messages: List[dict], body: dict) -> Union[str, Generator, Iterator]:
        chat_id = body.get("chat_id")
        msg = user_message.strip()
        yield "🤖...\r" 

        if chat_id not in self.agents:
            self.agents[chat_id] = {"active_fsm": None, "fsm_type": "CHAT"}
        
        user_state = self.agents[chat_id]
        active_fsm = user_state["active_fsm"]

        # 全域取消
        if msg.lower() in ["取消", "退出", "reset", "cancel"]:
            user_state["active_fsm"] = None
            yield "🛑 已重置狀態。"
            return

        # 狀態機推進邏輯
        if active_fsm and not active_fsm.current_state.is_initial:
            active_fsm.context["last_input"] = msg
            response = "Error"
            
            # 手動推進各個 FSM (這是最穩定的寫法)
            if isinstance(active_fsm, WeatherAgent):
                if active_fsm.current_state == active_fsm.collecting_city:
                    response = active_fsm.on_enter_processing()
                
            elif isinstance(active_fsm, MemoryAgent):
                if active_fsm.current_state == active_fsm.collecting_content:
                    response = active_fsm.on_enter_processing()

            elif isinstance(active_fsm, TravelAgent):
                # 旅遊的五階段推進
                if active_fsm.current_state == active_fsm.collecting_dest:
                    response = active_fsm.on_enter_collecting_date()
                    active_fsm.got_dest() 
                elif active_fsm.current_state == active_fsm.collecting_date:
                    response = active_fsm.on_enter_collecting_who() # Date -> Who
                    active_fsm.got_date()
                elif active_fsm.current_state == active_fsm.collecting_who:
                    response = active_fsm.on_enter_collecting_budget() # Who -> Budget
                    active_fsm.got_who()
                elif active_fsm.current_state == active_fsm.collecting_budget:
                    response = active_fsm.on_enter_collecting_style() # Budget -> Style
                    active_fsm.got_budget()
                elif active_fsm.current_state == active_fsm.collecting_style:
                    gen = active_fsm.on_enter_processing() # Style -> Finish
                    for chunk in gen: yield chunk
                    active_fsm.finish()
                    return

            yield response
            return

        # 意圖分析
        analysis = Tools.analyze_intent(msg)
        intent = analysis.get("intent", "CHAT")
        param = analysis.get("param")
        print(f"🧐 Intent: {intent} | Param: {param}")

        new_fsm = None
        if intent == "WEATHER":
            new_fsm = WeatherAgent()
            user_state["fsm_type"] = "WEATHER"
            new_fsm.context["param"] = param 
            response = new_fsm.on_enter_collecting_city() 
            if new_fsm.current_state == new_fsm.processing:
                 response = new_fsm.on_enter_processing()

        elif "MEMORY" in intent:
            new_fsm = MemoryAgent()
            user_state["fsm_type"] = "MEMORY"
            new_fsm.context["intent"] = intent
            new_fsm.context["param"] = param
            response = new_fsm.on_enter_identifying_mode()
            if new_fsm.current_state == new_fsm.processing:
                response = new_fsm.on_enter_processing()

        elif intent == "TRAVEL":
            new_fsm = TravelAgent()
            user_state["fsm_type"] = "TRAVEL"
            new_fsm.context["param"] = param
            response = new_fsm.on_enter_collecting_dest()
            if new_fsm.current_state == new_fsm.collecting_date:
                response = new_fsm.on_enter_collecting_date()

        else:
            user_state["active_fsm"] = None
            yield ChatAgent().handle(msg)
            return

        user_state["active_fsm"] = new_fsm
        yield response