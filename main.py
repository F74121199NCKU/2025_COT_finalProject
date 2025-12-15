import requests         #type: ignore
import json
import datetime
import random
import math

# === 1. 設定 API ===
api_url = "https://api-gateway.netdb.csie.ncku.edu.tw/api/chat"
api_key = "ea00b6195cbab7342f1e99824c0d4808c087438d0061fb07b8ab39186b1db778"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# === 2. 定義 6 大工具函式 ===

# [工具 1] 查天氣
def get_weather(city):
    try:
        print(f"   [系統] 正在查詢 {city} 的天氣...")
        # 使用 wttr.in 的格式，只抓取天氣狀況
        url = f"https://wttr.in/{city}?format=%C+%t"
        response = requests.get(url)
        return response.text.strip()
    except Exception as e:
        return f"天氣查詢失敗: {e}"

# [工具 2] 查虛擬貨幣
def get_crypto_price(coin_name):
    try:
        coin_id = coin_name.lower()
        print(f"   [系統] 正在查詢 {coin_id} 的價格...")
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = response.json()
        if coin_id in data:
            return f"{coin_name} 目前價格: {data[coin_id]['usd']} USD"
        return f"找不到 {coin_name}，請確認拼字"
    except:
        return "價格查詢失敗"

# [工具 3] 維基百科摘要 (New!)
# [工具 3] 維基百科摘要 (增強版)
def get_wikipedia_summary(keyword):
    try:
        print(f"   [系統] 正在搜尋維基百科: {keyword}...")
        
        # 1. 先用搜尋 API 找最接近的標題 (解決精準匹配問題)
        search_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={keyword}&format=json"
        search_res = requests.get(search_url).json()
        
        if "query" in search_res and "search" in search_res["query"]:
            results = search_res["query"]["search"]
            if len(results) > 0:
                # 取得第一個搜尋結果的標題
                best_title = results[0]["title"]
                print(f"   [系統] 找到最接近標題: {best_title}")
                
                # 2. 再用這個標題去抓摘要
                summary_url = f"https://zh.wikipedia.org/api/rest_v1/page/summary/{best_title}"
                summary_res = requests.get(summary_url)
                
                if summary_res.status_code == 200:
                    data = summary_res.json()
                    return f"維基百科 ({best_title}): {data.get('extract', '無摘要')}"
        
        return "維基百科搜尋不到相關結果"
        
    except Exception as e:
        return f"維基百科錯誤: {e}"

# [工具 4] 數學計算機 (New!)
def calculate_expression(expression):
    try:
        print(f"   [系統] 正在計算: {expression}")
        # 注意: eval 在正式產品中很危險，但在作業/本機端很方便
        # 它可以算 12*5, 3^2, sqrt(100) 等等
        allowed_names = {"math": math, "abs": abs, "round": round}
        result = eval(expression, {"_builtins_": None}, allowed_names)
        return f"計算結果: {result}"
    except Exception as e:
        return f"計算錯誤: {e}"

# [工具 5] 查詢現在時間 (New!)
def get_current_time():
    now = datetime.datetime.now()
    time_str = now.strftime("%Y年%m月%d日 %H:%M:%S")
    print(f"   [系統] 取得系統時間: {time_str}")
    return f"現在時間是: {time_str}"

# [工具 6] 擲骰子 (New!)
def roll_dice():
    result = random.randint(1, 6)
    print(f"   [系統] 擲出了: {result}")
    return f"骰子結果: {result} 點"

# === 3. 設定工具清單 (Schema) ===
# 這裡定義讓 AI 看的「說明書」
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查詢某個城市的即時天氣",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市英文名稱"}},
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "查詢加密貨幣的即時美金價格",
            "parameters": {
                "type": "object",
                "properties": {"coin_name": {"type": "string", "description": "貨幣英文名稱"}},
                "required": ["coin_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_wikipedia_summary",
            "description": "查詢維基百科上的知識、名詞定義或名人簡介",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "搜尋關鍵字"}},
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_expression",
            "description": "執行數學運算，例如加減乘除",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "數學算式, 如 23*45"}},
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "查詢現在的日期與時間",
            "parameters": {"type": "object", "properties": {}} # 無參數
        }
    },
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "擲一顆六面骰子，產生隨機數",
            "parameters": {"type": "object", "properties": {}} # 無參數
        }
    }
]

# === 4. 主程式 (互動迴圈) ===
def start_chat_loop():
    print("=== 全能 AI 助理已啟動 ===")
    print("你可以問：")
    print("1. 天氣 (台南天氣)")
    print("2. 幣價 (比特幣多少錢)")
    print("3. 知識 (誰是愛因斯坦)")
    print("4. 數學 (算 123 乘以 45)")
    print("5. 時間 (現在幾點)")
    print("6. 遊戲 (幫我擲骰子)")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n你: ").strip()
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("AI: 掰掰！")
                break
            if not user_input: continue

            # --- 呼叫 AI ---
            payload = {
                "model": "gpt-oss:20b", 
                "messages": [{"role": "user", "content": user_input}],
                "tools": tools_schema,
                "stream": False
            }

            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            if response.status_code != 200:
                print(f"API Error: {response.text}")
                continue

            result = response.json()
            message = result.get('message', {})

            # --- 判斷工具呼叫 ---
            if 'tool_calls' in message:
                print("AI: (準備使用工具...)")
                tool_calls = message['tool_calls']
                tools_outputs = []
                
                for tool in tool_calls:
                    func_name = tool['function']['name']
                    
                    # 參數解析
                    raw_args = tool['function']['arguments']
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    
                    # === 超級路由器：分配工作 ===
                    output = ""
                    if func_name == "get_weather":
                        output = get_weather(args.get('city'))
                    elif func_name == "get_crypto_price":
                        output = get_crypto_price(args.get('coin_name'))
                    elif func_name == "get_wikipedia_summary":
                        output = get_wikipedia_summary(args.get('keyword'))
                    elif func_name == "calculate_expression":
                        output = calculate_expression(args.get('expression'))
                    elif func_name == "get_current_time":
                        output = get_current_time()
                    elif func_name == "roll_dice":
                        output = roll_dice()
                    
                    # 儲存結果
                    print(f"   -> 工具回傳: {output}")
                    tools_outputs.append({"role": "tool", "content": output})

                # 回傳給 AI 整理
                final_payload = {
                    "model": "gpt-oss:20b",
                    "messages": [
                        {"role": "user", "content": user_input},
                        message,
                        *tools_outputs
                    ],
                    "stream": False
                }
                
                final_res = requests.post(api_url, headers=headers, data=json.dumps(final_payload))
                final_ans = final_res.json()['message']['content']
                print(f"AI: {final_ans}")

            else:
                # 純聊天
                print(f"AI: {message.get('content')}")

        except Exception as e:
            print(f"發生錯誤: {e}")

if __name__ == "__main__":
    start_chat_loop()