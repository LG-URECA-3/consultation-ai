import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAPPER_PATH = os.path.join(BASE_DIR, 'word_mapper.json')

def load_expansion_rules(file_path=DEFAULT_MAPPER_PATH):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def expand_query(user_query, rules):
    """
    질문 내 패턴을 감지하여 검색용 키워드를 풍성하게 확장합니다.
    """
    expanded_terms = []
    
    for category, content in rules.items():
        # 패턴 중 하나라도 질문에 포함되어 있다면
        if any(pattern in user_query for pattern in content['patterns']):
            expanded_terms.append(content['expansion'])
    
    # 중복 제거 및 결합
    if expanded_terms:
        # 원문과 확장 키워드를 결합하여 검색 엔진(Vector DB)에 전달
        expansion_str = ", ".join(expanded_terms)
        return f"{user_query} ({expansion_str})"
    
    return user_query

import re

def safe_split(text):
    
    delimiters = [
        r'\s+및\s+',     # '및' 앞뒤 공백
        r'\s+하고\s+',   # '하고' 앞뒤 공백
        r'\s+혹은\s+',   # '혹은' 앞뒤 공백
        r'고\s+',        # '~하고' (연결 어미) 뒤에 공백이 있는 경우
        r'랑\s+'         # '~이랑' (접속 조사) 뒤에 공백이 있는 경우
    ]
    
    pattern = "|".join(delimiters)
    parts = re.split(pattern, text)
    
    # 공백 제거 및 빈 문자열 필터링
    return [p.strip() for p in parts if p.strip()]