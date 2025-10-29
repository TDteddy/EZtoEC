# EZtoEC
이지어드민to이카운트

이지어드민에서 다운로드한 보고서를 이카운트 판매/매입/매입전표 양식으로 변환하는 프로그램입니다.

## 주요 기능

- 이카운트 로그인 API 연동 (`main.py`)
- OpenAI GPT API 연동 (`gpt_client.py`)
- 이지어드민 → 이카운트 엑셀 변환 (`excel_converter.py`)
  - 판매 데이터 변환
  - 매입 데이터 변환
  - 매입전표 (운송료/판매수수료) 생성

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
export ECOUNT_USER_ID="your-user-id"
export ECOUNT_API_CERT_KEY="your-api-cert-key"
export ECOUNT_COM_CODE="your-company-code"
```

## 사용 방법

### 1. 이카운트 로그인
```bash
python main.py
```

### 2. GPT 클라이언트
```bash
python gpt_client.py
```

### 3. 엑셀 변환 (이지어드민 → 이카운트)

#### 방법 1: 독립 실행
```bash
# 1. data/ 폴더에 이지어드민 엑셀 파일(.xlsx, .xls) 저장
# 2. rates.yml 파일에 프로젝트×판매채널별 요율 설정
# 3. 스크립트 실행
python excel_converter.py
```

#### 방법 2: 모듈로 import하여 사용
```python
from excel_converter import process_ezadmin_to_ecount, save_to_excel

# 데이터 처리 (DataFrame으로 반환)
result = process_ezadmin_to_ecount()

# 결과 구조
# result = {
#     "sales": 판매 DataFrame,
#     "purchase": 매입 DataFrame,
#     "voucher": 매입전표 DataFrame,
#     "by_project": {
#         "브랜드명": {
#             "sales": DataFrame,
#             "purchase": DataFrame,
#             "voucher": DataFrame
#         }
#     }
# }

# DataFrame 조회
print(result["sales"].head())
print(result["purchase"].head())
print(result["voucher"].head())

# 프로젝트별 데이터 조회
for project, data in result["by_project"].items():
    print(f"프로젝트: {project}")
    print(f"  판매: {len(data['sales'])}건")
    print(f"  매입: {len(data['purchase'])}건")
    print(f"  전표: {len(data['voucher'])}건")

# 파일로 저장 (선택적)
save_to_excel(result, "output_ecount.xlsx")
```

## 프로젝트 구조

```
EZtoEC/
├── data/                    # 이지어드민 엑셀 파일 저장 폴더
├── main.py                  # 이카운트 로그인 API
├── gpt_client.py            # OpenAI GPT API 클라이언트
├── excel_converter.py       # 엑셀 변환 모듈
├── rates.yml                # 운송료/판매수수료 요율 설정
├── requirements.txt         # 의존성 패키지
├── .env.example             # 환경 변수 예제
├── .gitignore               # Git 제외 파일
└── README.md                # 사용 설명서
```

## 요율 설정 (rates.yml)

`rates.yml` 파일에서 브랜드×판매채널별 운송료율과 판매수수료율을 설정합니다:

```yaml
닥터시드_국내:
  스마트스토어:
    shipping: 0.13      # 운송료율 13%
    commission: 0.06    # 판매수수료율 6%
  카페24:
    shipping: 0.09
    commission: 0.055
```

## 주의사항

- API 키와 인증 정보는 반드시 환경 변수로 관리하세요
- `.env` 파일은 Git에 커밋하지 마세요 (`.gitignore`에 포함됨)
- 이지어드민 엑셀 양식이 변경되면 `excel_converter.py`도 수정이 필요합니다
