import os
import requests
import json
import re
import datetime
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from statemachine import StateMachine, State
from bs4 import BeautifulSoup

# ==========================================
# PART 1: 記憶模組 (RAG - Personal Diary)
# ==========================================
class MemorySystem:
    # 記憶檔案存放路徑 (Docker 容器內)
    FILE_PATH = "/app/pipelines/memory.json"

    @staticmethod
    def load_memory():
        """ 讀取記憶資料庫 """
        if not os.path.exists(MemorySystem.FILE_PATH):
            return []
        try:
            with open(MemorySystem.FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    @staticmethod
    def save_memory(content: str):
        """ 寫入新記憶 """
        memories = MemorySystem.load_memory()
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content
        }
        memories.append(entry)
        
        # 寫回檔案
        try:
            with open(MemorySystem.FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)
            return f"✅ 已寫入日記/記憶：{content}"
        except Exception as e:
            return f"❌ 寫入失敗：{e}"

    @staticmethod
    def get_context_string():
        """ 將記憶串接成文本，作為 RAG 的背景知識 """
        memories = MemorySystem.load_memory()
        if not memories:
            return "目前沒有任何日記或記憶。"
        
        # 只取最近 15 筆，避免 Token 過多
        recent_memories = memories[-15:]
        context = "【使用者的個人記憶資料庫】:\n"
        for mem in recent_memories:
            context += f"- [{mem['timestamp']}] {mem['content']}\n"
        return context

