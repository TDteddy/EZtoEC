# EZtoEC
이지어드민 to 이카운트

이지어드민에서 다운로드한 보고서를 이카운트 판매/매입/매입전표 양식으로 변환하고, 자동으로 이카운트 API에 업로드하는 프로그램입니다.

**NEW! 쿠팡 로켓그로스 판매 데이터 처리 지원** 🎉

## 🌟 주요 기능

### 1. **완전 자동화 워크플로우**
```
이지어드민 엑셀 → 데이터 검증 → GPT 오타 교정 → 웹 에디터 → Ecount API 업로드 → 완료
```
- **매핑 후 자동 재검증**: 웹 에디터에서 매핑 완료 후 Enter만 누르면 자동으로 재검증 및 업로드 진행 (프로그램 재시작 불필요)
- **배치 자동 분할**: 300건 초과 시 전표번호별로 자동 분할 업로드

### 2. **쿠팡 로켓그로스 데이터 처리** 🆕
```
sales DB 조회 → 상품 매핑 → GPT 자동 매칭 → 수량 계산 → Ecount API 업로드 → 완료
```
- **별도 DB 조회**: `sales.sales_report_coupang_2p` 테이블에서 판매 데이터 직접 조회
- **GPT 상품 매칭**: 쿠팡 옵션명을 이지어드민 스탠다드 상품과 자동 매칭
- **수량 배수 처리**: N개 묶음 상품 자동 계산 (예: 3개입 → 실제 3개 판매)
- **브랜드 자동 인식**: 상품명 기반 브랜드 자동 분류

### 3. **지능형 데이터 검증**
- **수동발주 케이스 자동 검증**: 코드10 필드의 판매처 이름을 DB와 비교
- **GPT 기반 오타 교정**: AI가 자동으로 유사한 판매처 이름 찾기 (신뢰도 70% 이상)
- **웹 에디터 통합**: 정제 불가 데이터는 웹 UI에서 수동 매핑
- **빈 값 사전 검증**: 수동발주의 코드10 빈 값은 프로그램 실행 전에 체크하여 조기 차단

### 4. **스마트 브랜드 인식**
- **브라이즈 판매처 특수 처리**: 상품명에서 브랜드 추출
- **에이더 정규식 패턴**: `5자 알파벳 + 2자 숫자`로 시작하면 자동 인식 (예: ABCDE12)
- **키워드 매칭**: 딸로, 닥터시드, 테르스 자동 인식

### 5. **전표 자동 그룹화**
- **일자 + 브랜드 + 판매채널** 기준으로 자동 그룹화
- 같은 날짜의 같은 브랜드/판매채널만 하나의 전표로 묶음
- 전표묶음순번 자동 할당 (각 배치마다 1부터 시작)

### 6. **매입전표 자동 생성**
- rates.yml 기반 운반비/수수료 자동 계산
- 브랜드×판매채널별 요율 적용

### 7. **특수 케이스 자동 처리**
- **타사 재고 채움**: 성원글로벌, 에이원비앤에이치, 글로벌엠지코리아 → 매출 0원 처리
- **제외 판매처**: 로켓그로스, 전용수동발주 에이더 → 자동 제외 (이지어드민 처리 시)
- **배치 업로드**: 이카운트 API 제한(300건)에 맞춰 자동 분할

---

