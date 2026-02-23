# 상담 업무 지원 서비스 - AI 후처리
---
## 프로젝트 구조
```
consultation-ai/
├── .venv/               # Poetry 가상환경
├── app/                 # 메인 애플리케이션 소스 코드
│   ├── api/             # API 엔드포인트 정의
│   ├── core/            # 전역 설정 및 인프라 초기화
│   │   ├── config.py    # 환경 변수 및 앱 설정
│   │   └── infrastructure.py # DB/ES/AI 클라이언트 싱글톤 생성 및 세션 주입
│   ├── crud/            # 순수 DB 데이터 접근 로직
│   ├── kafka/           # Kafka 메시지 처리 로직
│   ├── models/          # DB 테이블 매핑 클래스
│   ├── schemas/         # API 요청/응답 형식 정의 (DTO 역할)
│   ├── services/        # 핵심 비즈니스 로직 및 AI 분석 프로세스
│   ├── tests/           # 단위 및 통합 테스트
│   │   ├── connection_test.py # 인프라(DB, ES, AI) 연결 확인용 테스트
│   │   └── embedding_test.py  # 임베딩 생성 및 벡터 검색 플로우 검증용 테스트
│   └── main.py          # 앱 진입점 및 FastAPI 초기화 (Spring Boot Main 클래스 역할)
├── .env                 # 로컬용 비밀 환경 변수 (DB 비번, API 키 등 / Git 제외)
├── poetry.lock          # 의존성 고정 파일
└── pyproject.toml       # 프로젝트 빌드 설정 및 의존성 관리
```

## 개발 환경 준비 (Prerequisites)
> 프로젝트 실행을 위해 설치되어야 합니다.
* Python 3.12+
* Poetry (Dependency Management)
```
1. Poetry 설치
# Windows
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -
```
*설치 후 터미널을 재실행하여 `poetry --version`이 뜨는지 확인하세요. 버전 확인 전 환경변수 등록이 필요합니다.*

* Docker Desktop

## 환경 세팅
### 1. 의존성 설정/라이브러리 설치
```
poetry config virtualenvs.in-project true
poetry install
```

### 2. 환경 변수 설정
`.env-example 파일을 복사하여 .env 파일을 생성합니다. your_*로 작성된 부분을 본인의 것(비밀번호, api-key 등)으로 작성합니다.
```
cp .env-example .env
```

### 3. 도커 실행
같은 Organization의 `consultation-service`와 동일한 도커 설정을 공유합니다. <br>
이 repository의 `docker-compose.yml` 파일은 `consultation-service`를 도커로 실행하지 않는 사용자에게 elasticsearch를 제공하기 위하여 작성되었습니다. <br>
따라서, `consultation-service`에서 도커를 실행하지 않은 경우에만 이 프로젝트 파일 경로에서 아래의 도커 실행 명령어를 입력해주세요. <br>

**구성 요소**
* ElasticSearch 8.12.0
* kibana 8.12.0
```
docker-compose up -d
```

### 4. 가상 환경 활성화 및 전환
터미널을 가상환경으로 전환합니다.
```
poetry shell
```

### 5. 연결 테스트
모든 환경 세팅이 완료되면 아래 명령어를 통해 테스트 스크립트가 정상적으로 작동하는지 확인합니다.
```
# 전체 인프라 연결 확인
python -m app.tests.connection_test

# OpenAI 임베딩 및 벡터 검색 확인
python -m app.tests.embedding_test
```

---
## Swagger (API 문서)

프로젝트 경로에서 아래 명령어로 서버를 실행합니다.

```
uvicorn app.main:app --reload
```

서버 실행 후 아래 링크에서 API 문서를 확인할 수 있습니다.

| Swagger UI                                                                     |
| ------------------------------------------------------------------------------ |
| [http://localhost:8000/docs](http://localhost:8000/docs) |