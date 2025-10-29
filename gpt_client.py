import os
from openai import OpenAI

# API 키는 환경 변수에서 가져오거나, 없으면 .env 파일에서 로드
# 사용법: export OPENAI_API_KEY="your-api-key-here"
client = OpenAI(
  api_key=os.environ.get("OPENAI_API_KEY")
)

response = client.responses.create(
  model="gpt-5-nano",
  input="write a haiku about ai",
  store=True,
)

print(response.output_text)
