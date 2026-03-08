"""AWS SSM Parameter Store에서 consultation-service 설정 로드."""
from __future__ import annotations

import os

SSM_PREFIX = "/config/consultation-service"

# SSM 파라미터 경로 -> 설정 키(환경변수명) 매핑
SSM_PARAM_TO_ENV: dict[str, str] = {
    f"{SSM_PREFIX}/openai_api_key": "OPENAI_API_KEY",
    f"{SSM_PREFIX}/friendli_token": "FRIENDLI_TOKEN",
    f"{SSM_PREFIX}/db_url": "DB_URL",
    f"{SSM_PREFIX}/db_user": "DB_USER",
    f"{SSM_PREFIX}/db_password": "DB_PASSWORD",
    f"{SSM_PREFIX}/redis_host": "REDIS_HOST",
    f"{SSM_PREFIX}/redis_password": "REDIS_PASSWORD",
    f"{SSM_PREFIX}/kafka_bootstrap_servers": "KAFKA_BOOTSTRAP_SERVERS",
    f"{SSM_PREFIX}/elasticsearch_uris": "ES_URL",
}


def load_ssm_into_env(
    *,
    prefix: str = SSM_PREFIX,
    param_to_env: dict[str, str] | None = None,
    region_name: str | None = None,
) -> dict[str, str]:
    """
    SSM Parameter Store에서 값을 읽어 os.environ에 주입.
    이미 설정된 환경변수는 덮어쓰지 않음(env 우선).
    반환값: 주입된 키-값 (로깅/디버깅용).
    """
    import boto3

    param_to_env = param_to_env or SSM_PARAM_TO_ENV
    names = list(param_to_env.keys())

    if not names:
        return {}

    try:
        client = boto3.client("ssm", region_name=region_name or os.getenv("AWS_REGION", "ap-northeast-2"))
        resp = client.get_parameters(Names=names, WithDecryption=True)
    except Exception:
        return {}

    injected: dict[str, str] = {}
    for param in resp.get("Parameters", []):
        name = param.get("Name")
        value = param.get("Value")
        if name is None or value is None:
            continue
        env_key = param_to_env.get(name)
        if not env_key:
            continue
        if os.environ.get(env_key) is not None:
            continue
        os.environ[env_key] = value.strip()
        injected[env_key] = value.strip()

    return injected
