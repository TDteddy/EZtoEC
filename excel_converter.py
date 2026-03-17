"""
본 프로그램은 이지어드민에서 다운로드한 보고서 양식을
이카운트 판매·매입·매입전표(운송료/판매수수료) 입력 양식으로 변환해주는 스크립트입니다.

- data/ 폴더의 .xlsx/.xls 파일들을 읽어 하나의 결과를 만듭니다.
- '로켓그로스' 또는 '전용수동발주 에이더'가 판매처에 포함된 행은 제외합니다.
- 결과는 DataFrame으로 반환됩니다:
  1) '판매_데이터'
  2) '구매_데이터'
  3) '매입_데이터_운반비+수수료'
- 매입전표 계산에 쓰는 프로젝트×부서 요율은 rates.yml에서 읽습니다.
- 판매처 이름은 seller_mapping.db를 통해 정규화됩니다.
"""

import os
import re
import math
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import yaml
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 판매처 매핑 DB import
try:
    from seller_mapping import SellerMappingDB
    SELLER_MAPPING_AVAILABLE = True
except ImportError:
    SELLER_MAPPING_AVAILABLE = False
    print("[WARN] seller_mapping.py를 찾을 수 없습니다. 판매처 이름 정규화가 비활성화됩니다.")

# ===== 타사 재고 채움 처리 (매출 0원 처리 대상) =====
# 타사에 재고를 채워준 경우, 물건은 나갔지만 매출은 0으로 처리해야 함
# 코드10에 다음 판매처가 있으면 매출 금액을 모두 0으로 변경
ZERO_SALES_PARTNERS = [
    "성원글로벌",
    "에이원비앤에이치",
    "글로벌엠지코리아",
    # 추가 판매처는 여기에 추가하세요
]

# ===== 설정 =====
DATA_DIR = "./data"
RATES_YAML = "rates.yml"
BRAND_KEYWORDS = ["딸로", "닥터시드", "테르스", "에이더"]
FIXED_WAREHOUSE_CODE = "200"


# ===== 유틸 =====
def to_str(x: object) -> str:
    """NaN/None/비문자값을 안전하게 문자열로 변환"""
    if isinstance(x, str):
        return x
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else str(x)


def to_int_series(series: pd.Series) -> pd.Series:
    """문자열 숫자(콤마/원화기호/공백 등 제거) → int 시리즈로 변환"""
    cleaned = series.map(to_str).str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").fillna(0).astype(int)


def convert_xls_to_xlsx(xls_path: str) -> str:
    """ .xls → .xlsx 임시 변환 (xlrd 필요) """
    try:
        df = pd.read_excel(xls_path, dtype=str, engine="xlrd")
    except Exception as e:
        raise RuntimeError(f".xls 읽기 실패: xlrd 설치 필요하거나 파일 손상 가능 — {e}")
    tmp_path = Path(tempfile.gettempdir()) / (Path(xls_path).stem + ".xlsx")
    df.to_excel(tmp_path, index=False)
    return str(tmp_path)


def read_excel_auto(path: str) -> pd.DataFrame:
    """확장자에 따라 안전하게 읽기"""
    ext = Path(path).suffix.lower()
    if ext == ".xls":
        xlsx_path = convert_xls_to_xlsx(path)
        return pd.read_excel(xlsx_path, dtype=str)
    return pd.read_excel(path, dtype=str)


def extract_brand(seller_name: str, product_name: str) -> str:
    """
    판매처와 상품명으로부터 브랜드(프로젝트) 추출

    - 일반적으로 판매처 이름의 첫 단어를 브랜드로 사용
    - 브라이즈 판매처의 경우 상품명에서 브랜드 키워드 검색
    - 에이더의 경우: 상품명이 "5자리 알파벳 + 2자리 숫자"로 시작하면 에이더로 인식
    """
    seller_name = to_str(seller_name).strip()
    product_name = to_str(product_name).strip()
    base = seller_name.split(" ")[0] if seller_name else ""
    brand = base.split("(")[0] if base else ""

    if brand == "브라이즈":
        # 1. 먼저 일반 키워드로 매칭 시도
        for kw in BRAND_KEYWORDS:
            if kw and kw in product_name:
                brand = kw
                break

        # 2. 키워드 매칭 실패 시 에이더 정규식 패턴 체크
        if brand == "브라이즈":
            # 에이더 패턴: 5자리 알파벳 + 2자리 숫자로 시작
            aider_pattern = re.compile(r'^[A-Za-z]{5}\d{2}')
            if aider_pattern.match(product_name):
                brand = "에이더"

    return brand if brand else "브랜드미상"


def safe_filename(name: str, maxlen: int = 80) -> str:
    """파일명에 쓰기 안전한 문자열로 변환"""
    s = to_str(name).strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w\-_.가-힣]", "", s)
    return (s or "unknown")[:maxlen]


