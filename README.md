docker pull ghcr.io/open-webui/open-webui:main  #下載docker image
#啟動與連結伺服器 --name後名字可自改
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name COT_AI ghcr.io/open-webui/open-webui:main

__開啟localhost__
ngrok config add-authtoken (YOUR ID)
ngrok http 3000
複製 Forwarding後的網址即可

架設docker_pipelines
docker-compose restart pipelines
docker-compose down
docker-compose up -d    (需等待下載時間)
docker-compose down

# **流程圖**
graph TD
    %% 定義樣式
    classDef start fill:#f9f,stroke:#333,stroke-width:2px;
    classDef router fill:#bbf,stroke:#333,stroke-width:2px,stroke-dasharray: 5 5;
    classDef process fill:#dfd,stroke:#333,stroke-width:2px;
    classDef fsm fill:#ffe6cc,stroke:#d79b00,stroke-width:2px;
    classDef api fill:#e1d5e7,stroke:#9673a6,stroke-width:2px;

    User([使用者輸入]) --> Pipe[Pipe.pipe]:::start
    Pipe --> Analyze[Tools.analyze_intent_only]:::router
    
    %% 意圖判斷分支
    Analyze -->|TRAVEL| CheckState{是否有未完成<br>旅遊狀態?}:::fsm
    Analyze -->|WEATHER| WeatherProc[天氣處理]:::process
    Analyze -->|MEMORY_SAVE| MemSave[ZoneMemory.handle 'SAVE']:::process
    Analyze -->|MEMORY_QUERY| MemQuery[ZoneMemory.handle 'QUERY']:::process
    Analyze -->|TRASH / OTHER| GeneralChat[一般閒聊]:::process

    %% 旅遊 FSM 邏輯
    subgraph Travel_FSM [旅遊狀態機 ZoneTravel]
        direction TB
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

    %% 天氣處理邏輯
    subgraph Weather_System [天氣系統]
        WeatherProc --> ExtractWeather[提取城市 & 日期]
        ExtractWeather --> CheckDate{檢查日期}
        CheckDate -- "是今天 (today)" --> API_Current[Open-Meteo Current API]:::api
        CheckDate -- "是未來 (forecast)" --> API_Daily[Open-Meteo Daily API]:::api
        API_Current & API_Daily --> WeatherReport[回傳天氣報告]
    end

    %% 記憶系統邏輯
    subgraph Memory_System [記憶系統]
        MemSave --> SaveFile[(寫入 JSON)]:::api
        MemQuery --> LoadFile[(讀取 JSON)]:::api
        LoadFile --> LLM_RAG[LLM 生成回答]:::api
    end

    %% 一般閒聊
    GeneralChat --> LLM_Chat[LLM 一般對話]:::api

    %% 輸出
    AskDest & AskDate & Finish & WeatherReport & SaveFile & LLM_RAG & LLM_Chat --> Response([回傳給使用者])

    %% Key Manager 說明 (註解)
    KeyManager[KeyManager: 三 Key 輪詢] -.->|提供 Headers| PlanMorning & PlanAfternoon & PlanNight & LLM_Chat & LLM_RAG
    style KeyManager fill:#fff,stroke:#333,stroke-dasharray: 5 5
    