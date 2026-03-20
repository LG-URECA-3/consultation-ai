<div align="center">

# 🤖 LG U+ 프리톡 - AI 서비스 (consultation-ai)
**FastAPI 기반 RAG 엔진 및 상담 데이터 후처리 파이프라인**

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI_0.131-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Elasticsearch](https://img.shields.io/badge/Elasticsearch_8.x-005571?style=for-the-badge&logo=elasticsearch&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Apache_Kafka-231F20?style=for-the-badge&logo=apache-kafka&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Poetry](https://img.shields.io/badge/Poetry-60A5FA?style=for-the-badge&logo=poetry&logoColor=white)

<br/>

> *메인 서버가 발행한 상담 종료 이벤트를 비동기로 소비하여, **상담 이력 인덱싱, FAQ 자동 생성, RAG 기반 실시간 검색 및 고객 성향 분석**을 수행하는 지능형 백엔드 서비스입니다.*

</div>

<br/>

## 📖 프로젝트 개요 (Introduction)

`consultation-ai`는 메인 상담 서버(`consultation-service`)의 워커 모듈이 Kafka에 발행한 이벤트를 기반으로 무거운 AI 후처리 작업을 전담하는 Python 기반 마이크로서비스입니다. 

### 💡 핵심 역할
* 🗂️ **상담 이력 ES 인덱싱:** 전체 상담 메시지와 요약 벡터를 Elasticsearch에 저장하여 초고속 시맨틱 검색 환경 구축
* 🪄 **FAQ 자동 생성 및 지식베이스화:** 신규 상담 요약을 기존 FAQ와 비교 분석(하이브리드 검색)하여, 자동으로 FAQ를 생성하고 관리
* ⚡ **실시간 FAQ 검색 (RAG):** 상담사가 질문 입력 시, 가장 적합한 FAQ를 검색하고 LLM이 맞춤형 답변을 즉시 합성하여 제공
* 📊 **고객 성향 분석 배치:** 매일 새벽(03:00) 대규모 상담 데이터를 분석하여 고객별 성향 지표(가격민감도, 결정스타일 등) 도출 및 저장

---

## 🏗 시스템 아키텍처 및 이벤트 흐름 (Architecture & Flow)

메시지 브로커(Kafka)를 통해 메인 서버와 느슨하게 결합(Loosely Coupled)되어 안정적인 비동기 파이프라인을 형성합니다.

```text
[consultation-service worker-module]
        │  Kafka Topic: consultation.summary.completed
        │  Payload: { consultation_id, record_id, timestamp }
        ▼
[ consultation-ai / AIOKafkaConsumer ]
        │
        ├─ Step 1: 상담 이력 ES 인덱싱
        │    DB 데이터 조회 → 임베딩 생성(text-embedding-3-small) → ES 인덱스 저장
        │
        └─ Step 2: FAQ 자동 매칭 / 지식베이스 생성
             ES 하이브리드 검색 (벡터 + BM25, 상품군 필터)
             ┌ score >= 0.9      → 기존 FAQ hit_count 증가
             ├ 0.6 <= score < 0.9 → LLM 동일 질문 판별 후 (hit_count 증가 OR 신규 생성)
             └ score < 0.6       → LLM 활용 신규 FAQ 생성 및 저장

[ FastAPI REST Endpoints ]
  ├─ POST /fastapi/v1/search/faq          ← 실시간 RAG 기반 FAQ 검색
  ├─ POST /fastapi/v1/search/consultations ← 조건별 통합 상담 이력 검색
  └─ GET  /fastapi/v1/consultations/{id}   ← 특정 상담 상세 이력 조회

[ Batch Job ]
  └─ 매일 03:00 → 전일 상담 데이터 추출 → LLM 고객 성향 분석(Friendli AI) → DB 적재
```

---

## 🛠 기술 스택 (Tech Stack)

| 분류 | 기술 | 비고 |
| :--- | :--- | :--- |
| **Language/Framework** | Python 3.12, FastAPI | 비동기 I/O 최적화 및 빠른 API 서빙 |
| **Data/Search** | SQLModel, AsyncElasticsearch | 비동기 ORM 및 검색 엔진 통신 |
| **Message Queue** | aiokafka | Kafka 이벤트 비동기 소비 |
| **AI / LLM** | OpenAI API, Friendli AI | `gpt-4o`, `text-embedding-3-small`, `EXAONE` 활용 |
| **Prompt Engineering** | instructor | LLM 응답을 Pydantic 모델로 구조화(Structured Output) |
| **Infra/Config** | Boto3 (AWS SSM), Poetry | 클라우드 파라미터 연동 및 의존성 관리 |

---

## 🗄️ Elasticsearch 인덱스 설계 (Index Design)

정교한 검색과 RAG 성능을 위해 두 개의 핵심 인덱스를 운용합니다.

### 1. `consultations_histories` (상담 이력)
* **목적:** 과거 상담 내용 전문 및 메타데이터 검색
* **주요 필드:** `consultation_id`(doc_id), `full_text`, `summary_vector`(512차원 dense_vector), `keywords`, `messages`(nested), 고객/상담사 메타데이터

### 2. `faq_knowledge_base` (지식베이스)
* **목적:** AI가 자동 생성한 FAQ 데이터 보관 및 RAG 검색 소스
* **주요 필드:** `faq_id`, `question`, `answer`, `question_vector`(512차원 dense_vector), `product_line_code`
* **스코어링(하이브리드 검색):** Vector Similarity(cosine) + BM25를 결합하여 문맥과 키워드 정확도를 모두 확보

---

## 🔌 주요 API 명세 (API Specification)

> 서버 실행 후 `http://localhost:8000/fastapi/docs` 에서 Swagger UI를 통해 테스트 가능합니다.

| Method | Endpoint | 설명 |
| :--- | :--- | :--- |
| `POST` | `/fastapi/v1/search/faq` | 질문 입력 시 RAG를 거쳐 최적의 답변과 참조 FAQ 반환 |
| `POST` | `/fastapi/v1/search/consultations` | 키워드, 담당자, 기간, 결과 코드 기반 상담 이력 다중 조건 검색 |
| `GET` | `/fastapi/v1/consultations/{id}` | 특정 상담의 전체 메시지 및 요약 상세 조회 |
| `GET` | `/fastapi/health/ready` | DB, ES 연동 상태를 포함한 Readiness 체크 |

---

## 📂 프로젝트 구조 (Directory Structure)

```text
consultation-ai/
├── app/
│   ├── api/           # 라우터 엔드포인트 (RAG 검색, 이력 검색 등)
│   ├── batch/         # 스케줄러 및 성향 분석 배치 작업 (매일 03:00)
│   ├── core/          # 환경변수, AWS SSM 연동, DB/ES 클라이언트 싱글톤
│   ├── crud/          # 비동기 DB 접근 레이어
│   ├── kafka/         # AIOKafkaConsumer 구독 및 이벤트 진입점
│   ├── models/        # SQLModel 엔티티 매핑
│   ├── schemas/       # Pydantic DTO (API 요청/응답 구조화)
│   ├── services/      # 핵심 비즈니스 로직 (RAG, 임베딩, 후처리 흐름 제어)
│   └── main.py        # FastAPI 앱 진입점 (Lifespan 이벤트 관리)
├── tests/             # 연결 및 임베딩/검색 로직 테스트 
├── docker-compose.yml # 로컬 개발용 ES/Kibana 컨테이너 설정
├── pyproject.toml     # Poetry 패키지 의존성 명세서
└── .env-example       # 로컬 환경 변수 템플릿
```

---

## 🚀 실행 방법 (Getting Started)

### 1. 환경 준비 및 의존성 설치
Python 3.12 이상 및 `Poetry`가 필요합니다.

```bash
$ cd consultation-ai
$ poetry config virtualenvs.in-project true
$ poetry install
```

### 2. 인프라 실행 및 환경 변수 설정
* `consultation-service`의 메인 인프라(MySQL, Kafka 등)가 실행 중이어야 합니다.
* `.env-example` 파일을 복사하여 `.env`를 생성하고 필수 API Key를 입력합니다.

```bash
$ cp .env-example .env
# .env 파일을 열어 OPENAI_API_KEY, FRIENDLI_TOKEN 및 DB 접속 정보 입력
```

### 3. 애플리케이션 실행

**FastAPI 웹 서버 실행 (API 및 Kafka Consumer 작동)**
```bash
# 가상환경 활성화
$ source .venv/bin/activate  # (Windows: .venv\Scripts\Activate.ps1)

# 서버 구동
$ uvicorn app.main:app --reload --port 8000
```

**고객 성향 분석 배치 수동 실행 (별도 프로세스)**
```bash
# 매일 03:00 스케줄러로 구동 대기
$ python -m app.batch.batch_scheduler

# 특정 일자 기준 즉시 강제 실행
$ python -m app.batch.batch_main --date 2026-03-19
```

---

## ⚙️ 환경 변수 설정 (Configuration)

운영 환경 배포 시 `ENVIRONMENT=production`으로 설정하면, 필요한 모든 민감 정보 및 인프라 주소를 **AWS SSM Parameter Store**(`/config/consultation-service/*`)에서 안전하게 자동 로드합니다.

| 주요 환경 변수 | 설명 |
| :--- | :--- |
| `OPENAI_API_KEY` | 텍스트 임베딩 및 FAQ 생성/RAG를 위한 OpenAI 키 (필수) |
| `FRIENDLI_TOKEN` | 고객 성향 분석 배치에 사용되는 EXAONE 모델 호출 키 (필수) |
| `ES_URL` / `ES_PASSWORD`| Elasticsearch 클러스터 접속 정보 |
| `KAFKA_BOOTSTRAP_SERVERS`| Kafka 브로커 주소 |
| `DB_HOST`, `DB_USER` 등 | 메인 MySQL 데이터베이스 접속 정보 |