# ===== YAML 로더 =====
def sync_rates_from_db(yaml_path: str = RATES_YAML) -> bool:
    """
    DB에서 요율 정보를 가져와서 rates.yml 파일을 업데이트

    Args:
        yaml_path: 저장할 YAML 파일 경로

    Returns:
        성공 여부
    """
    try:
        # DB 연결
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database="marketplace_rates"
        )
        cursor = conn.cursor(dictionary=True)

        # 요율 데이터 조회
        cursor.execute("""
            SELECT brand, marketplace, shipping, commission
            FROM marketplace_rates
            ORDER BY brand, marketplace
        """)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not rows:
            print("⚠️  DB에 요율 데이터가 없습니다.")
            return False

        # YAML 구조 생성
        rate_data = {}
        for row in rows:
            brand = row['brand']
            marketplace = row['marketplace']
            shipping = float(row['shipping'])
            commission = float(row['commission'])

            if brand not in rate_data:
                rate_data[brand] = {}

            rate_data[brand][marketplace] = {
                'shipping': shipping,
                'commission': commission
            }

        # YAML 파일 저장
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(rate_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        print(f"✅ DB에서 요율 정보를 가져와 {yaml_path} 파일을 업데이트했습니다. ({len(rows)}건)")
        return True

    except Error as e:
        print(f"❌ DB 연결 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 요율 동기화 실패: {e}")
        return False


def load_rate_book_from_yaml(path: str) -> dict:
    """
    YAML 구조 예:
    닥터시드_국내:
      스마트스토어: { shipping: 0.13, commission: 0.06 }
      카페24: { shipping: 0.09, commission: 0.055 }
    """
    if not os.path.exists(path):
        print(f"[WARN] 요율 파일이 없습니다: {path} — 모든 요율 0으로 처리됩니다.")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    rate_book = {}
    for proj, client_map in raw.items():
        if not isinstance(client_map, dict):
            print(f"[WARN] '{proj}' 값이 매핑 형태가 아닙니다. 무시.")
            continue
        rate_book[proj] = {}
        for client, rates in client_map.items():
            if not isinstance(rates, dict):
                print(f"[WARN] '{proj}/{client}' 값이 매핑 형태가 아닙니다. 무시.")
                continue
            comm = rates.get("commission", 0.0)
            ship = rates.get("shipping", 0.0)
            try:
                comm = float(comm)
            except (TypeError, ValueError):
                comm = 0.0
            try:
                ship = float(ship)
            except (TypeError, ValueError):
                ship = 0.0
            rate_book[proj][client] = {"commission": comm, "shipping": ship}
    return rate_book


# ===== 핵심 변환 =====
def validate_and_correct_sellers(df: pd.DataFrame, pending_mappings: List[Dict] = None) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    판매처 이름 검증 및 교정 (수동발주 케이스 전용)

    Args:
        df: 변환된 DataFrame (거래처명 컬럼 포함)
        pending_mappings: 기존 정제 불가 목록 (선택)

    Returns:
        (교정된 DataFrame, 정제 불가 데이터 리스트)
    """
    if pending_mappings is None:
        pending_mappings = []

    if not SELLER_MAPPING_AVAILABLE:
        print("[WARN] seller_mapping을 사용할 수 없습니다. 검증을 건너뜁니다.")
        return df, pending_mappings

    # 수동발주 케이스 필터링
    is_manual = df.apply(lambda row: "수동발주" in to_str(row.get("판매처", "")), axis=1)
    manual_df = df[is_manual].copy()

    if manual_df.empty:
        return df, pending_mappings

    print(f"\n[검증] 수동발주 데이터 {len(manual_df)}건 검증 중...")

    with SellerMappingDB() as db:
        all_standard_names = set(db.get_all_standard_names())

        # GPT 호출 결과 캐시 (중복 호출 방지)
        gpt_cache = {}

        # 1단계: 고유한 판매처명 수집 및 분류
        unique_sellers = {}  # {판매처명: [row_index 리스트]}

        for idx, row in manual_df.iterrows():
            seller_name = to_str(row.get("거래처명", "")).strip()

            # 빈 값은 이미 process_file에서 걸러졌으므로 여기서는 체크 안함
            if seller_name and seller_name not in all_standard_names and not db.get_standard_name(seller_name):
                # DB에 없는 경우만 수집
                if seller_name not in unique_sellers:
                    unique_sellers[seller_name] = []
                unique_sellers[seller_name].append(idx)

        # 2단계: DB 매칭 확인 및 DataFrame 업데이트
        for idx, row in manual_df.iterrows():
            seller_name = to_str(row.get("거래처명", "")).strip()
            if seller_name:
                # DB에서 스탠다드 이름 조회
                if seller_name in all_standard_names:
                    # 이미 스탠다드 이름인 경우
                    standard_name = seller_name
                    print(f"  ✅ [{idx}] {seller_name} - DB 매칭 (스탠다드 이름)")
                else:
                    # 별칭인 경우 스탠다드 이름으로 변환
                    standard_name = db.get_standard_name(seller_name)
                    if standard_name:
                        print(f"  ✅ [{idx}] {seller_name} → {standard_name} - DB 매칭")
                        # DataFrame 업데이트 (거래처명, 판매유형, 판매채널)
                        df.at[idx, "거래처명"] = standard_name
                        if "판매유형" in df.columns:
                            df.at[idx, "판매유형"] = standard_name
                        if "판매채널" in df.columns:
                            df.at[idx, "판매채널"] = standard_name

        # 3단계: 고유 판매처에 대해서만 GPT 호출 (중복 제거)
        print(f"\n[GPT 교정] 고유 판매처 {len(unique_sellers)}건 검증 중...")

        for seller_name, indices in unique_sellers.items():
            # 첫 번째 인덱스만 로그에 표시
            first_idx = indices[0]
            print(f"  🤖 {seller_name} ({len(indices)}건) - GPT 교정 시도 중...")

            gpt_result = db.find_similar_with_gpt(seller_name, threshold=0.7)
            gpt_cache[seller_name] = gpt_result

            if gpt_result:
                if gpt_result.get("requires_manual"):
                    # 수동 매핑 필요
                    confidence = gpt_result.get("confidence", 0)
                    print(f"  ⚠️  {seller_name} - 수동 매핑 필요 (신뢰도: {confidence:.0%})")

                    # 모든 인덱스에 대해 pending_mappings에 추가
                    for idx in indices:
                        # 원본 행 데이터 추출 (웹 에디터에서 표시용)
                        row_data = df.loc[idx]
                        order_info = {
                            "주문번호": to_str(row_data.get("주문번호", "")),
                            "품목명": to_str(row_data.get("품목명", "")),
                            "수량": to_str(row_data.get("수량", "")),
                            "일자": to_str(row_data.get("일자", "")),
                            "브랜드": to_str(row_data.get("브랜드", ""))
                        }

                        pending_mappings.append({
                            "original": seller_name,
                            "gpt_suggestion": gpt_result.get("matched"),
                            "confidence": confidence,
                            "reason": gpt_result.get("reason", ""),
                            "row_index": idx,
                            "order_info": order_info  # 원본 주문 정보 추가
                        })
                else:
                    # 자동 교정 성공
                    matched = gpt_result.get("matched")
                    confidence = gpt_result.get("confidence", 0)
                    print(f"  ✅ {seller_name} → {matched} (신뢰도: {confidence:.0%})")

                    # 모든 해당 행의 DataFrame 업데이트 (거래처명, 판매유형, 판매채널)
                    for idx in indices:
                        df.at[idx, "거래처명"] = matched
                        if "판매유형" in df.columns:
                            df.at[idx, "판매유형"] = matched
                        if "판매채널" in df.columns:
                            df.at[idx, "판매채널"] = matched

                    # DB에 자동으로 매핑 추가 (한 번만)
                    db.add_mapping(seller_name, matched)
            else:
                # GPT 실패
                print(f"  ❌ {seller_name} - GPT 매칭 실패")

                # 모든 인덱스에 대해 pending_mappings에 추가
                for idx in indices:
                    # 원본 행 데이터 추출 (웹 에디터에서 표시용)
                    row_data = df.loc[idx]
                    order_info = {
                        "주문번호": to_str(row_data.get("주문번호", "")),
                        "품목명": to_str(row_data.get("품목명", "")),
                        "수량": to_str(row_data.get("수량", "")),
                        "일자": to_str(row_data.get("일자", "")),
                        "브랜드": to_str(row_data.get("브랜드", ""))
                    }

                    pending_mappings.append({
                        "original": seller_name,
                        "gpt_suggestion": None,
                        "confidence": 0.0,
                        "reason": "GPT 매칭 실패",
                        "row_index": idx,
                        "order_info": order_info  # 원본 주문 정보 추가
                    })

    unique_pending = len(set(p["original"] for p in pending_mappings))
    if pending_mappings:
        print(f"\n⚠️  수동 매핑 필요: {unique_pending}개 고유 판매처 (총 {len(pending_mappings)}건)")
    else:
        print(f"\n✅ 모든 데이터 검증 완료")

    return df, pending_mappings


def process_file(file_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    이지어드민 엑셀 파일을 읽어서 판매/매입 DataFrame으로 변환

    Returns:
        (sales_df, purchase_df): 판매 및 매입 DataFrame
    """
    try:
        df = read_excel_auto(file_path)

        # 0) 합계/총합계 행 제거
        total_mask = df.astype(str).apply(
            lambda col: col.str.replace(r"\s+", "", regex=True).str.fullmatch(r"(합계|총합계)"),
        ).any(axis=1)
        df = df[~total_mask].copy()

        # 1) 컬럼명 정규화
        df.columns = (
            pd.Series(df.columns)
              .map(to_str)
              .map(lambda c: " ".join(c.split()))
              .map(str.strip)
        )

        # 2) 필요한 핵심 컬럼 보강
        required_cols = [
            "주문일", "발주일", "판매처", "코드10", "판매처 상품명",
            "주문상세번호", "상품코드", "상품명", "옵션명",
            "주문수량", "판매가", "상품원가",
            "송장번호", "수령자주소", "수령자이름", "수령자전화", "수령자휴대폰", "배송메모"
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # 3) 셀 값 정리
        df = df.apply(lambda col: col.map(lambda x: None if (isinstance(x, str) and x.strip() == "") else x))

        # 4) 판매처에 '로켓그로스' 또는 '전용수동발주 에이더' 포함 시 제외
        df = df[~df["판매처"].map(to_str).str.contains("로켓그로스", na=False)].copy()
        df = df[~df["판매처"].map(to_str).str.contains("전용수동발주 에이더", na=False)].copy()

        # 5) CS 컬럼에 '전체 취소' 포함 시 제외
        if "CS" in df.columns:
            before_count = len(df)
            df = df[~df["CS"].map(to_str).str.contains("전체 취소", na=False)].copy()
            removed_count = before_count - len(df)
            if removed_count > 0:
                print(f"  ℹ️  CS '전체 취소' 건 제외: {removed_count}건")

        # 6) 수동발주 케이스의 코드10 빈 값 검사 (로켓그로스/에이더 제외 후 실행)
        manual_order_mask = df["판매처"].astype(str).str.contains("수동발주", na=False)
        manual_orders = df[manual_order_mask].copy()

        if not manual_orders.empty:
            # 코드10이 비어있는 행 찾기
            empty_code10_mask = manual_orders["코드10"].isna() | (manual_orders["코드10"].astype(str).str.strip() == "")
            empty_code10_rows = manual_orders[empty_code10_mask]

            if not empty_code10_rows.empty:
                print("\n" + "=" * 80)
                print("❌ [치명적 오류] 수동발주 케이스에 코드10이 비어있는 데이터 발견!")
                print("=" * 80)
                print(f"\n수동발주는 코드10 필드에 판매처 정보가 반드시 입력되어야 합니다.")
                print(f"발견된 빈 값: {len(empty_code10_rows)}건\n")

                # 빈 값이 있는 행의 상세 정보 출력 (최대 10개)
                print("빈 값이 발견된 주문 정보:")
                print("-" * 80)
                for idx, (row_idx, row) in enumerate(empty_code10_rows.iterrows(), 1):
                    if idx > 10:
                        print(f"... 외 {len(empty_code10_rows) - 10}건 더 있음")
                        break

                    주문번호 = to_str(row.get("주문상세번호", ""))
                    품목명 = to_str(row.get("상품명", ""))
                    판매처 = to_str(row.get("판매처", ""))
                    주문일 = to_str(row.get("주문일", ""))

                    print(f"{idx}. 행번호: {row_idx + 2}")  # Excel 행번호 (헤더 1 + 0-based index)
                    if 주문번호:
                        print(f"   주문번호: {주문번호}")
                    if 품목명:
                        print(f"   품목명: {품목명}")
                    if 판매처:
                        print(f"   판매처: {판매처}")
                    if 주문일:
                        print(f"   주문일: {주문일}")
                    print()

                print("=" * 80)
                print("⚠️  조치 방법:")
                print("1. 원본 Excel 파일을 열어주세요")
                print(f"2. 위에 표시된 행의 '코드10' 컬럼에 판매처 이름을 입력하세요")
                print("3. 파일을 저장한 후 프로그램을 다시 실행하세요")
                print("=" * 80)

                raise ValueError(
                    f"수동발주 케이스에 코드10이 비어있는 데이터가 {len(empty_code10_rows)}건 발견되었습니다. "
                    f"원본 Excel 파일의 코드10 컬럼을 먼저 채워주세요."
                )

        # 6) 일자: 주문일 우선, 없으면 발주일
        order_dt = pd.to_datetime(df["주문일"], errors="coerce")
        po_dt = pd.to_datetime(df["발주일"], errors="coerce")
        df["일자"] = order_dt.fillna(po_dt).dt.date

        # 일자 분포 확인 (디버깅용)
        date_counts = df["일자"].value_counts().sort_index()
        if len(date_counts) > 0:
            print(f"\n  📅 일자 분포:")
            for date_val, count in date_counts.items():
                print(f"     {date_val}: {count}건")
            print()

        # 7) 공통 필드
        df["순번"] = ""
        df["판매No."] = ""
        df["거래처코드"] = ""

        # 판매처 이름 추출 및 정규화 (DB 연결은 한 번만)
        def extract_partner_names(df_input):
            """
            판매처 이름 추출 및 정규화

            - 수동발주 케이스: 코드10 값을 그대로 사용 (DB normalization 제외)
              → validate_and_correct_sellers()에서 전담 처리
            - 기타 케이스: 추출 후 DB normalization 적용
            """
            names = []
            is_manual_orders = []  # 수동발주 여부 플래그

            for _, row in df_input.iterrows():
                seller = to_str(row.get("판매처"))
                code2 = to_str(row.get("코드10"))

                # 수동발주 여부 확인
                is_manual = "수동발주" in seller
                is_manual_orders.append(is_manual)

                # 기존 로직
                if is_manual:
                    result = code2  # 코드10 값 그대로 (검증은 나중에)
                elif "(" in seller and ")" in seller:
                    try:
                        result = seller.split("(")[1].split(")")[0]
                    except Exception:
                        result = seller
                else:
                    result = seller

                names.append(result)

            # DB 정규화 (수동발주가 아닌 케이스만)
            if SELLER_MAPPING_AVAILABLE:
                try:
                    with SellerMappingDB() as db:
                        normalized_names = []
                        for i, name in enumerate(names):
                            if is_manual_orders[i]:
                                # 수동발주는 validate_and_correct_sellers에서 처리
                                normalized_names.append(name)
                            else:
                                # 수동발주가 아닌 경우만 DB normalization
                                normalized_names.append(db.normalize_name(name))
                        names = normalized_names
                except Exception:
                    pass  # 에러 발생 시 원본 그대로 사용

            return names

        df["거래처명"] = extract_partner_names(df)

        def _project(row):
            seller = to_str(row.get("판매처"))
            prod_name = to_str(row.get("상품명"))
            brand = extract_brand(seller, prod_name)
            dom_over = "해외" if "해외" in seller else "국내"
            return f"{brand}_{dom_over}"

        df["프로젝트"] = df.apply(_project, axis=1)
        df["판매유형"] = df["거래처명"]

        # 7) 주문번호 추출
        cand_cols = [c for c in df.columns if c == "주문상세번호" or c.startswith("주문상세번호")]
        if len(cand_cols) >= 2:
            order_detail_second_col = cand_cols[1]
        elif "주문상세번호.1" in df.columns:
            order_detail_second_col = "주문상세번호.1"
        elif "주문상세번호_2" in df.columns:
            order_detail_second_col = "주문상세번호_2"
        else:
            order_detail_second_col = "주문상세번호"
        df["주문번호"] = df[order_detail_second_col]

        # 8) 수량/금액
        df["수량"] = to_int_series(df.get("주문수량"))

        # ===== 판매 시트 구성 =====
        df["단가(vat포함)"] = to_int_series(df.get("판매가"))
        supply_sales = (df["단가(vat포함)"] / 11 * 10).astype(int)
        vat_sales = (df["단가(vat포함)"] / 11).astype(int)

        sales = pd.DataFrame({
            "일자": df["일자"],
            "순번": df["순번"],
            "브랜드": df["프로젝트"],
            "판매채널": df["판매유형"],
            "거래처코드": df["거래처코드"],
            "거래처명": df["거래처명"],
            "출하창고": FIXED_WAREHOUSE_CODE,
            "통화": "",
            "환율": "",
            "주문번호": df["주문번호"],
            "상품코드": "",
            "품목명": df.get("상품명"),
            "옵션": df.get("옵션명"),
            "규격": "",
            "수량": df["수량"],
            "단가(vat포함)": df["단가(vat포함)"],
            "단가": "",
            "외화금액": "",
            "공급가액": supply_sales,
            "부가세": vat_sales,
            "송장번호": df.get("송장번호"),
            "수령자주소": df.get("수령자주소"),
            "수령자이름": df.get("수령자이름"),
            "수령자전화": df.get("수령자전화"),
            "수령자휴대폰": df.get("수령자휴대폰"),
            "배송메모": df.get("배송메모"),
            "주문상세번호": df.get("주문상세번호"),
            "생산전표생성": "",
            "판매처": df.get("판매처")  # 원본 판매처 컬럼 보존 (검증용)
        })

        sales_cols = [
            "일자", "순번", "브랜드", "판매채널", "거래처코드", "거래처명", "출하창고",
            "통화", "환율", "주문번호", "상품코드", "품목명", "옵션", "규격", "수량",
            "단가(vat포함)", "단가", "외화금액", "공급가액", "부가세", "송장번호",
            "수령자주소", "수령자이름", "수령자전화", "수령자휴대폰", "배송메모",
            "주문상세번호", "생산전표생성", "판매처"
        ]
        sales = sales[sales_cols]

        # ===== 타사 재고 채움 처리: 매출 0원 처리 =====
        # 코드10에 특정 판매처가 있으면 매출 금액을 0으로 변경 (재고는 나가지만 매출은 없음)
        zero_sales_mask = sales["거래처명"].isin(ZERO_SALES_PARTNERS)
        if zero_sales_mask.any():
            affected_count = zero_sales_mask.sum()
            affected_partners = sales.loc[zero_sales_mask, "거래처명"].unique()
            print(f"[INFO] 타사 재고 채움 처리: {affected_count}건 (판매처: {', '.join(affected_partners)})")
            print(f"       → 매출 금액을 0으로 변경 (물건은 나가지만 매출 없음)")

            # 금액 관련 컬럼을 모두 0으로 변경
            sales.loc[zero_sales_mask, "단가(vat포함)"] = 0
            sales.loc[zero_sales_mask, "단가"] = 0
            sales.loc[zero_sales_mask, "공급가액"] = 0
            sales.loc[zero_sales_mask, "부가세"] = 0
            sales.loc[zero_sales_mask, "외화금액"] = ""

        # ===== 매입 시트 구성 =====
        cost = to_int_series(df.get("상품원가"))
        cost = cost * df["수량"]
        supply_cost = (cost / 11 * 10).astype(int)
        vat_cost = (cost / 11).astype(int)

        purchase = pd.DataFrame({
            "일자": df["일자"],
            "순번": "",
            "브랜드": df["프로젝트"],
            "판매채널": df["거래처명"],
            "거래처코드": "",
            "거래처명": df["거래처명"],
            "입고창고": FIXED_WAREHOUSE_CODE,
            "통화": "",
            "환율": "",
            "품목코드": "",
            "품목명": df.get("상품명"),
            "규격명": "",
            "수량": df["수량"],
            "단가": cost,
            "외화금액": "",
            "공급가액": supply_cost,
            "부가세": vat_cost,
            "적요": df["프로젝트"] + " " + df["거래처명"],
            "판매처": df.get("판매처")  # 원본 판매처 컬럼 보존 (검증용)
        })

        purchase_cols = [
            "일자", "순번", "브랜드", "판매채널", "거래처코드", "거래처명", "입고창고",
            "통화", "환율", "품목코드", "품목명", "규격명", "수량", "단가",
            "외화금액", "공급가액", "부가세", "적요", "판매처"
        ]
        purchase = purchase[purchase_cols]

        return sales, purchase

    except ValueError as e:
        # ValueError는 사용자 데이터 문제 (코드10 빈 값 등)
        # 상위로 전파하여 프로그램 중단
        raise
    except Exception as e:
        print(f"❌ {file_path}: 오류 발생 - {e}")
        return pd.DataFrame(), pd.DataFrame()


# ===== 매출전표 생성 =====
def build_sales_voucher(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    sales_df를 (월, 브랜드, 판매채널, 거래처명)으로 묶고,
    공급가액과 부가세를 합산하여 매출전표 생성

    Args:
        sales_df: 판매 DataFrame

    Returns:
        매출전표 DataFrame
    """
    if sales_df.empty:
        return pd.DataFrame()

    need_cols = ["일자", "브랜드", "판매채널", "거래처명", "공급가액", "부가세"]
    for c in need_cols:
        if c not in sales_df.columns:
            raise KeyError(f"매출전표 생성에 필요한 컬럼이 없습니다: {c}")

    # 월 추출 (YYYY-MM 형식)
    temp_df = sales_df[need_cols].copy()
    temp_df["월"] = pd.to_datetime(temp_df["일자"]).dt.to_period('M')

    # (월, 브랜드, 판매채널, 거래처명)으로 그룹핑하여 공급가액과 부가세 합산
    # 전표일자는 해당 월의 마지막 일자 사용
    base = (
        temp_df
        .groupby(["월", "브랜드", "판매채널", "거래처명"], dropna=False, as_index=False)
        .agg({
            "일자": "max",  # 해당 월의 마지막 날짜
            "공급가액": "sum",
            "부가세": "sum"
        })
    )

    rows = []
    for _, r in base.iterrows():
        rows.append({
            "전표일자": r["일자"],
            "브랜드": to_str(r["브랜드"]),
            "판매채널": to_str(r["판매채널"]),
            "거래처코드": "",
            "거래처명": to_str(r["거래처명"]),
            "부가세유형": "",
            "공급가액": int(r["공급가액"]),
            "외화금액": "",
            "환율": "",
            "부가세": int(r["부가세"]),
            "적요": "",
            "매출계정코드": "4019",
            "입금계좌": ""
        })

    voucher = pd.DataFrame(rows, columns=[
        "전표일자", "브랜드", "판매채널", "거래처코드", "거래처명", "부가세유형",
        "공급가액", "외화금액", "환율", "부가세", "적요", "매출계정코드", "입금계좌"
    ])
    return voucher


# ===== 원가매입전표 생성 =====
def build_cost_voucher(purchase_df: pd.DataFrame) -> pd.DataFrame:
    """
    purchase_df를 (월, 브랜드, 판매채널, 거래처명)으로 묶고,
    공급가액과 부가세를 합산하여 원가매입전표 생성

    Args:
        purchase_df: 매입 DataFrame

    Returns:
        원가매입전표 DataFrame
    """
    if purchase_df.empty:
        return pd.DataFrame()

    need_cols = ["일자", "브랜드", "판매채널", "거래처명", "공급가액", "부가세"]
    for c in need_cols:
        if c not in purchase_df.columns:
            raise KeyError(f"원가매입전표 생성에 필요한 컬럼이 없습니다: {c}")

    # 월 추출 (YYYY-MM 형식)
    temp_df = purchase_df[need_cols].copy()
    temp_df["월"] = pd.to_datetime(temp_df["일자"]).dt.to_period('M')

    # (월, 브랜드, 판매채널, 거래처명)으로 그룹핑하여 공급가액과 부가세 합산
    # 전표일자는 해당 월의 마지막 일자 사용
    base = (
        temp_df
        .groupby(["월", "브랜드", "판매채널", "거래처명"], dropna=False, as_index=False)
        .agg({
            "일자": "max",  # 해당 월의 마지막 날짜
            "공급가액": "sum",
            "부가세": "sum"
        })
    )

    rows = []
    for _, r in base.iterrows():
        rows.append({
            "전표일자": r["일자"],
            "브랜드": to_str(r["브랜드"]),
            "판매채널": to_str(r["판매채널"]),
            "거래처코드": "",
            "거래처명": to_str(r["거래처명"]),
            "부가세유형": "",
            "신용카드/승인번호": "",
            "공급가액": int(r["공급가액"]),
            "외화금액": "",
            "환율": "",
            "부가세": int(r["부가세"]),
            "적요": "",
            "매입계정코드": "4519",
            "돈나간계좌번호": "",
            "채무번호": "",
            "만기일자": ""
        })

    voucher = pd.DataFrame(rows, columns=[
        "전표일자", "브랜드", "판매채널", "거래처코드", "거래처명", "부가세유형",
        "신용카드/승인번호", "공급가액", "외화금액", "환율", "부가세", "적요",
        "매입계정코드", "돈나간계좌번호", "채무번호", "만기일자"
    ])
    return voucher


# ===== 매입전표(운송료/판매수수료) 생성 =====
def build_voucher_from_sales(sales_df: pd.DataFrame, rate_book: dict) -> pd.DataFrame:
    """
    sales_df를 (일자, 프로젝트, 거래처명)으로 묶고,
    각 그룹의 '단가(vat포함)' 합계에 YAML의 shipping/commission 요율을 적용해 전표 2줄씩 생성.
    """
    if sales_df.empty:
        return pd.DataFrame()

    need_cols = ["일자", "브랜드", "거래처명", "단가(vat포함)"]
    for c in need_cols:
        if c not in sales_df.columns:
            raise KeyError(f"매입전표 생성에 필요한 컬럼이 없습니다: {c}")

    base = (
        sales_df[need_cols]
        .groupby(["일자", "브랜드", "거래처명"], dropna=False, as_index=False)["단가(vat포함)"]
        .sum()
        .rename(columns={"단가(vat포함)": "합계단가_VAT포함"})
    )

    rows = []
    for _, r in base.iterrows():
        day = r["일자"]
        proj = to_str(r["브랜드"])
        dept = to_str(r["거래처명"])
        total = int(r["합계단가_VAT포함"])

        rates = rate_book.get(proj, {}).get(dept, {"shipping": 0.0, "commission": 0.0})
        ship_rate = float(rates.get("shipping", 0.0))
        comm_rate = float(rates.get("commission", 0.0))

        def mk_row(rate: float, account_code: str):
            amount = total * rate
            supply = int(amount / 11 * 10)
            vat = int(amount / 11)
            return {
                "전표일자": day,
                "브랜드": proj,
                "판매채널": dept,
                "거래처코드": "",
                "거래처명": dept,
                "부가세유형": "",
                "신용카드/승인번호": "",
                "공급가액": supply,
                "외화금액": "",
                "환율": "",
                "부가세": vat,
                "적요": "",
                "매입계정코드": account_code,
                "돈나간계좌번호": "",
                "채무번호": "",
                "만기일자": ""
            }

        if ship_rate != 0.0:
            rows.append(mk_row(ship_rate, "8019"))
        if comm_rate != 0.0:
            rows.append(mk_row(comm_rate, "8029"))

    voucher = pd.DataFrame(rows, columns=[
        "전표일자", "브랜드", "판매채널", "거래처코드", "거래처명", "부가세유형",
        "신용카드/승인번호", "공급가액", "외화금액", "환율", "부가세", "적요",
        "매입계정코드", "돈나간계좌번호", "채무번호", "만기일자"
    ])
    return voucher


# ===== 프로젝트별 분리 =====
def split_by_project(sales_df: pd.DataFrame, purchase_df: pd.DataFrame,
                     sales_voucher_df: pd.DataFrame, cost_voucher_df: pd.DataFrame,
                     fee_voucher_df: pd.DataFrame) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    프로젝트(브랜드)별로 데이터 분리

    Returns:
        {
            "브랜드명": {
                "sales": DataFrame,
                "purchase": DataFrame,
                "sales_voucher": DataFrame,  # 매출전표
                "cost_voucher": DataFrame,   # 원가매입전표
                "fee_voucher": DataFrame     # 운반비/수수료 매입전표
            },
            ...
        }
    """
    projects = set()
    if not sales_df.empty and "브랜드" in sales_df.columns:
        projects.update(sales_df["브랜드"].dropna().unique())
    if not purchase_df.empty and "브랜드" in purchase_df.columns:
        projects.update(purchase_df["브랜드"].dropna().unique())

    for df in [sales_voucher_df, cost_voucher_df, fee_voucher_df]:
        if df is not None and not df.empty and "브랜드" in df.columns:
            projects.update(df["브랜드"].dropna().unique())

    result = {}
    for proj in sorted(projects, key=to_str):
        result[proj] = {
            "sales": sales_df[sales_df["브랜드"] == proj] if not sales_df.empty else pd.DataFrame(),
            "purchase": purchase_df[purchase_df["브랜드"] == proj] if not purchase_df.empty else pd.DataFrame(),
            "sales_voucher": sales_voucher_df[sales_voucher_df["브랜드"] == proj] if (sales_voucher_df is not None and not sales_voucher_df.empty) else pd.DataFrame(),
            "cost_voucher": cost_voucher_df[cost_voucher_df["브랜드"] == proj] if (cost_voucher_df is not None and not cost_voucher_df.empty) else pd.DataFrame(),
            "fee_voucher": fee_voucher_df[fee_voucher_df["브랜드"] == proj] if (fee_voucher_df is not None and not fee_voucher_df.empty) else pd.DataFrame()
        }

    return result


# ===== 메인 처리 함수 (DataFrame 반환) =====
def process_ezadmin_to_ecount(data_dir: str = DATA_DIR,
                               rates_yaml: str = RATES_YAML,
                               validate_sellers: bool = True) -> Tuple[Dict[str, any], List[Dict]]:
    """
    이지어드민 데이터를 이카운트 양식으로 변환

    Args:
        data_dir: 이지어드민 엑셀 파일들이 있는 디렉토리
        rates_yaml: 요율 설정 YAML 파일 경로
        validate_sellers: 판매처 검증 여부 (수동발주 케이스)

    Returns:
        (
            {
                "sales": 전체 판매 DataFrame,
                "purchase": 전체 매입 DataFrame,
                "voucher": 전체 매입전표 DataFrame,
                "by_project": {브랜드: {sales, purchase, voucher}}
            },
            pending_mappings: 정제 불가 데이터 리스트
        )
    """
    os.makedirs(data_dir, exist_ok=True)
    print("[INFO] CWD:", os.getcwd())
    print("[INFO] DATA_DIR:", os.path.abspath(data_dir))

    # YAML 로드
    rate_book = load_rate_book_from_yaml(rates_yaml)

    sales_all, purchase_all = [], []
    candidates = [f for f in os.listdir(data_dir) if f.lower().endswith((".xlsx", ".xls"))]
    print("[INFO] 대상 파일:", candidates if candidates else "(없음)")

    for file in candidates:
        file_path = os.path.join(data_dir, file)
        print(f"[INFO] 처리 시작: {file_path}")
        sales_df, purchase_df = process_file(file_path)
        if not sales_df.empty:
            print(f"[INFO] 판매 OK: {len(sales_df)}건")
            sales_all.append(sales_df)
        else:
            print(f"[WARN] 판매 변환 결과가 비어있습니다: {file_path}")
        if not purchase_df.empty:
            print(f"[INFO] 매입 OK: {len(purchase_df)}건")
            purchase_all.append(purchase_df)
        else:
            print(f"[WARN] 매입 변환 결과가 비어있습니다: {file_path}")

    # 결과 병합
    sales_merged = pd.concat(sales_all, ignore_index=True) if sales_all else pd.DataFrame()
    purchase_merged = pd.concat(purchase_all, ignore_index=True) if purchase_all else pd.DataFrame()

    # 데이터 검증 및 정제 (수동발주 케이스)
    pending_mappings = []
    if validate_sellers and not sales_merged.empty:
        print("\n" + "=" * 80)
        print("데이터 검증 시작 (수동발주 케이스)")
        print("=" * 80)
        sales_merged, pending_mappings = validate_and_correct_sellers(sales_merged, pending_mappings)

        if not purchase_merged.empty:
            purchase_merged, pending_mappings = validate_and_correct_sellers(purchase_merged, pending_mappings)

    # 전표 생성
    sales_voucher_df = build_sales_voucher(sales_merged) if not sales_merged.empty else pd.DataFrame()
    cost_voucher_df = build_cost_voucher(purchase_merged) if not purchase_merged.empty else pd.DataFrame()
    fee_voucher_df = build_voucher_from_sales(sales_merged, rate_book) if not sales_merged.empty else pd.DataFrame()

    print(f"[INFO] 매출전표 생성: {len(sales_voucher_df)}건")
    print(f"[INFO] 원가매입전표 생성: {len(cost_voucher_df)}건")
    print(f"[INFO] 운반비/수수료 매입전표 생성: {len(fee_voucher_df)}건")

    # 프로젝트별 분리
    by_project = split_by_project(sales_merged, purchase_merged, sales_voucher_df, cost_voucher_df, fee_voucher_df)

    total_sales = len(sales_merged)
    total_purchase = len(purchase_merged)
    total_sales_vouchers = len(sales_voucher_df)
    total_cost_vouchers = len(cost_voucher_df)
    total_fee_vouchers = len(fee_voucher_df)
    print(f"\n✅ 처리 완료: 판매 {total_sales}건, 매입 {total_purchase}건")
    print(f"   전표: 매출 {total_sales_vouchers}건, 원가매입 {total_cost_vouchers}건, 운반비/수수료 {total_fee_vouchers}건")

    return {
        "sales": sales_merged,
        "purchase": purchase_merged,
        "sales_voucher": sales_voucher_df,
        "cost_voucher": cost_voucher_df,
        "fee_voucher": fee_voucher_df,
        "voucher": fee_voucher_df,  # 하위 호환성을 위해 유지
        "by_project": by_project
    }, pending_mappings


# ===== 파일 저장 함수 (선택적) =====
def save_to_excel(result: Dict[str, any], output_file: str = "output_ecount.xlsx"):
    """
    변환 결과를 엑셀 파일로 저장

    Args:
        result: process_ezadmin_to_ecount() 함수의 반환값
        output_file: 저장할 파일명
    """
    sales_df = result.get("sales", pd.DataFrame())
    purchase_df = result.get("purchase", pd.DataFrame())
    sales_voucher_df = result.get("sales_voucher", pd.DataFrame())
    cost_voucher_df = result.get("cost_voucher", pd.DataFrame())
    fee_voucher_df = result.get("fee_voucher", pd.DataFrame())

    if sales_df.empty and purchase_df.empty and sales_voucher_df.empty and cost_voucher_df.empty and fee_voucher_df.empty:
        print("❌ 저장할 데이터가 없습니다.")
        return

    # 통합 파일 저장
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        if not sales_df.empty:
            sales_df.to_excel(writer, index=False, sheet_name="판매")
        if not purchase_df.empty:
            purchase_df.to_excel(writer, index=False, sheet_name="매입")
        if not sales_voucher_df.empty:
            sales_voucher_df.to_excel(writer, index=False, sheet_name="매출전표")
        if not cost_voucher_df.empty:
            cost_voucher_df.to_excel(writer, index=False, sheet_name="원가매입전표")
        if not fee_voucher_df.empty:
            fee_voucher_df.to_excel(writer, index=False, sheet_name="운반비수수료전표")

    print(f"✅ {output_file}: 판매 {len(sales_df)}건, 매입 {len(purchase_df)}건")
    print(f"   전표: 매출 {len(sales_voucher_df)}건, 원가매입 {len(cost_voucher_df)}건, 운반비/수수료 {len(fee_voucher_df)}건 저장 완료")

    # 프로젝트별 파일 저장
    by_project = result.get("by_project", {})
    for proj, data in by_project.items():
        sales_empty = data.get("sales", pd.DataFrame()).empty
        purchase_empty = data.get("purchase", pd.DataFrame()).empty
        sales_voucher_empty = data.get("sales_voucher", pd.DataFrame()).empty
        cost_voucher_empty = data.get("cost_voucher", pd.DataFrame()).empty
        fee_voucher_empty = data.get("fee_voucher", pd.DataFrame()).empty

        if sales_empty and purchase_empty and sales_voucher_empty and cost_voucher_empty and fee_voucher_empty:
            continue

        fname = f"output_ecount_{safe_filename(proj)}.xlsx"
        with pd.ExcelWriter(fname, engine="openpyxl") as writer:
            if not sales_empty:
                data["sales"].to_excel(writer, index=False, sheet_name="판매")
            if not purchase_empty:
                data["purchase"].to_excel(writer, index=False, sheet_name="매입")
            if not sales_voucher_empty:
                data["sales_voucher"].to_excel(writer, index=False, sheet_name="매출전표")
            if not cost_voucher_empty:
                data["cost_voucher"].to_excel(writer, index=False, sheet_name="원가매입전표")
            if not fee_voucher_empty:
                data["fee_voucher"].to_excel(writer, index=False, sheet_name="운반비수수료전표")

        print(f"✅ 프로젝트별 저장 완료: {proj} → {fname}")


# ===== 실행부 =====
if __name__ == "__main__":
    # 데이터 처리
    result, pending_mappings = process_ezadmin_to_ecount()

    # 정제 불가 데이터가 있으면 웹 에디터 실행
    if pending_mappings:
        print("\n" + "=" * 80)
        print(f"⚠️  수동 매핑이 필요한 판매처: {len(pending_mappings)}건")
        print("=" * 80)
        for p in pending_mappings:
            print(f"  - {p['original']}")

        print("\n웹 에디터를 실행하려면 다음 명령을 사용하세요:")
        print("  python main.py")
        print("\n또는 직접 웹 에디터 실행:")
        print("  from seller_editor import start_editor")
        print("  start_editor(pending_mappings)")

    # 파일로 저장 (선택적)
    if result["sales"].empty and result["purchase"].empty and result["voucher"].empty:
        print("❌ 처리할 데이터가 없습니다.")
    else:
        save_to_excel(result)
