# shop-bot-py 이미지(2장 2.1). 잠금 파일(해시 검사)로 설치하고, 일반 사용자(uid 10001)로 돈다.
# 실행: docker compose up --build   (직접: docker build -t shop-bot-py-lab .)
# 단계: base(의존성) → fake-mcp(mcp SDK가 필요한 가짜 MCP 서버) / app(기본, 마지막 단계)
FROM python:3.14.10-slim-trixie AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY labcore labcore
COPY shopbot shopbot
COPY tools tools
RUN useradd --system --uid 10001 app
USER app

FROM base AS fake-mcp
ENV BIND=0.0.0.0
EXPOSE 8095
CMD ["python", "-I", "tools/fake_mcp.py"]

FROM base AS app
# 컨테이너 안에서만 0.0.0.0으로 듣는다. 호스트 공개는 compose의 "127.0.0.1:" 바인딩으로만
ENV HOST=0.0.0.0
EXPOSE 8080 8082
CMD ["sh", "-c", "exec uvicorn shopbot.main:app --host \"$HOST\" --port 8080"]
