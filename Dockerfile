FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
# LibreOffice (jen Calc a Writer, bez GUI) převádí šablony dokumentů do PDF; písma kompatibilní s Arial/Calibri
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-calc-nogui libreoffice-writer-nogui fonts-liberation fonts-crosextra-carlito fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# ochrana proti Windows konců řádků (CRLF) ve skriptu
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
