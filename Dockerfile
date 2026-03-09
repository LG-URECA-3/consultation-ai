# consultation-ai API (FastAPI)
FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 (필요 시 추가)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Poetry 설치 (로컬과 동일한 2.x 사용 - lock 파일 호환)
ENV POETRY_VERSION=2.3.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

@@ -18,18 +18,18 @@

ENV PATH="${POETRY_HOME}/bin:${PATH}"

# 의존성만 먼저 설치 (캐시 활용, dev 제외)
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root --no-interaction

# 애플리케이션 코드
COPY app ./app

# 비 root 사용자 (선택)
# RUN adduser --disabled-password appuser && chown -R appuser:appuser /app
# USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# retriever 기능을 지원 버전
# FROM docker.elastic.co/elasticsearch/elasticsearch:8.18.0

# 주석 해제 시 노리(Nori, 한글 형태소 분석기) 추가 가능
# RUN bin/elasticsearch-plugin install --batch analysis-nori