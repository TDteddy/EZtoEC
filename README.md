# EZtoEC
이지어드민 to 이카운트

이지어드민에서 다운로드한 보고서를 이카운트 판매/매입/매입전표 양식으로 변환하고, 자동으로 이카운트 API에 업로드하는 프로그램입니다.

## 🌟 주요 기능

### 1. **완전 자동화 워크플로우**
```
이지어드민 엑셀 → 데이터 검증 → GPT 오타 교정 → 웹 에디터 → Ecount API 업로드 → 완료
```

### 2. **지능형 데이터 검증**
- **수동발주 케이스 자동 검증**: 코드10 필드의 판매처 이름을 DB와 비교
- **GPT 기반 오타 교정**: AI가 자동으로 유사한 판매처 이름 찾기 (신뢰도 70% 이상)
- **웹 에디터 통합**: 정제 불가 데이터는 웹 UI에서 수동 매핑

### 3. **스마트 브랜드 인식**
- **브라이즈 판매처 특수 처리**: 상품명에서 브랜드 추출
- **에이더 정규식 패턴**: `5자 알파벳 + 2자 숫자`로 시작하면 자동 인식 (예: ABCDE12)
- **키워드 매칭**: 딸로, 닥터시드, 테르스 자동 인식

### 4. **전표 자동 그룹화**
- 같은 브랜드 + 판매채널 자동으로 하나의 전표로 묶음
- 전표묶음순번 자동 할당

### 5. **매입전표 자동 생성**
- rates.yml 기반 운반비/수수료 자동 계산
- 브랜드×판매채널별 요율 적용

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
│  ├─ 판매/매입 데이터 변환                                    │
│  ├─ 브랜드 자동 추출 (브라이즈/에이더 특수 처리)               │
│  ├─ 매입전표 생성 (운반비/수수료)                             │
│  └─ 수동발주 케이스 검증                                     │
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
│  └─ Enter로 계속 진행                                       │
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
│ STEP 6: Ecount API 업로드                                   │
│  ├─ 판매 데이터 업로드 (전표묶음순번 자동 할당)               │
│  └─ 구매 데이터 업로드 (전표묶음순번 자동 할당)               │
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
3. 수동 매핑 완료 후 Enter
4. Ecount 로그인 및 API 업로드
5. 엑셀 파일 생성

---

## 📖 상세 사용 방법

### 실행 모드

```bash
# 1. 완전한 워크플로우 (기본, 권장)
python main.py
# → 변환 → 검증 → (웹 에디터) → API 업로드 → 엑셀 저장

# 2. 로그인만 테스트
python main.py login
# → Ecount 로그인 테스트, SESSION_ID 확인

# 3. 엑셀 변환만 (API 업로드 제외)
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
```

### 3. 전표 자동 그룹화

같은 브랜드 + 판매채널을 하나의 전표로 묶음:

```
일자       브랜드        판매채널       전표묶음순번
2024-01-15 에이더_국내   G마켓         1
2024-01-15 에이더_국내   G마켓         1  (같은 그룹)
2024-01-15 에이더_국내   쿠팡          2  (다른 판매채널)
2024-01-15 딸로_국내     G마켓         3  (다른 브랜드)
```

### 4. 매입전표 자동 생성

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

# 4. API 업로드
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
```

---

## 📊 API 필드 매핑

### 전표 묶음 순번 (UPLOAD_SER_NO)
이카운트 API는 같은 순번을 가진 데이터를 하나의 전표로 묶어 처리합니다.

**자동 할당 규칙:**
- 같은 **브랜드(프로젝트)** + **판매채널(부서)**를 가진 데이터는 동일한 순번
- 순번은 1부터 자동 할당
- 예시:
  - 닥터시드_국내 + 스마트스토어 → 순번 1
  - 닥터시드_국내 + 카페24 → 순번 2
  - 딸로_국내 + 스마트스토어 → 순번 3

### 판매 API (SaveSale)
| 이지어드민 | 이카운트 API | 비고 |
|----------|-------------|------|
| 주문일 | IO_DATE | YYYYMMDD |
| (자동) | UPLOAD_SER_NO | 전표묶음순번 (자동 할당) |
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
| 발주일 | IO_DATE | YYYYMMDD |
| (자동) | UPLOAD_SER_NO | 전표묶음순번 (자동 할당) |
| 브랜드 | PJT_CD | 프로젝트 코드 |
| 거래처명 | SITE | 부서 |
| 거래처명 | CUST_DES | 정규화된 이름 |
| 입고창고 | WH_CD | 고정값: "200" |
| 품목명 | PROD_DES | 상품명 + 옵션 |
| 수량 | QTY | 정수 |
| 공급단가 | PRICE | VAT 별도 |

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

### MySQL
- 판매처 매핑 DB는 선택 사항이지만 **강력히 권장**
- MySQL 없이도 작동하지만 검증 단계가 건너뛰어짐
- 초기 설정 후 지속적으로 매핑 데이터 축적 필요

### GPT API
- GPT API 없이도 작동 (수동 매핑만 사용)
- 신뢰도 임계값(70%)은 `seller_mapping.py`에서 조정 가능
- GPT-4o-mini 모델 사용 (비용 효율적)

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

---

## 📝 라이선스

This project is for internal use only.

---

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.
