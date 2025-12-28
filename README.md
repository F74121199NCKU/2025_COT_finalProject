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

> [!TIP] 參數說明
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
    %% 🎨 樣式定義區 (高對比配色)
    %% ==========================================
    %% start: 起點 - 亮粉紅邊框 + 白字
    classDef start fill:#331133,stroke:#ff79c6,stroke-width:3px,color:#fff;
    
    %% router: 判斷點 - 亮藍虛線 + 白字
    classDef router fill:#0d1117,stroke:#38bdf8,stroke-width:2px,stroke-dasharray: 5 5,color:#fff;
    
    %% process: 一般處理 - 深灰底 + 亮綠邊框 + 白字
    classDef process fill:#161b22,stroke:#50fa7b,stroke-width:2px,color:#fff;
    
    %% fsm: 狀態機 - 深橘底 + 亮橘邊框 + 白字
    classDef fsm fill:#2a1a00,stroke:#ffb86c,stroke-width:2px,color:#fff;
    
    %% api: 外部呼叫/LLM - 深紫底 + 亮紫邊框 + 白字
    classDef api fill:#1a0f2e,stroke:#bd93f9,stroke-width:2px,color:#fff;

    %% ==========================================
    %% 🔗 流程邏輯區 (完全不用動)
    %% ==========================================
    User([使用者輸入]) --> Pipe[Pipe.pipe]:::start
    Pipe --> Analyze[Tools.analyze_intent_only]:::router
    
    Analyze -->|TRAVEL| CheckState{是否有未完成<br>旅遊狀態?}:::fsm
    Analyze -->|WEATHER| WeatherProc[天氣處理]:::process
    Analyze -->|MEMORY_SAVE| MemSave[ZoneMemory.handle 'SAVE']:::process
    Analyze -->|MEMORY_QUERY| MemQuery[ZoneMemory.handle 'QUERY']:::process
    Analyze -->|TRASH / OTHER| GeneralChat[一般閒聊]:::process

    subgraph Travel_FSM [旅遊狀態機 ZoneTravel]
        direction TB
        style Travel_FSM fill:#161b22,stroke:#ffb86c,stroke-width:2px,color:#fff
        
        CheckState -- No --> StartPlan[FSM: start_plan]
        CheckState -- Yes --> RestoreState[恢復狀態: collecting_dest/date]
        
        StartPlan --> Extract1[提取地點 & 日期]
        RestoreState --> Extract1
        
        Extract1 --> CheckData{資料齊全?}
        CheckData -- No (缺地點) --> StateDest[State: collecting_dest]
        CheckData -- No (缺日期) --> StateDate[State: collecting_date]
        
        StateDest --> AskDest[問: 想去哪?]
        StateDate --> AskDate[問: 何時去?]
        
        CheckData -- Yes --> StateProc[State: processing]
        StateProc --> Parallel[平行處理]
        
        Parallel -->|Thread 1| PlanMorning[規劃上午行程]:::api
        Parallel -->|Thread 2| PlanAfternoon[規劃下午行程]:::api
        Parallel -->|Thread 3| PlanNight[規劃晚上行程]:::api
        
        PlanMorning & PlanAfternoon & PlanNight --> Combine[合併結果]
        Combine --> Finish[FSM: finish / 重置]
    end

    subgraph Weather_System [天氣系統]
        style Weather_System fill:#161b22,stroke:#50fa7b,stroke-width:2px,color:#fff
        WeatherProc --> ExtractWeather[提取城市 & 日期]
        ExtractWeather --> CheckDate{檢查日期}
        CheckDate -- "是今天 (today)" --> API_Current[Open-Meteo Current API]:::api
        CheckDate -- "是未來 (forecast)" --> API_Daily[Open-Meteo Daily API]:::api
        API_Current & API_Daily --> WeatherReport[回傳天氣報告]
    end

    subgraph Memory_System [記憶系統]
        style Memory_System fill:#161b22,stroke:#50fa7b,stroke-width:2px,color:#fff
        MemSave --> SaveFile[(寫入 JSON)]:::api
        MemQuery --> LoadFile[(讀取 JSON)]:::api
        LoadFile --> LLM_RAG[LLM 生成回答]:::api
    end

    GeneralChat --> LLM_Chat[LLM 一般對話]:::api

    AskDest & AskDate & Finish & WeatherReport & SaveFile & LLM_RAG & LLM_Chat --> Response([回傳給使用者])
    style Response fill:#331133,stroke:#ff79c6,stroke-width:3px,color:#fff

    KeyManager[KeyManager: 三 Key 輪詢] -.->|提供 Headers| PlanMorning & PlanAfternoon & PlanNight & LLM_Chat & LLM_RAG
    style KeyManager fill:#000,stroke:#fff,stroke-dasharray: 5 5,color:#fff