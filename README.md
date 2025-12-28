# 🛠️ 專案環境設置指南 (Environment Setup)

本文件說明如何部署 Open WebUI、設定 ngrok 外部連線，以及管理 Docker Pipelines。

## 1. 部署 Open WebUI

使用 Docker 下載並啟動 Open WebUI 服務。

### 步驟 1：下載 Docker Image

從 GitHub Container Registry 下載最新版本的映像檔。

```
docker pull ghcr.io/open-webui/open-webui:main
```

### 步驟 2：啟動容器

啟動並連結伺服器（Container 名稱設定為 `COT_AI`）。

```
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name COT_AI ghcr.io/open-webui/open-webui:main
```

>  參數說明
> 
> - `-d`: 在背景執行 (Detached mode)。
>     
> - `-p 3000:8080`: 將本機的 3000 port 對應到容器的 8080 port。
>     
> - `-v`: 掛載 Volume 以保存資料。
>     
> - `--name`: 自訂容器名稱（此處為 `COT_AI`，可自行修改）。
>     

---

## 2. 設定外部連線 (ngrok)

使用 ngrok 將本機服務暴露至外部網路，以便進行測試或展示。

### 步驟 1：設定 Authtoken

請將 `(YOUR ID)` 替換為您的 ngrok 驗證碼。

```
ngrok config add-authtoken (YOUR ID)
```

### 步驟 2：啟動通道

將 port 3000 開放至外部。

```
ngrok http 3000
```

### 步驟 3：取得網址

執行後，複製終端機顯示的 `Forwarding` 網址（例如 `https://xxxx.ngrok-free.app`），即可在瀏覽器開啟。

---

