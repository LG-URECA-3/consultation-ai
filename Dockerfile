# 1. retriever 기능을 지원 버전전
FROM docker.elastic.co/elasticsearch/elasticsearch:8.18.0

# 주석 해제 시 노리(Nori, 한글 형태소 분석기) 추가 가능
# RUN bin/elasticsearch-plugin install --batch analysis-nori