# ==========================================
# PART 2: 工具庫 (Web UI Tools + New Tools)
# ==========================================
class Tools:
    # --- 學校 API 設定 ---
    API_URL = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
    API_KEY = "253b609e99624ea28f7f036e9d4d363b2ad71b853b3fd7b986b12be2b014ff69"
    MODEL_NAME = "gpt-oss:20b"

    @staticmethod
    def _call_school_api(prompt: str, temperature: float = 0.7) -> str:
        """ 呼叫學校 API 的通用函式 """
        try:
            headers = {"Authorization": f"Bearer {Tools.API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": Tools.MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": temperature
            }
            response = requests.post(Tools.API_URL, headers=headers, data=json.dumps(payload), timeout=60)
            if response.status_code == 200:
                return response.json().get('message', {}).get('content', '').strip()
            return "Error: API 連線失敗"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def analyze_intent(user_msg: str) -> str:
        """ 🔥 超級大腦：意圖識別路由器 (Router) 🔥 """
        prompt = (
            f"You are a smart command classifier. Analyze this user message: '{user_msg}'\n"
            f"Classify it into one of these categories and output ONLY the command string:\n\n"
            f"1. SAVE MEMORY: output 'CMD:REMEMBER|<Content>'\n"
            f"   (e.g., '記住我喜歡吃壽司', '寫日記:今天去跑步' -> CMD:REMEMBER|我喜歡吃壽司)\n"
            f"2. RECALL MEMORY: output 'CMD:RECALL|<Question>'\n"
            f"   (e.g., '我喜歡吃什麼?', '我什麼時候去跑步?', '日記有寫到丹丹嗎' -> CMD:RECALL|我喜歡吃什麼)\n"
            f"3. SUMMARIZE URL: output 'CMD:SUMMARIZE|<URL>'\n"
            f"   (e.g., '幫我總結這個網頁 https://example.com' -> CMD:SUMMARIZE|https://example.com)\n"
            f"4. WEATHER: output 'CMD:WEATHER|<CityNameInEnglish>'\n"
            f"   (e.g., '台南天氣' -> CMD:WEATHER|Tainan)\n"
            f"5. MLB: output 'CMD:MLB|<PlayerNameInEnglish>'\n"
            f"   (e.g., '大谷翔平數據' -> CMD:MLB|Shohei Ohtani)\n"
            f"6. CRYPTO: output 'CMD:CRYPTO|<CoinNameInEnglish>'\n"
            f"   (e.g., '比特幣價格' -> CMD:CRYPTO|bitcoin)\n"
            f"7. TRAVEL: output 'CMD:TRAVEL'\n"
            f"   (e.g., '我想去旅行', '規劃行程')\n"
            f"8. CHAT: output 'CMD:CHAT'\n"
            f"   (e.g., '你好', '你是誰', '講個笑話')\n\n"
            f"Result:"
        )
        return Tools._call_school_api(prompt, temperature=0.1)

    # --- 新增功能：RAG 問答 ---
    @staticmethod
    def query_memory_rag(question: str) -> str:
        context = MemorySystem.get_context_string()
        prompt = (
            f"你是個人的日記助理。請根據以下【記憶資料庫】回答使用者的問題。\n"
            f"如果資料庫裡沒有答案，請老實說「日記裡沒有紀錄」。\n\n"
            f"{context}\n\n"
            f"使用者問題：{question}\n"
            f"回答："
        )
        return Tools._call_school_api(prompt, temperature=0.5)

    # --- 新增功能：網頁總結 (Study Helper) ---
    @staticmethod
    def summarize_url(url: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 移除不必要的標籤
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
            text = soup.get_text()
            
            # 整理文字格式
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # 截取前 2500 字避免 API 錯誤
            clean_text = clean_text[:2500] 
            
            prompt = f"請閱讀以下網頁內容，並用繁體中文列出 3-5 個重點摘要：\n\n{clean_text}"
            return Tools._call_school_api(prompt)
        except Exception as e:
            return f"❌ 無法讀取網頁：{e}"

    # --- 原有 WebUI 工具 (完整保留) ---
    @staticmethod
    def get_weather(city: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {"name": city, "count": 1, "format": "json"}
            geo_res = requests.get(geo_url, params=params, headers=headers, timeout=5)
            geo_data = geo_res.json()
            if "results" not in geo_data: return f"找不到城市 '{city}'。"
            res = geo_data["results"][0]
            lat, lon, name = res["latitude"], res["longitude"], res["name"]
            w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=precipitation_probability_max&timezone=auto"
            w_data = requests.get(w_url, headers=headers, timeout=5).json()
            curr = w_data["current_weather"]
            rain = w_data.get("daily", {}).get("precipitation_probability_max", [0])[0]
            return f"📍 {name} 天氣: 溫度 {curr['temperature']}°C, 風速 {curr['windspeed']} km/h, 降雨機率 {rain}%"
        except Exception as e: return f"Weather Error: {e}"

    @staticmethod
    def get_mlb_stats(player_name: str) -> str:
        try:
            search_url = "https://statsapi.mlb.com/api/v1/people/search"
            params = {"names": player_name, "active": "true"}
            data = requests.get(search_url, params=params, timeout=5).json()
            if "people" not in data or len(data["people"]) == 0: return f"MLB 資料庫找不到 '{player_name}'。"
            pid = data["people"][0]["id"]
            stats_url = f"https://statsapi.mlb.com/api/v1/people/{pid}"
            s_data = requests.get(stats_url, params={"hydrate": "stats(group=[hitting],type=[season])"}, timeout=5).json()
            try:
                stat = s_data["people"][0]["stats"][0]["splits"][-1]["stat"]
                return f"⚾ {player_name} 本季數據: AVG {stat.get('avg', '.---')}, HR {stat.get('homeRuns', 0)}, OPS {stat.get('ops', '.---')}"
            except:
                return f"找到 '{player_name}' 但沒有打擊數據。"
        except Exception as e: return f"MLB Error: {e}"

    @staticmethod
    def get_crypto_price(coin: str) -> str:
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin.lower()}&vs_currencies=usd&include_24hr_change=true"
            data = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()
            if coin.lower() in data:
                return f"💰 {coin}: ${data[coin.lower()]['usd']:,} USD (24h: {data[coin.lower()].get('usd_24h_change', 0):+.2f}%)"
            return f"找不到幣種 '{coin}'。"
        except: return "Crypto Error."

    @staticmethod
    def chat_with_school(user_input: str) -> str:
        return Tools._call_school_api(user_input)

# ==========================================
# PART 3: 有限狀態機 (FSM) - 旅遊代理
# ==========================================
class TravelAgentMachine(StateMachine):
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
        # 使用工具查天氣，提供給使用者參考
        dest = self.trip_data["dest"]
        weather_hint = Tools.get_weather(dest) 
        return f"好的，目的地是 {dest}。\n(系統資訊: {weather_hint})\n\n請問您預計什麼時候出發？"

    def on_enter_processing(self):
        dest = self.trip_data['dest']
        date = self.trip_data['date']
        # 最後一步：讓學校 AI 幫我們寫詳細行程
        prompt = f"請為我去 {dest} 旅行規劃一日遊行程，日期是 {date}。請提供詳細景點與美食建議，並用繁體中文回答。"
        plan = Tools.chat_with_school(prompt)
        return f"✅ 行程規劃完成！\n\n{plan}"

# ==========================================
# PART 4: Pipeline 主程式 (Router 邏輯整合)
# ==========================================
class Pipeline:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.name = "TOC Ultimate Agent"
        self.user_machines = {} 

    async def on_startup(self):
        print(f"on_startup: {self.name}")

    async def on_shutdown(self):
        print(f"on_shutdown: {self.name}")

    def pipe(self, user_message: str, model_id: str, messages: List[dict], body: dict) -> Union[str, Generator, Iterator]:
        try:    
            chat_id = body.get("chat_id")
            
            # 1. 初始化每個使用者的狀態機
            if chat_id not in self.user_machines:
                self.user_machines[chat_id] = TravelAgentMachine()
            
            fsm = self.user_machines[chat_id]
            msg = user_message.strip()
            print(f"User Input: {msg} | State: {fsm.current_state.name}")

            # 2. [優先權 High] 如果 FSM 正在運作中 (非 Idle)，直接讓 FSM 接手
            if fsm.current_state != fsm.idle:
                # 🔥 新增：檢查逃生指令 🔥
                if msg.lower() in ["取消", "退出", "exit", "cancel", "不玩了", "重來", "算了"]:
                    fsm.reset() # 觸發狀態機的 reset 事件
                    return "🛑 已取消旅遊規劃，回到一般模式。有需要隨時叫我！"
                if fsm.current_state == fsm.collecting_dest:
                    fsm.trip_data["dest"] = msg
                    fsm.got_dest()
                    return fsm.on_enter_collecting_date()
                elif fsm.current_state == fsm.collecting_date:
                    fsm.trip_data["date"] = msg
                    fsm.got_date()
                    result = fsm.on_enter_processing()
                    fsm.finish()
                    return result

            # 3. [優先權 Medium] 如果 FSM 閒置，使用 AI Router 判斷意圖
            intent_result = Tools.analyze_intent(msg)
            print(f"AI Router Decision: {intent_result}")

            # 解析 AI 回傳的指令 "CMD:TYPE|PARAM"
            if intent_result.startswith("CMD:"):
                parts = intent_result.replace("CMD:", "").split("|")
                cmd_type = parts[0].strip()
                param = parts[1].strip() if len(parts) > 1 else ""

                # --- 新增功能區 ---
                if cmd_type == "REMEMBER":
                    return MemorySystem.save_memory(param)
                
                elif cmd_type == "RECALL":
                    return Tools.query_memory_rag(param)
                
                elif cmd_type == "SUMMARIZE":
                    return Tools.summarize_url(param)

                elif cmd_type == "WEATHER":
                    return Tools.get_weather(param)
                
                elif cmd_type == "MLB":
                    return Tools.get_mlb_stats(param)
                
                elif cmd_type == "CRYPTO":
                    return Tools.get_crypto_price(param)
                
                elif cmd_type == "TRAVEL":
                    fsm.start_plan()
                    return fsm.on_enter_collecting_dest()
                
                elif cmd_type == "CHAT":
                    return Tools.chat_with_school(msg)
            
            # 4. [優先權 Low] 預設行為：當作一般閒聊
            return Tools.chat_with_school(msg)
        except Exception as e:  # <--- 2. 在最下面加上這個 except 區塊
            print(f"Pipeline Error: {e}")
            return f"系统發生錯誤，請稍後再試。(錯誤代碼: {e})"