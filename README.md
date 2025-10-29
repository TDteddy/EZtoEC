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
# OpenAI & Ecount API
export OPENAI_API_KEY="your-api-key-here"
export ECOUNT_USER_ID="your-user-id"
export ECOUNT_API_CERT_KEY="your-api-cert-key"
export ECOUNT_COM_CODE="your-company-code"

# MySQL Database
export DB_HOST="localhost"
export DB_USER="root"
export DB_PASSWORD="your-mysql-password"
export DB_NAME="seller_mapping"
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

### 3. 판매처 이름 통일 (선택 사항)

이지어드민 원천데이터에 같은 판매처가 다른 이름으로 나오는 경우 (예: "지마켓", "G마켓"), 판매처 매핑 DB를 사용하여 통일할 수 있습니다.

**MySQL 데이터베이스 사용**: SQLite 대신 MySQL을 사용하여 판매처 매핑을 관리합니다. 데이터베이스가 없으면 자동으로 생성됩니다.

#### DB 초기화 및 기본 매핑 등록
```bash
# 환경 변수에 MySQL 접속 정보 설정 (.env 파일)
# DB_HOST=localhost
# DB_USER=root
# DB_PASSWORD=your-password
# DB_NAME=seller_mapping

# 기본 매핑과 함께 DB 초기화 (G마켓, 카카오선물하기, 스마트스토어, 쿠팡 등)
python seller_mapping.py init
```

#### CLI 메뉴로 관리
```bash
# 대화형 메뉴 실행
python seller_mapping.py

# 사용 가능한 기능:
# 1. DB 초기화
# 2. 매핑 추가 (개별)
# 3. 매핑 추가 (그룹)
# 4. 전체 매핑 보기
# 5. 매핑 테스트
# 6. CSV로 내보내기
# 7. CSV에서 가져오기
```

#### 프로그래밍 방식 사용
```python
from seller_mapping import SellerMappingDB

with SellerMappingDB() as db:
    # 그룹으로 추가 (여러 별칭 → 하나의 표준 이름)
    db.add_group(
        aliases=["지마켓", "G마켓", "gmarket"],
        standard_name="G마켓"
    )

    # 매핑 테스트
    print(db.normalize_name("지마켓"))  # → "G마켓"
    print(db.normalize_name("gmarket"))  # → "G마켓"
```

**자동 적용:** 판매처 매핑 DB가 있으면 엑셀 변환 시 자동으로 판매처 이름이 정규화됩니다.

#### GPT 기반 오타 교정 및 웹 에디터

**수동발주 케이스 전용**: 코드10에 있는 거래처/판매처가 DB에 없을 때:

1. **DB 매칭 우선**: DB에 있는 판매처는 자동으로 매핑
2. **GPT 오타 교정**: DB에 없는 판매처는 GPT API가 유사한 이름 추천 (신뢰도 70% 이상)
3. **웹 에디터**: GPT가 낮은 신뢰도로 판단하거나 매칭하지 못한 판매처는 웹 인터페이스에서 수동 매핑

```python
from seller_mapping import SellerMappingDB

with SellerMappingDB() as db:
    # GPT로 오타 교정 시도
    result = db.find_similar_with_gpt("지마켓")

    if result and not result['requires_manual']:
        # 자동 매핑 성공
        print(f"매칭됨: {result['matched']} (신뢰도: {result['confidence']})")
    else:
        # 수동 매핑 필요 - 웹 에디터 사용
        from seller_editor import start_editor
        start_editor([result], port=5000)
```

**웹 에디터 사용:**
```bash
# 매핑이 필요한 판매처가 있을 때 자동으로 웹 에디터가 열립니다
# 브라우저에서 http://localhost:5000 접속하여 수동 매핑
python seller_editor.py
```

### 4. 엑셀 변환 (이지어드민 → 이카운트)

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

### 5. 이카운트 API 업로드 (통합)

이지어드민 엑셀 변환 → 이카운트 API 업로드를 한 번에 실행:

#### 통합 실행 (권장)
```bash
# 1. data/ 폴더에 이지어드민 엑셀 파일 저장
# 2. 환경 변수 설정
# 3. 실행
python main.py
```

#### 실행 모드
```bash
# 통합 처리 (변환 + 로그인 + 업로드)
python main.py

# 로그인만 테스트
python main.py login

# 엑셀 변환만 수행
python main.py convert
```

**처리 흐름:**
1. data/ 폴더의 이지어드민 엑셀 파일 변환
2. 이카운트 로그인
3. 판매 데이터 API 전송
4. 구매 데이터 API 전송

#### 프로그래밍 방식 사용
```python
from main import process_and_upload

# 통합 처리 함수 사용
results = process_and_upload(
    upload_sales=True,      # 판매 데이터 업로드
    upload_purchase=True,   # 구매 데이터 업로드
    save_excel=True         # 엑셀 파일로도 저장
)

# 결과 확인
print(results["sales_upload"]["success_count"])
print(results["purchase_upload"]["success_count"])
```

