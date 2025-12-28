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
      'tertiaryColor': '#fff'
    }
  }
}%%

graph TD
    %% ==========================================
    %% 🎨 樣式定義區
    %% ==========================================
    classDef start fill:#331133,stroke:#ff79c6,stroke-width:3px,color:#fff;
    classDef logic fill:#0d1117,stroke:#38bdf8,stroke-width:2px,stroke-dasharray: 5 5,color:#fff;
    classDef process fill:#161b22,stroke:#50fa7b,stroke-width:2px,color:#fff;
    classDef fsm fill:#2a1a00,stroke:#ffb86c,stroke-width:2px,color:#fff;
    classDef api fill:#1a0f2e,stroke:#bd93f9,stroke-width:2px,color:#fff;
    classDef optimization fill:#003366,stroke:#00ccff,stroke-width:2px,color:#fff,stroke-dasharray: 2 2;

    %% ==========================================
    %% 🔗 系統主流程
    %% ==========================================
    User([使用者輸入]) --> Pipe[Pipe.pipe]:::start
    
    %% 1. FSM 狀態檢查
    Pipe --> CheckActive{"FSM<br>進行中?"}:::logic
    
    CheckActive -- "Yes (State Found)" --> Restore["恢復狀態 & 設定 Intent=TRAVEL"]:::fsm
    
    %% 2. 意圖判斷
    CheckActive -- No --> KeywordCheck{"關鍵字<br>光速判斷?"}:::optimization
    
    KeywordCheck -- "命中 (天氣/記憶/旅遊)" --> SetIntent[鎖定 Intent]:::process
    KeywordCheck -- 無命中 --> LLM_Classify[LLM 意圖分類]:::api
    
    Restore --> Router((分流))
    SetIntent --> Router
    LLM_Classify --> Router

    %% ==========================================
    %% 🏖️ 旅遊 FSM
    %% ==========================================
    subgraph Travel_System [✈️ 旅遊規劃系統 ZoneTravel]
        direction TB
        style Travel_System fill:#161b22,stroke:#ffb86c,stroke-width:2px,color:#fff
        
        Router -->|TRAVEL| LocalParse["try_local_parse<br>本地極速解析"]:::optimization
        LocalParse --> LLM_Extract[LLM 提取補強]:::api
        
        LLM_Extract --> CheckData{資料檢查}:::fsm
        
        %% 狀態分支
        CheckData -- 缺地點 --> StateDest["State: collecting_dest<br>問: 去哪裡?"]:::fsm
        CheckData -- 缺日期 --> StateDate["State: collecting_date<br>問: 何時去?"]:::fsm
        CheckData -- "缺天數 (New!)" --> StateDuration["State: collecting_duration<br>問: 玩幾天?"]:::fsm
        
        %% 處理中
        CheckData -- 資料齊全 --> Processing["State: processing"]:::fsm
        
        %% 🔥 修正點：加上引號避免括號解析錯誤
        Processing --> Parallel["平行處理 (ThreadPool)"]:::process
        
        Parallel -->|Thread 1| PlanMorning[上午行程]:::api
        Parallel -->|Thread 2| PlanAfternoon[下午行程]:::api
        Parallel -->|Thread 3| PlanNight[晚上行程]:::api
        
        PlanMorning & PlanAfternoon & PlanNight --> Combine[合併 & 生成回應]
    end

    %% ==========================================
    %% ☁️ 天氣系統
    %% ==========================================
    subgraph Weather_System [☁️ 天氣系統]
        style Weather_System fill:#161b22,stroke:#50fa7b,stroke-width:2px,color:#fff
        Router -->|WEATHER| ExtractWx[提取城市 & 日期]:::process
        ExtractWx --> API_Meteo[Open-Meteo API]:::api
        API_Meteo --> WxReport[回傳報告]
    end

    %% ==========================================
    %% 🧠 記憶與其他
    %% ==========================================
    subgraph Memory_System [🧠 記憶系統]
        style Memory_System fill:#161b22,stroke:#bd93f9,stroke-width:2px,color:#fff
        Router -->|MEMORY_SAVE| MemSave[寫入 JSON]:::api
        Router -->|MEMORY_QUERY| MemQuery[讀取 JSON + RAG]:::api
    end

    Router -->|TRASH| Chat[一般閒聊]:::api

    %% ==========================================
    %% 輸出與資源管理
    %% ==========================================
    StateDest & StateDate & StateDuration & Combine & WxReport & MemSave & MemQuery & Chat --> Response([回傳給使用者]):::start
    style Response fill:#331133,stroke:#ff79c6,stroke-width:3px,color:#fff

    %% Key Manager
    KeyManager[KeyManager: 三 Key 輪詢] -.->|Authorization| PlanMorning & PlanAfternoon & PlanNight & LLM_Classify & Chat & MemQuery
    style KeyManager fill:#000,stroke:#fff,stroke-dasharray: 5 5,color:#fff