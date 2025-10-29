# EZtoEC
이지어드민to이카운트

## 설정 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 API 키를 입력하세요:
```bash
cp .env.example .env
```

그리고 `.env` 파일을 편집하여 실제 API 키를 입력합니다.

또는 환경 변수를 직접 설정할 수 있습니다:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 3. 실행

#### 이카운트 로그인
```bash
python main.py
```

#### GPT 클라이언트
```bash
python gpt_client.py
```