## 📋 완전한 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: 이지어드민 엑셀 파일을 data/ 폴더에 배치              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: python main.py 실행                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: 데이터 변환 및 검증                                  │
│  ├─ 로켓그로스/전용수동발주 에이더 제외                        │
│  ├─ 수동발주 코드10 빈 값 검증 (조기 차단)                    │
│  ├─ 판매/매입 데이터 변환                                    │
│  ├─ 브랜드 자동 추출 (브라이즈/에이더 특수 처리)               │
│  ├─ 타사 재고 채움 판매처 → 매출 0원 처리                    │
│  ├─ 매입전표 생성 (운반비/수수료)                             │
│  └─ 판매처 검증                                             │
│      ├─ DB 매칭 확인 ✅ PASS                                │
│      ├─ GPT 오타 교정 (신뢰도 ≥70%) ✅ 자동 교정              │
│      └─ 정제 불가 ⚠️ pending_mappings 수집                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                  (정제 불가 데이터 있음?)
                         │
                    YES  │  NO
                         │  └─→ STEP 5로
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: 웹 에디터 자동 실행 (http://localhost:5000)          │
│  ├─ GPT 추천 표시 (신뢰도와 함께)                             │
│  ├─ 사용자가 수동 매핑                                       │
│  ├─ DB에 자동 저장                                          │
│  ├─ Enter로 계속 진행                                       │
│  └─ → 자동으로 STEP 3 재검증 (최대 5회) 🔄                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Ecount 로그인                                       │
│  └─ SESSION_ID 획득                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: Ecount API 배치 업로드                               │
│  ├─ 판매 데이터 업로드                                       │
│  │   ├─ 300건 초과 시 전표번호별 자동 분할                   │
│  │   ├─ 배치 1/3 (300건) ✅                                 │
│  │   ├─ 배치 2/3 (300건) ✅                                 │
│  │   └─ 배치 3/3 (250건) ✅                                 │
│  └─ 구매 데이터 업로드 (동일한 배치 처리)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: 엑셀 OUTPUT 생성 (선택)                              │
│  ├─ output_ecount.xlsx (통합 파일)                          │
│  ├─ output_ecount_에이더_국내.xlsx                          │
│  ├─ output_ecount_딸로_국내.xlsx                            │
│  └─ output_ecount_닥터시드_국내.xlsx                         │
│      (매입전표 시트 포함: 운반비+수수료)                       │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
                    ✅ 완료!
```

---

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env.example`을 복사하여 `.env` 파일 생성:
```bash
cp .env.example .env
```

`.env` 파일 편집:
```bash
# OpenAI API (GPT 오타 교정용)
OPENAI_API_KEY=your-openai-api-key

# Ecount API
ECOUNT_USER_ID=your-user-id
ECOUNT_API_CERT_KEY=your-api-cert-key
ECOUNT_COM_CODE=your-company-code
ECOUNT_LAN_TYPE=ko-KR

# MySQL Database (판매처 매핑용)
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=seller_mapping
```

### 3. MySQL 판매처 매핑 DB 초기화
```bash
# DB 초기화 (테이블 생성 + 기본 매핑 등록)
python seller_mapping.py init
```

기본 매핑 목록:
- G마켓: 지마켓, G마켓, gmarket
- 카카오선물하기: 카카오, 선물하기, 카카오선물하기
- 스마트스토어: 스마트스토어, 네이버스마트스토어
- 쿠팡: 쿠팡, coupang

### 4. 이지어드민 엑셀 파일 준비
```bash
# data/ 폴더에 엑셀 파일 배치
cp 이지어드민_2024_01.xlsx ./data/
```

### 5. 프로그램 실행
```bash
# 완전한 워크플로우 실행
python main.py
```

**실행 과정**:
1. 엑셀 변환 및 데이터 검증
2. 정제 불가 데이터 발견 시 웹 에디터 자동 오픈 (http://localhost:5000)
3. 수동 매핑 완료 후 Enter → **자동으로 재검증 및 업로드 진행** ✨
4. 300건 초과 시 자동 배치 분할 업로드
5. 엑셀 파일 생성

---

## 📖 상세 사용 방법

### 실행 모드

```bash
# 1. 완전한 워크플로우 - 이지어드민 (기본, 권장)
python main.py
# → 변환 → 검증 → (웹 에디터) → 자동 재검증 → API 업로드 → 엑셀 저장

# 2. 쿠팡 로켓그로스 처리 🆕
python main.py coupang 2025-01-15
# → DB 조회 → 상품 매핑 → GPT 자동 매칭 → API 업로드 → 엑셀 저장

# 또는 대화형으로
python main.py coupang
# → 날짜 입력 프롬프트 (YYYY-MM-DD)

# 3. 로그인만 테스트
python main.py login
# → Ecount 로그인 테스트, SESSION_ID 확인

# 4. 엑셀 변환만 (API 업로드 제외)
python main.py convert
# → 변환 → 검증 → (웹 에디터) → 엑셀 저장
```

---

## 🔍 핵심 기능 상세

### 1. 브랜드 자동 추출

#### 일반 판매처
```
판매처: "딸로 쇼핑몰" → 브랜드: "딸로"
판매처: "닥터시드(스마트스토어)" → 브랜드: "닥터시드"
```

#### 브라이즈 판매처 (특수 처리)
```python
# 상품명에서 키워드 추출
판매처: "브라이즈"
상품명: "딸로 비타민" → 브랜드: "딸로"
상품명: "닥터시드 오메가3" → 브랜드: "닥터시드"

# 에이더 정규식 패턴 (5자 알파벳 + 2자 숫자)
판매처: "브라이즈"
상품명: "ABCDE12 상품명" → 브랜드: "에이더" ✅
상품명: "HELLO99 테스트" → 브랜드: "에이더" ✅
상품명: "ABC123 테스트" → 브랜드: "브라이즈" (패턴 불일치)
```

### 2. 판매처 이름 정규화

#### DB 매핑 (자동 PASS)
```python
입력: "지마켓"
출력: "G마켓" ✅ (DB에 매핑 있음)
```

#### GPT 오타 교정 (자동)
```python
입력: "G마켓123" (DB에 없음)
GPT 분석: "G마켓"과 95% 유사
출력: "G마켓" ✅ (자동 교정 + DB에 저장)
```

#### 웹 에디터 (수동)
```python
입력: "알수없는판매처" (DB에 없음)
GPT 분석: 유사한 이름 없음, 신뢰도 20%
동작: 웹 에디터 실행 → 사용자 수동 매핑 ⚠️
     → Enter 누르면 자동 재검증 → 업로드 진행 ✨
```

### 3. 전표 자동 그룹화

**그룹화 기준**: 일자 + 브랜드 + 판매채널

```
일자       브랜드        판매채널       전표묶음순번
2024-01-15 에이더_국내   G마켓         1
2024-01-15 에이더_국내   G마켓         1  (같은 그룹)
2024-01-15 에이더_국내   쿠팡          2  (다른 판매채널)
2024-01-15 딸로_국내     G마켓         3  (다른 브랜드)
2024-01-16 에이더_국내   G마켓         4  (다른 날짜)
```

**중요**: 날짜가 다르면 같은 브랜드/판매채널이어도 별도 전표로 처리됩니다.

### 4. 배치 자동 분할 (300건 제한)

이카운트 API는 1회 업로드 시 최대 300건까지만 허용합니다. 프로그램이 자동으로 처리합니다:

```
총 850건 → 3개 배치로 자동 분할

배치 1: 300건 (전표 1~5번 완전 포함)
배치 2: 300건 (전표 6~10번 완전 포함)
배치 3: 250건 (전표 11~15번 완전 포함)

✅ 전표는 절대 중간에 끊기지 않음
```

**특수 케이스**: 한 전표가 300건 초과
```
전표 A: 500건 → 배치 1 (300건) + 배치 2 (200건)
```

### 5. 특수 판매처 처리

#### 타사 재고 채움 (매출 0원)
```python
# excel_converter.py에서 자동 처리
ZERO_SALES_PARTNERS = [
    "성원글로벌",
    "에이원비앤에이치",
    "글로벌엠지코리아"
]

# 코드10에 위 판매처가 있으면:
# - 단가(vat포함) = 0
# - 단가 = 0
# - 공급가액 = 0
# - 부가세 = 0
# → 물건은 나가지만 매출은 0으로 처리
```

**추가 방법**: `excel_converter.py`의 `ZERO_SALES_PARTNERS` 리스트에 판매처 추가

#### 제외 판매처
```python
# 자동 제외되는 판매처 (처리 대상에서 완전 제외)
- 로켓그로스
- 전용수동발주 에이더
```

### 6. 매입전표 자동 생성

rates.yml 설정:
```yaml
에이더_국내:
  G마켓:
    shipping: 0.13      # 운송료 13%
    commission: 0.06    # 판매수수료 6%
  쿠팡:
    shipping: 0.15      # 운송료 15%
    commission: 0.08    # 판매수수료 8%
```

계산 예시:
```
공급가액: 100,000원
운송료: 100,000 × 0.13 = 13,000원
판매수수료: 100,000 × 0.06 = 6,000원
합계: 19,000원 (부가세 별도)
```

---

## 🛠️ 판매처 매핑 DB 관리

### CLI 메뉴
```bash
python seller_mapping.py

# 메뉴:
# 1. DB 초기화
# 2. 매핑 추가 (개별)
# 3. 매핑 추가 (그룹)
# 4. 전체 매핑 보기
# 5. 매핑 테스트
# 6. CSV로 내보내기
# 7. CSV에서 가져오기
```

### 프로그래밍 방식
```python
from seller_mapping import SellerMappingDB

with SellerMappingDB() as db:
    # 그룹으로 추가
    db.add_group(
        aliases=["지마켓", "G마켓", "gmarket"],
        standard_name="G마켓"
    )

    # 정규화 테스트
    print(db.normalize_name("지마켓"))  # → "G마켓"

    # GPT 오타 교정
    result = db.find_similar_with_gpt("G마켓123")
    if not result['requires_manual']:
        print(f"매칭: {result['matched']} (신뢰도: {result['confidence']:.0%})")
```

---

## 🌐 웹 에디터 사용법

### 자동 실행
`python main.py` 실행 시 정제 불가 데이터가 있으면 자동으로 실행됩니다.

### 수동 실행
```bash
python seller_editor.py
```

### 웹 UI
```
http://localhost:5000

┌─────────────────────────────────────────┐
│  판매처 이름 매핑 에디터                   │
├─────────────────────────────────────────┤
│  📝 지마켓                               │
│  🤖 GPT 추천: G마켓 (신뢰도: 95%)         │
│  ┌─────────────────────────┐            │
│  │ [✓] G마켓               │            │
│  │ [ ] 카카오선물하기        │            │
│  │ [ ] ➕ 새로운 이름 입력   │            │
│  └─────────────────────────┘            │
├─────────────────────────────────────────┤
│  [💾 모든 매핑 저장]                      │
└─────────────────────────────────────────┘
```

**중요**: 매핑 저장 후 터미널로 돌아가서 **Enter만 누르면** 자동으로 재검증 및 업로드가 진행됩니다.

---

## 📂 프로젝트 구조

```
EZtoEC/
├── data/                    # 이지어드민 엑셀 파일 저장 폴더
├── main.py                  # 메인 진입점 (완전한 워크플로우)
├── excel_converter.py       # 엑셀 변환 + 데이터 검증
├── seller_mapping.py        # 판매처 매핑 DB 관리 (MySQL + GPT 통합)
├── seller_editor.py         # 판매처 수동 매핑 웹 에디터 (Flask)
├── rates.yml                # 운송료/판매수수료 요율 설정
├── requirements.txt         # 의존성 패키지
├── .env.example             # 환경 변수 예제
├── .gitignore               # Git 제외 파일
└── README.md                # 이 파일
```

---

## 🔧 프로그래밍 API

### 완전한 워크플로우
```python
from main import process_and_upload

results = process_and_upload(
    upload_sales=True,      # 판매 데이터 업로드
    upload_purchase=True,   # 구매 데이터 업로드
    save_excel=True         # 엑셀 파일로도 저장
)

# 결과 확인
print(results["excel_conversion"]["success"])
print(results["sales_upload"]["success_count"])
print(results["sales_upload"]["batch_count"])  # 배치 개수
print(results["purchase_upload"]["success_count"])
```

### 개별 단계 실행
```python
from excel_converter import process_ezadmin_to_ecount, save_to_excel
from main import login_ecount, save_sale, save_purchase

# 1. 엑셀 변환 및 검증
result, pending_mappings = process_ezadmin_to_ecount()

# 2. 정제 불가 데이터 처리
if pending_mappings:
    from seller_editor import start_editor
    start_editor(pending_mappings, port=5000)

# 3. Ecount 로그인
login_result = login_ecount(...)
session_id = login_result["Data"]["Datas"]["SESSION_ID"]

# 4. API 업로드 (배치는 자동 처리됨)
save_sale(session_id, result["sales"])
save_purchase(session_id, result["purchase"])

# 5. 엑셀 저장
save_to_excel(result, "output_ecount.xlsx")
```

### 반환 데이터 구조
```python
result = {
    "sales": pd.DataFrame,          # 판매 데이터
    "purchase": pd.DataFrame,       # 매입 데이터
    "voucher": pd.DataFrame,        # 매입전표 (운반비+수수료)
    "by_project": {
        "에이더_국내": {
            "sales": pd.DataFrame,
            "purchase": pd.DataFrame,
            "voucher": pd.DataFrame
        },
        "딸로_국내": {...},
        ...
    }
}

pending_mappings = [
    {
        "original": "알수없는판매처",
        "gpt_suggestion": "G마켓",
        "confidence": 0.3,
        "requires_manual": True,
        "reason": "신뢰도가 낮아 수동 확인이 필요합니다."
    },
    ...
]

upload_results = {
    "sales_upload": {
        "success": True,
        "success_count": 850,
        "fail_count": 0,
        "batch_count": 3,  # 배치 개수
        "slip_nos": ["2025-001", "2025-002", ...]
    }
}
```

---

## 📊 API 필드 매핑

### 전표 묶음 순번 (UPLOAD_SER_NO)
이카운트 API는 같은 순번을 가진 데이터를 하나의 전표로 묶어 처리합니다.

**자동 할당 규칙:**
- 같은 **일자** + **브랜드(프로젝트)** + **판매채널(부서)**를 가진 데이터는 동일한 순번
- 순번은 각 배치마다 1부터 자동 할당
- 예시:
  - 2024-01-15 + 닥터시드_국내 + 스마트스토어 → 순번 1
  - 2024-01-15 + 닥터시드_국내 + 카페24 → 순번 2
  - 2024-01-15 + 딸로_국내 + 스마트스토어 → 순번 3
  - 2024-01-16 + 닥터시드_국내 + 스마트스토어 → 순번 4 (날짜 다름)

### 판매 API (SaveSale)
| 이지어드민 | 이카운트 API | 비고 |
|----------|-------------|------|
| 주문일 | IO_DATE | YYYYMMDD (예: 20180612) |
| (자동) | UPLOAD_SER_NO | 전표묶음순번 (일자+브랜드+판매채널) |
| 브랜드 | PJT_CD | 프로젝트 코드 |
| 판매채널 | SITE | 부서 |
| 거래처명 | CUST_DES | 정규화된 이름 |
| 출하창고 | WH_CD | 고정값: "200" |
| 품목명 | PROD_DES | 상품명 + 옵션 |
| 수량 | QTY | 정수 |
| 판매단가 | USER_PRICE_VAT | VAT 포함 |
| 공급단가 | SUPPLY_AMT | VAT 별도 |

### 구매 API (SavePurchases)
| 이지어드민 | 이카운트 API | 비고 |
|----------|-------------|------|
| 발주일 | IO_DATE | YYYYMMDD (예: 20180612) |
| (자동) | UPLOAD_SER_NO | 전표묶음순번 (일자+브랜드+판매채널) |
| 브랜드 | PJT_CD | 프로젝트 코드 |
| 거래처명 | SITE | 부서 |
| 거래처명 | CUST_DES | 정규화된 이름 |
| 입고창고 | WH_CD | 고정값: "200" |
| 품목명 | PROD_DES | 상품명 + 옵션 |
| 수량 | QTY | 정수 |
| 공급단가 | PRICE | VAT 별도 |

---

## ⚙️ 설정 및 커스터마이징

### 타사 재고 채움 판매처 추가
`excel_converter.py` 파일의 `ZERO_SALES_PARTNERS` 리스트 수정:
```python
ZERO_SALES_PARTNERS = [
    "성원글로벌",
    "에이원비앤에이치",
    "글로벌엠지코리아",
    "새로운판매처",  # 여기에 추가
]
```

### 배치 크기 변경
`main.py` 파일에서 `batch_size` 파라미터 수정:
```python
# 기본값: 300건
batches = split_dataframe_into_batches(df, batch_size=300)

# 변경 예시: 200건
batches = split_dataframe_into_batches(df, batch_size=200)
```

### GPT 신뢰도 임계값 조정
`seller_mapping.py` 파일에서 `threshold` 파라미터 수정:
```python
# 기본값: 0.7 (70%)
result = db.find_similar_with_gpt(seller_name, threshold=0.7)

# 더 엄격하게: 0.9 (90%)
result = db.find_similar_with_gpt(seller_name, threshold=0.9)
```

---

## ⚠️ 주의사항

### 보안
- API 키와 인증 정보는 반드시 환경 변수로 관리
- `.env` 파일은 Git에 커밋하지 말 것 (`.gitignore`에 포함됨)
- MySQL 비밀번호는 강력하게 설정

### 데이터
- 이지어드민 엑셀 양식이 변경되면 `excel_converter.py` 수정 필요
- 이카운트 API 필수 필드는 회사별 설정에 따라 다를 수 있음
- **테스트 서버**(`USE_TEST_SERVER=True`)에서 먼저 테스트 후 운영 서버로 전환

### 배치 업로드
- 이카운트 API는 1회 최대 300건 제한
- 전표는 절대 중간에 끊기지 않음 (자동 처리)
- 한 전표가 300건 초과 시에도 자동 분할됨

### MySQL
- 판매처 매핑 DB는 선택 사항이지만 **강력히 권장**
- MySQL 없이도 작동하지만 검증 단계가 건너뛰어짐
- 초기 설정 후 지속적으로 매핑 데이터 축적 필요

### GPT API
- GPT API 없이도 작동 (수동 매핑만 사용)
- 신뢰도 임계값(70%)은 `seller_mapping.py`에서 조정 가능
- GPT-4o-mini 모델 사용 (비용 효율적)

### 웹 에디터 사용 시
- 매핑 완료 후 반드시 터미널로 돌아가서 **Enter** 입력
- Enter를 누르면 자동으로 재검증 및 업로드 진행
- 최대 5회까지 매핑/재검증 반복 가능

---

## 🐛 문제 해결

### MySQL 연결 실패
```bash
# MySQL 설치 확인
mysql --version

# DB 접속 테스트
mysql -h localhost -u root -p

# .env 파일 확인
cat .env | grep DB_
```

### 웹 에디터가 안 열림
```bash
# 포트 5000 사용 중인지 확인
lsof -i :5000

# 다른 포트 사용
python seller_editor.py  # 코드에서 port 변경 필요
```

### Ecount API 오류
```bash
# 테스트 서버에서 먼저 실행
# main.py의 USE_TEST_SERVER = True 확인

# 로그인만 테스트
python main.py login
```

### 배치 업로드 오류
```
ERROR: 전표가 중간에 끊김
→ 프로그램 버그 가능성, 이슈 등록 필요

ERROR: 300건 초과
→ 정상 동작, 자동으로 분할되어야 함
```

---

## 🚀 쿠팡 로켓그로스 처리 가이드

### 개요
이지어드민에서는 쿠팡 로켓그로스 판매 건이 보이지 않기 때문에, 별도 DB(`sales.sales_report_coupang_2p`)에서 판매 데이터를 직접 조회하여 처리합니다.

### 워크플로우
```
1. sales DB에서 날짜별 판매 데이터 조회
   ↓
2. 쿠팡 옵션명 → 스탠다드 상품 매핑 확인
   ├─ DB에 매핑 있음 → 바로 사용 ✅
   └─ DB에 매핑 없음 → GPT 자동 매칭
       ├─ 신뢰도 ≥ 70% → 자동 저장 ✅
       └─ 신뢰도 < 70% → 수동 매핑 필요 ⚠️
   ↓
3. 실제 판매수량 계산
   실제수량 = 주문수량 × 수량배수
   ↓
4. 이카운트 형식 변환 (판매/매입/매입전표)
   ↓
5. 이카운트 API 업로드
```

### 사용 방법

#### 1. 쿠팡 데이터 처리 및 업로드
```bash
# 날짜 지정하여 실행
python main.py coupang 2025-01-15

# 또는 대화형으로
python main.py coupang
# → "처리할 날짜를 입력하세요 (YYYY-MM-DD):" 프롬프트
```

#### 2. 스탠다드 상품 목록 등록
```python
from coupang_product_mapping import CoupangProductMappingDB

with CoupangProductMappingDB() as db:
    # 스탠다드 상품 추가
    db.add_standard_product("닥터시드 비타민C 1000mg", "닥터시드")
    db.add_standard_product("딸로 컬러케어 샴푸 500ml", "딸로")
    db.add_standard_product("테르스 오메가3", "테르스")
```

#### 3. 수동 매핑 추가 (GPT 실패 시)
```python
from coupang_product_mapping import CoupangProductMappingDB

with CoupangProductMappingDB() as db:
    db.add_mapping(
        coupang_option_name="닥터시드 비타민C 3개입",
        standard_product_name="닥터시드 비타민C 1000mg",
        quantity_multiplier=3,  # 3개 묶음
        brand="닥터시드"
    )

    db.add_mapping(
        coupang_option_name="딸로 샴푸 5+1 기획세트",
        standard_product_name="딸로 컬러케어 샴푸 500ml",
        quantity_multiplier=6,  # 5+1 = 6개
        brand="딸로"
    )
```

#### 4. 매핑 목록 조회
```python
from coupang_product_mapping import CoupangProductMappingDB

with CoupangProductMappingDB() as db:
    # 모든 매핑 조회
    mappings = db.get_all_mappings()
    for m in mappings:
        print(f"{m['coupang_option_name']} → {m['standard_product_name']} (x{m['quantity_multiplier']})")

    # 특정 매핑 조회
    mapping = db.get_mapping("닥터시드 비타민C 3개입")
    if mapping:
        print(f"상품: {mapping['standard_product_name']}")
        print(f"배수: {mapping['quantity_multiplier']}")
        print(f"브랜드: {mapping['brand']}")
```

### 데이터베이스 스키마

#### standard_products (스탠다드 상품 목록)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INT | AUTO_INCREMENT PRIMARY KEY |
| product_name | VARCHAR(500) | 이지어드민 스탠다드 상품명 (UNIQUE) |
| brand | VARCHAR(100) | 브랜드 (닥터시드/딸로/테르스/에이더) |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

#### coupang_product_mapping (쿠팡-이지어드민 매핑)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INT | AUTO_INCREMENT PRIMARY KEY |
| coupang_option_name | VARCHAR(500) | 쿠팡 옵션명 (UNIQUE) |
| standard_product_name | VARCHAR(500) | 이지어드민 스탠다드 상품명 |
| quantity_multiplier | INT | 수량 배수 (N개 묶음) |
| brand | VARCHAR(100) | 브랜드 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

### GPT 자동 매칭 동작 방식
1. 쿠팡 옵션명 분석
2. 스탠다드 상품 목록과 비교
3. 가장 유사한 상품 찾기
4. 수량 배수 자동 계산 (예: "3개입" → 3, "5+1" → 6)
5. 브랜드 자동 인식
6. 신뢰도 계산 (0.0 ~ 1.0)
7. 신뢰도 ≥ 70% → 자동 저장, < 70% → 수동 매핑 필요

### 수량 배수 처리 예시
```
쿠팡 옵션: "비타민C 1000mg 3개입"
주문수량: 2개
수량배수: 3

→ 실제 판매수량 = 2 × 3 = 6개
→ 이카운트: "비타민C 1000mg" 6개 판매로 기록
```

### rates.yml 설정
```yaml
닥터시드_국내:
  로켓그로스:
    shipping: 0.13    # 운송료 13%
    commission: 0.06  # 수수료 6%

딸로_국내:
  로켓그로스:
    shipping: 0.13
    commission: 0.06

테르스_국내:
  로켓그로스:
    shipping: 0.13
    commission: 0.06

에이더_국내:
  로켓그로스:
    shipping: 0.13
    commission: 0.06
```

### 생성되는 파일
- `output_coupang_rocketgrowth.xlsx`: 변환된 데이터
  - 판매 시트: 로켓그로스 판매 데이터
  - 매입 시트: 로켓그로스 매입 데이터
  - 매입전표 시트: 수수료/운송료

### 고정값
쿠팡 로켓그로스 데이터는 다음 값으로 고정됩니다:
- **거래처명**: 로켓그로스
- **판매채널**: 로켓그로스
- **판매유형**: 로켓그로스
- **프로젝트**: {브랜드}_국내 (예: 닥터시드_국내)
- **창고**: 200

---

## 📝 라이선스

This project is for internal use only.

---

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.

---

## 📌 버전 히스토리

### v1.4.0 (Latest) 🆕
- ✨ 쿠팡 로켓그로스 판매 데이터 처리
- ✨ 상품 매핑 DB 자동 생성 (standard_products, coupang_product_mapping)
- ✨ GPT 기반 상품 자동 매칭 (신뢰도 70% 이상)
- ✨ 수량 배수 처리 (N개 묶음 상품 자동 계산)
- ✨ sales DB에서 직접 조회 (sales.sales_report_coupang_2p)
- 🐛 판매유형/판매채널 필드도 스탠다드 이름으로 업데이트
- 🐛 날짜 형식 수정 (YYYYMMDD, datetime.date 처리)

### v1.3.0
- ✨ 매핑 완료 후 자동 재검증 및 업로드 (프로그램 재시작 불필요)
- ✨ 배치 자동 분할 (이카운트 API 300건 제한 대응)
- ✨ 전표번호에 날짜 추가 (일자+브랜드+판매채널)
- ✨ 타사 재고 채움 판매처 매출 0원 처리
- ✨ 전용수동발주 에이더 자동 제외
- 🐛 코드10 검사 순서 수정 (제외 필터 후 검사)

### v1.2.0
- GPT 기반 오타 교정
- 웹 에디터 통합
- 수동발주 케이스 검증

### v1.1.0
- MySQL 판매처 매핑 DB
- 브랜드 자동 추출 (브라이즈/에이더)
- 매입전표 자동 생성

### v1.0.0
- 이지어드민 to 이카운트 기본 변환
- Ecount API 연동
