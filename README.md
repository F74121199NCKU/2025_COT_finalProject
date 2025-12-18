docker pull ghcr.io/open-webui/open-webui:main  #下載docker image
#啟動與連結伺服器 --name後名字可自改
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name COT_AI ghcr.io/open-webui/open-webui:main

__開啟localhost__
ngrok config add-authtoken (YOUR ID)
ngrok http 3000
複製 Forwarding後的網址即可

架設docker_pipelines
docker-compose restart pipelines
docker-compose up -d    (需等待下載時間)