# TOC_FinalProject_TravelAssistant✈️
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Backend](https://img.shields.io/badge/NCKU-API_Gateway-green)

旅遊小幫手，你規劃行程的最佳選擇<br>
本專案是一個基於**OpenWebUI Pipe** 架構開發的AI Agent，整合了 **NCKU LLM API**、**氣象服務** 與 **旅遊行程規劃**。

## 三大功能：
  - 🌥️ 天氣查詢<br>
  - 🧠 記憶系統<br>
  - 🗺️ 旅遊規劃<br>

## 📂 檔案結構
```
.
├── toc_agent.py          # 主程式 (包含 Pipe, FSM, Tools, KeyManager)
├── toc_memory.json       # (自動生成) 儲存使用者記憶的 JSON 檔案
├── docker-compose.yaml   # 設置docker環境和連線
└── requirements.txt      # 專案依賴套件列表
```

## 功能特色
  - 🔑 三組API Key輪詢<br>
    - 自動在 3 組 API Key 之間切換，大幅降低 ```Too Many Requests``` 的風險
    - 在生成多天數行程時，利用 ```concurrent.futures``` 結合多 Key 進行平行加速，避免等很久的情況
  - 🗺️ 旅遊規劃狀態機
    - 使用 python-statemachine 管理對話狀態
    - 關鍵字快篩 與 LLM 意圖判斷，能精準識別使用者想法。
    - 行程規劃時，會自動呼叫 Open-Meteo API 查詢當地氣象，並在行程中標註雨天備案
  - 🧠 本地記憶庫
    - ```SAVE``` 識別「幫我記住...」指令，將資訊存入 ```toc_memory.json```
    - ```QUERY``` 識別「我上次說了什麼...」指令，從記憶庫檢索相關內容並回答

## 📖 使用範例
  - **查詢天氣**<br>
    使用者輸入：
      ```台北明天的天氣```<br>
    Agent 回應：
      ```🗓️ Taipei 天氣預報 (2025-12-30) ☁️ 概況: 多雲 ☁️ 🌡️ 氣溫: 18.5°C ~ 22.1°C ☔ 降雨機率: 20%```
    
  - **記憶功能**<br>
    使用者輸入：
      ```幫我記住我不吃香菜```<br>
    Agent 回應：
      ```💾 寫入中... ✅ 已記錄：幫我記住我不吃香菜```

  - **旅遊規劃**<br>
    使用者輸入：
      ```我想出去玩```<br>
    Agent 回應：
      ```👋 旅遊模式啟動！請問想去 哪裡 玩？```<br>
    使用者輸入：
      ```台南```<br>
    Agent 回應：
      ```👋 ✅ 目的地：台南。```
      ```請問 **什麼時候** 出發？```<br>
    使用者輸入：
      ```明天```<br>
    Agent 回應：
      ```✅ 出發日期：2025-01-01。```
       ```請問這次旅行要安排 **幾天**。```<br>
    使用者輸入：
      ```三天兩夜```<br>
    Agent 回應：
      ```🚀 正在為您規劃 日本京都 的 3 天行程 (正在確認每日天氣...)```<br>
    
    

# **流程圖**
```mermaid 
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'primaryColor': '#2d2d2d',
      'primaryTextColor': '#fff',
      'primaryBorderColor': '#fff',
      'lineColor': '#38bdf8',
      'secondaryColor': '#006100',
      'tertiaryColor': '#fff',
      'clusterBkg': '#111'
    }
  }
}%%

graph TD
    %% ==========================================
    %% 🎨 樣式定義區 (高對比配色)
    %% ==========================================
    classDef start fill:#331133,stroke:#ff79c6,stroke-width:3px,color:#fff;
    classDef logic fill:#0d1117,stroke:#38bdf8,stroke-width:2px,stroke-dasharray: 5 5,color:#fff;
    classDef process fill:#161b22,stroke:#50fa7b,stroke-width:2px,color:#fff;
    classDef fsm fill:#2a1a00,stroke:#ffb86c,stroke-width:2px,color:#fff;
    classDef api fill:#1a0f2e,stroke:#bd93f9,stroke-width:2px,color:#fff;
    classDef optimization fill:#003366,stroke:#00ccff,stroke-width:2px,color:#fff,stroke-dasharray: 2 2;
    classDef decision fill:#660000,stroke:#ff0000,stroke-width:2px,color:#fff;
    classDef trash fill:#333,stroke:#777,stroke-width:1px,color:#ccc;

    %% ==========================================
    %% 1. 頂層輸入與分流 (Top Layer)
    %% ==========================================
    User([使用者輸入]) --> Pipe[Pipe.pipe]:::start
    Pipe --> KeywordCheck{"關鍵字判斷?"}:::optimization
    
    KeywordCheck -- "命中" --> SetIntent[鎖定 Intent]:::process
    KeywordCheck -- "無命中" --> LLM_Classify[LLM 意圖分類]:::api
    
    SetIntent --> Router((核心分流))
    LLM_Classify --> Router

    %% ==========================================
    %% 2. 中層子系統 (Middle Layer - Subgraphs)
    %% 排列技巧：利用連結順序讓 Weather 在左，Travel 在中
    %% ==========================================

    %% --- [左區塊 25%] 天氣系統 ---
    subgraph Weather_System ["☁️ 天氣系統 (25%)"]
        style Weather_System fill:#0f1419,stroke:#50fa7b,stroke-width:2px,color:#fff
        direction TB
        
        ExtractWx[提取需求]:::process
        CheckDate{"日期判斷"}:::logic
        API_Current[即時天氣 API]:::api
        API_Daily["每日預報 API<br>(支援 14 天)"]:::api
        WxReport[回傳天氣報告]:::process

        ExtractWx --> CheckDate
        CheckDate --> API_Current & API_Daily
        API_Current & API_Daily --> WxReport
    end

    %% --- [中區塊 50%] 旅遊系統 (最寬) ---
    subgraph Travel_System ["✈️ 旅遊規劃系統 (50%)"]
        style Travel_System fill:#1a1500,stroke:#ffb86c,stroke-width:2px,color:#fff
        direction TB

        LocalParse["try_local_parse"]:::optimization
        CheckData{資料檢查}:::fsm
        StateCollect["State: collecting..."]:::fsm
        Processing["State: processing"]:::fsm
        
        %% 核心邏輯
        DayLoop{"逐日迴圈"}:::logic
        GetDayWx["查詢該日天氣"]:::api
        CheckRain{"天氣判斷"}:::decision
        InjectStrategy["注入行程策略<br>(室內/室外)"]:::process
        
        %% 平行處理 (撐開寬度的關鍵)
        subgraph Parallel_Block ["平行處理區 (ThreadPool)"]
            direction LR
            style Parallel_Block fill:#000,stroke:#666,stroke-dasharray: 5 5
            PlanMorning[上午行程]:::api
            PlanAfternoon[下午行程]:::api
            PlanNight[晚上行程]:::api
        end
        
        Combine[合併結果]:::process

        %% 流程線
        LocalParse --> CheckData
        CheckData -->|缺資料| StateCollect
        CheckData -->|資料齊全| Processing
        Processing --> DayLoop
        DayLoop --> GetDayWx
        GetDayWx --> CheckRain
        CheckRain --> InjectStrategy
        InjectStrategy --> PlanMorning & PlanAfternoon & PlanNight
        PlanMorning & PlanAfternoon & PlanNight --> Combine
        Combine --> DayLoop
    end

    %% --- [右區塊 15%] 記憶系統 ---
    subgraph Memory_System ["🧠 記憶系統 (15%)"]
        style Memory_System fill:#150f25,stroke:#bd93f9,stroke-width:2px,color:#fff
        direction TB
        MemSave[寫入記憶]:::api
        MemQuery[讀取/RAG]:::api
    end

    %% --- [角落區塊 10%] 閒聊 ---
    subgraph Trash_Bin ["🗑️ 閒聊 (10%)"]
        style Trash_Bin fill:#000,stroke:#555,stroke-width:1px,color:#ccc
        Chat[一般閒聊]:::trash
    end

    %% ==========================================
    %% 3. 路由連接 (Routing Connections)
    %% ==========================================
    Router -->|WEATHER| ExtractWx
    Router -->|TRAVEL| LocalParse
    Router -->|MEMORY| MemSave & MemQuery
    Router -->|TRASH| Chat

    %% 跨系統連線 (Cross-System) - 這裡解決交叉問題
    GetDayWx -.->|請求天氣| ExtractWx
    WxReport -.->|回傳資訊| CheckRain

    %% ==========================================
    %% 4. 輸出與底層資源 (Output & Resources)
    %% ==========================================
    StateCollect & Combine & WxReport & MemSave & MemQuery & Chat --> Response([回傳給使用者]):::start
    
    %% Key Manager 置底
    KeyManager["🔑 KeyManager (三 Key 輪詢)"]:::optimization
    style KeyManager fill:#000,stroke:#fff,stroke-dasharray: 5 5,color:#fff
    
    KeyManager -.-> PlanMorning & PlanAfternoon & PlanNight & LLM_Classify & Chat & MemQuery
