FROM python:3.11-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
USER appuser
EXPOSE 8500
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8500"]
