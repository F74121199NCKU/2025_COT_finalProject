docker pull ghcr.io/open-webui/open-webui:main  #下載docker image
#啟動與連結伺服器 --name後名字可自改
docker run -d -p 3000:8080 -v open-webui:/app/backend/data --name COT_AI ghcr.io/open-webui/open-webui:main