#### 개별 함수 사용
```python
from excel_converter import process_ezadmin_to_ecount
from main import login_ecount, save_sale, save_purchase
import os

# 1. 엑셀 변환
result = process_ezadmin_to_ecount()
sales_df = result["sales"]
purchase_df = result["purchase"]

# 2. 이카운트 로그인
login_result = login_ecount(
    com_code=os.environ.get("ECOUNT_COM_CODE"),
    user_id=os.environ.get("ECOUNT_USER_ID"),
    api_cert_key=os.environ.get("ECOUNT_API_CERT_KEY"),
    zone="AD",
    test=True
)
session_id = login_result["Data"]["Datas"]["SESSION_ID"]

# 3. 판매 데이터 업로드
if not sales_df.empty:
    sale_result = save_sale(session_id, sales_df, zone="AD", test=True)
    print(f"판매 업로드: {sale_result['Data']['SuccessCnt']}건 성공")

# 4. 구매 데이터 업로드
if not purchase_df.empty:
    purchase_result = save_purchase(session_id, purchase_df, zone="AD", test=True)
    print(f"구매 업로드: {purchase_result['Data']['SuccessCnt']}건 성공")
```

## 프로젝트 구조

```
EZtoEC/
├── data/                    # 이지어드민 엑셀 파일 저장 폴더
├── main.py                  # 통합 메인 파일 (로그인/판매/구매 API + 통합 실행)
├── gpt_client.py            # OpenAI GPT API 클라이언트
├── excel_converter.py       # 엑셀 변환 모듈
├── seller_mapping.py        # 판매처 이름 통일 관리 (MySQL DB)
├── seller_editor.py         # 판매처 수동 매핑 웹 에디터 (Flask)
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

## API 필드 매핑

### 전표 묶음 순번 (UPLOAD_SER_NO)
이카운트 API는 같은 순번을 가진 데이터를 하나의 전표로 묶어 처리합니다.

**자동 할당 규칙:**
- 같은 **브랜드(프로젝트)** + **판매채널(부서)**를 가진 데이터는 동일한 순번으로 묶임
- 순번은 1부터 자동 할당
- 예시:
  - 닥터시드_국내 + 스마트스토어 → 순번 1
  - 닥터시드_국내 + 카페24 → 순번 2
  - 딸로_국내 + 스마트스토어 → 순번 3

이를 통해 동일한 프로젝트와 판매채널의 여러 품목이 하나의 전표로 묶여 처리됩니다.

### 판매 API 매핑
| 엑셀 필드 | 이카운트 API 필드 | 설명 |
|----------|-----------------|------|
| 일자 | IO_DATE | 판매일자 (YYYYMMDD) |
| 순번 | UPLOAD_SER_NO | 전표 묶음 순번 (자동 할당) |
| 브랜드 | PJT_CD | 프로젝트 코드 |
| 판매채널 | SITE | 부서 |
| 거래처명 | CUST_DES | 거래처명 |
| 출하창고 | WH_CD | 창고코드 |
| 주문번호 | ADD_TXT_03 | 추가문자형식3 |
| 상품코드 | PROD_CD | 품목코드 |
| 품목명 | PROD_DES | 품목명 |
| 옵션 | ADD_TXT_04 | 추가문자형식4 |
| 수량 | QTY | 수량 |
| 단가(vat포함) | USER_PRICE_VAT | VAT 포함 단가 |
| 공급가액 | SUPPLY_AMT | 공급가액(원화) |
| 부가세 | VAT_AMT | 부가세 |
| 송장번호 | REMARKS | 적요 |
| 수령자주소 | ADD_TXT_01 | 추가문자형식1 |
| 수령자이름 | P_REMARKS1 | 적요1 |
| 수령자전화 | P_REMARKS2 | 적요2 |
| 수령자휴대폰 | P_REMARKS3 | 적요3 |
| 배송메모 | ADD_TXT_02 | 추가문자형식2 |
| 주문상세번호 | ADD_TXT_05 | 추가문자형식5 |

### 구매 API 매핑
| 엑셀 필드 | 이카운트 API 필드 | 설명 |
|----------|-----------------|------|
| 일자 | IO_DATE | 구매일자 (YYYYMMDD) |
| 순번 | UPLOAD_SER_NO | 전표 묶음 순번 (자동 할당) |
| 브랜드 | PJT_CD | 프로젝트 코드 |
| 판매채널 | SITE | 부서 |
| 거래처명 | CUST_DES | 거래처명 |
| 입고창고 | WH_CD | 창고코드 |
| 품목명 | PROD_DES | 품목명 |
| 수량 | QTY | 수량 |
| 단가 | PRICE | 단가 |
| 공급가액 | SUPPLY_AMT | 공급가액(원화) |
| 부가세 | VAT_AMT | 부가세 |
| 적요 | REMARKS | 적요 |

## 주의사항

- API 키와 인증 정보는 반드시 환경 변수로 관리하세요
- `.env` 파일은 Git에 커밋하지 마세요 (`.gitignore`에 포함됨)
- 이지어드민 엑셀 양식이 변경되면 `excel_converter.py`도 수정이 필요합니다
- 이카운트 API 필수 필드는 회사별 설정에 따라 다를 수 있습니다
- 테스트 서버(`USE_TEST_SERVER=True`)에서 먼저 테스트 후 운영 서버로 전환하세요
