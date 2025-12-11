"""
쿠팡 로켓그로스 판매 데이터 처리

sales.sales_report_coupang_2p 테이블에서 판매 데이터를 조회하여
이카운트 형식으로 변환 및 업로드
"""

import mysql.connector
from mysql.connector import Error
import os
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional, Any
from dotenv import load_dotenv
import yaml

from coupang_product_mapping import CoupangProductMappingDB

# Load environment variables
load_dotenv()

# ===== DB 설정 =====
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
SALES_DB_NAME = "sales"  # 쿠팡 판매 데이터 DB

# ===== 설정 =====
RATES_YAML = "rates.yml"
FIXED_WAREHOUSE_CODE = "200"
SELLER_NAME = "로켓그로스"  # 거래처명, 판매채널, 판매유형 고정


def fetch_coupang_sales_data(target_date: str) -> pd.DataFrame:
    """
    쿠팡 로켓그로스 판매 데이터 조회

    Args:
        target_date: 조회할 날짜 (YYYY-MM-DD 형식)

    Returns:
        DataFrame with sales data
    """
    try:
        # DB 연결
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=SALES_DB_NAME
        )
        cursor = conn.cursor(dictionary=True)

        print(f"✅ 쿠팡 판매 DB 연결: {SALES_DB_NAME}")

        # 날짜 조회 (환불 포함)
        query = """
        SELECT
            Date,
            ID_product_coupang_2p_at_sales_report_coupang_2p,
            ID_option_coupang_2p_at_sales_report_coupang_2p,
            Name_option_coupang_at_sales_report_coupang_2p,
            Qty_sales_total_at_sales_report_coupang_2p,
            Sales_total_amount_at_sales_report_coupang_2p
        FROM sales_report_coupang_2p
        WHERE Date = %s
        ORDER BY ID_product_coupang_2p_at_sales_report_coupang_2p
        """

        cursor.execute(query, (target_date,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not rows:
            print(f"⚠️  {target_date}에 대한 판매 데이터가 없습니다.")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        print(f"✅ {len(df)}건의 판매 데이터 조회 완료")

        return df

    except Error as e:
        print(f"❌ 쿠팡 판매 데이터 조회 실패: {e}")
        return pd.DataFrame()


def validate_and_map_products(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    상품 매핑 검증 및 자동 매칭 (세트상품 지원)

    Args:
        df: 쿠팡 판매 데이터 DataFrame

    Returns:
        (매핑된 DataFrame, 수동 처리 필요 목록)
    """
    if df.empty:
        return df, []

    pending_mappings = []

    with CoupangProductMappingDB() as db:
        # 결과 컬럼 추가
        df["standard_product_name"] = ""
        df["quantity_multiplier"] = 1
        df["brand"] = ""
        df["actual_quantity"] = 0
        df["cost_price"] = 0.0
        df["is_set_product"] = False
        df["set_items"] = None  # 세트상품 구성품 리스트

        print(f"\n[검증] 쿠팡 상품 {len(df)}건 매핑 확인 중...")

        # 고유한 옵션명 수집
        unique_options = {}
        for idx, row in df.iterrows():
            option_name = str(row.get("Name_option_coupang_at_sales_report_coupang_2p", "")).strip()
            if option_name:
                if option_name not in unique_options:
                    unique_options[option_name] = []
                unique_options[option_name].append(idx)

        # 각 고유 옵션에 대해 매핑 확인
        for option_name, indices in unique_options.items():
            # DB에서 매핑 조회 (세트상품 지원)
            mapping = db.get_mapping_with_set(option_name)

            if mapping:
                # 매핑 존재
                cost_price = float(mapping.get("cost_price", 0))
                is_set = bool(mapping.get("is_set_product", False))
                set_marker = " [세트]" if is_set else ""

                print(f"  ✅ [{option_name}] → {mapping['standard_product_name']}{set_marker} "
                      f"(x{mapping['quantity_multiplier']}, {mapping['brand']}, 원가: {cost_price:,.0f}원)")

                # 모든 해당 행 업데이트
                for idx in indices:
                    qty_total = int(df.at[idx, "Qty_sales_total_at_sales_report_coupang_2p"] or 0)
                    df.at[idx, "standard_product_name"] = mapping["standard_product_name"]
                    df.at[idx, "quantity_multiplier"] = mapping["quantity_multiplier"]
                    df.at[idx, "brand"] = mapping["brand"]
                    df.at[idx, "actual_quantity"] = qty_total * mapping["quantity_multiplier"]
                    df.at[idx, "cost_price"] = cost_price
                    df.at[idx, "is_set_product"] = is_set
                    if is_set and mapping.get("items"):
                        df.at[idx, "set_items"] = mapping["items"]
            else:
                # 매핑 없음 - GPT 자동 매칭 시도
                print(f"  🤖 [{option_name}] GPT 자동 매칭 시도 중...")

                gpt_result = db.match_product_with_gpt(option_name)

                if gpt_result and gpt_result.get("confidence", 0) >= 0.7:
                    # 신뢰도 높은 경우 자동 저장
                    is_set = bool(gpt_result.get("is_set_product", False))
                    set_marker = " [세트]" if is_set else ""
                    print(f"  ✅ [{option_name}] → {gpt_result['standard_product_name']}{set_marker} "
                          f"(x{gpt_result['quantity_multiplier']}, {gpt_result['brand']}) "
                          f"[신뢰도: {gpt_result['confidence']:.0%}]")

                    # DB에 매핑 저장 (세트상품 여부 포함)
                    db.add_mapping(
                        coupang_option_name=option_name,
                        standard_product_name=gpt_result["standard_product_name"],
                        quantity_multiplier=gpt_result["quantity_multiplier"],
                        brand=gpt_result["brand"],
                        is_set_product=is_set
                    )

                    # 원가 정보 조회 (방금 저장한 매핑에서)
                    saved_mapping = db.get_mapping_with_set(option_name)
                    cost_price = float(saved_mapping.get("cost_price", 0)) if saved_mapping else 0.0

                    # 모든 해당 행 업데이트
                    for idx in indices:
                        qty_total = int(df.at[idx, "Qty_sales_total_at_sales_report_coupang_2p"] or 0)
                        df.at[idx, "standard_product_name"] = gpt_result["standard_product_name"]
                        df.at[idx, "quantity_multiplier"] = gpt_result["quantity_multiplier"]
                        df.at[idx, "brand"] = gpt_result["brand"]
                        df.at[idx, "actual_quantity"] = qty_total * gpt_result["quantity_multiplier"]
                        df.at[idx, "cost_price"] = cost_price
                        df.at[idx, "is_set_product"] = is_set
                        if is_set and saved_mapping and saved_mapping.get("items"):
                            df.at[idx, "set_items"] = saved_mapping["items"]
                else:
                    # 신뢰도 낮거나 실패 - 수동 처리 필요
                    confidence = gpt_result.get("confidence", 0) if gpt_result else 0
                    suggestion = gpt_result.get("standard_product_name") if gpt_result else None

                    print(f"  ⚠️  [{option_name}] 수동 매핑 필요 (신뢰도: {confidence:.0%})")

                    # 첫 번째 행 정보만 추가
                    first_idx = indices[0]
                    row_data = df.loc[first_idx]
                    pending_mappings.append({
                        "option_name": option_name,
                        "count": len(indices),
                        "gpt_suggestion": suggestion,
                        "gpt_multiplier": gpt_result.get("quantity_multiplier") if gpt_result else None,
                        "gpt_brand": gpt_result.get("brand") if gpt_result else None,
                        "is_set_product": gpt_result.get("is_set_product", False) if gpt_result else False,
                        "confidence": confidence,
                        "reason": gpt_result.get("reason") if gpt_result else "매칭 실패",
                        "sample_data": {
                            "date": str(row_data.get("Date", "")),
                            "product_id": str(row_data.get("ID_product_coupang_2p_at_sales_report_coupang_2p", "")),
                            "qty": str(row_data.get("Qty_sales_total_at_sales_report_coupang_2p", "")),
                            "amount": str(row_data.get("Sales_total_amount_at_sales_report_coupang_2p", ""))
                        }
                    })

    return df, pending_mappings


def convert_to_ecount_format(df: pd.DataFrame, target_date: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    쿠팡 판매 데이터를 이카운트 형식으로 변환 (세트상품 지원)

    Args:
        df: 매핑된 쿠팡 판매 데이터
        target_date: 판매일자 (YYYY-MM-DD)

    Returns:
        (판매 DataFrame, 매입 DataFrame)
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 매핑되지 않은 데이터 필터링
    df_mapped = df[df["standard_product_name"] != ""].copy()

    if df_mapped.empty:
        print("⚠️  매핑된 상품이 없습니다.")
        return pd.DataFrame(), pd.DataFrame()

    print(f"\n[변환] {len(df_mapped)}건의 매핑된 데이터를 이카운트 형식으로 변환 중...")

    # 날짜 변환
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    except:
        date_obj = date.today()

    # 판매 데이터 생성 (세트상품 확장 포함)
    sales_list = []
    for _, row in df_mapped.iterrows():
        brand = row["brand"]
        project = f"{brand}_국내"

        # 매출액 (부가세 포함)
        total_amount = int(row.get("Sales_total_amount_at_sales_report_coupang_2p", 0) or 0)

        # 세트상품인 경우 구성품별로 분할
        is_set = row.get("is_set_product", False)
        set_items = row.get("set_items")

        if is_set and set_items:
            # 세트상품: 구성품별로 행 생성
            # 총 원가를 기준으로 각 구성품의 매출 비중 계산
            total_cost = sum(float(item.get("cost_price", 0)) * item.get("quantity", 1)
                            for item in set_items)

            qty_multiplier = row["quantity_multiplier"]

            for item in set_items:
                item_cost = float(item.get("cost_price", 0))
                item_qty = item.get("quantity", 1)
                item_total_cost = item_cost * item_qty

                # 매출 비중에 따른 금액 배분
                if total_cost > 0:
                    amount_ratio = item_total_cost / total_cost
                else:
                    amount_ratio = 1 / len(set_items)

                item_amount = int(total_amount * amount_ratio)
                supply_amt = int(item_amount / 1.1)
                vat_amt = item_amount - supply_amt

                # 실제 수량 = 구성품 수량 × 주문 수량 × 수량배수
                actual_qty = item_qty * qty_multiplier

                sales_list.append({
                    "일자": date_obj,
                    "순번": "",
                    "브랜드": project,
                    "판매채널": SELLER_NAME,
                    "거래처코드": "",
                    "거래처명": SELLER_NAME,
                    "출하창고": FIXED_WAREHOUSE_CODE,
                    "통화": "",
                    "환율": "",
                    "주문번호": "",
                    "상품코드": "",
                    "품목명": item["standard_product_name"],
                    "옵션": "",
                    "규격": "",
                    "수량": actual_qty,
                    "단가(vat포함)": int(item_amount / actual_qty) if actual_qty > 0 else 0,
                    "단가": "",
                    "외화금액": "",
                    "공급가액": supply_amt,
                    "부가세": vat_amt,
                    "송장번호": "",
                    "수령자주소": "",
                    "수령자이름": "",
                    "수령자전화": "",
                    "수령자휴대폰": "",
                    "배송메모": "",
                    "주문상세번호": "",
                    "생산전표생성": "",
                    "판매처": SELLER_NAME
                })
        else:
            # 일반 상품: 기존 로직
            supply_amt = int(total_amount / 1.1)
            vat_amt = total_amount - supply_amt

            sales_list.append({
                "일자": date_obj,
                "순번": "",
                "브랜드": project,
                "판매채널": SELLER_NAME,
                "거래처코드": "",
                "거래처명": SELLER_NAME,
                "출하창고": FIXED_WAREHOUSE_CODE,
                "통화": "",
                "환율": "",
                "주문번호": "",
                "상품코드": "",
                "품목명": row["standard_product_name"],
                "옵션": "",
                "규격": "",
                "수량": row["actual_quantity"],
                "단가(vat포함)": int(total_amount / row["actual_quantity"]) if row["actual_quantity"] > 0 else 0,
                "단가": "",
                "외화금액": "",
                "공급가액": supply_amt,
                "부가세": vat_amt,
                "송장번호": "",
                "수령자주소": "",
                "수령자이름": "",
                "수령자전화": "",
                "수령자휴대폰": "",
                "배송메모": "",
                "주문상세번호": "",
                "생산전표생성": "",
                "판매처": SELLER_NAME
            })

    sales_df = pd.DataFrame(sales_list)

    # 매입 데이터 생성 (원가 기준, 세트상품 확장 포함)
    purchase_list = []
    for _, row in df_mapped.iterrows():
        brand = row["brand"]
        project = f"{brand}_국내"

        # 세트상품인 경우 구성품별로 분할
        is_set = row.get("is_set_product", False)
        set_items = row.get("set_items")

        if is_set and set_items:
            # 세트상품: 구성품별로 행 생성
            qty_multiplier = row["quantity_multiplier"]

            for item in set_items:
                item_cost = float(item.get("cost_price", 0))
                item_qty = item.get("quantity", 1)

                # 실제 수량 = 구성품 수량 × 주문 수량 × 수량배수
                actual_qty = item_qty * qty_multiplier

                # 총 원가 = 단가 × 수량
                total_cost = int(item_cost * actual_qty)
                supply_amt = int(total_cost / 1.1)
                vat_amt = total_cost - supply_amt

                purchase_list.append({
                    "일자": date_obj,
                    "순번": "",
                    "브랜드": project,
                    "판매채널": SELLER_NAME,
                    "거래처코드": "",
                    "거래처명": SELLER_NAME,
                    "입고창고": FIXED_WAREHOUSE_CODE,
                    "통화": "",
                    "환율": "",
                    "품목코드": "",
                    "품목명": item["standard_product_name"],
                    "규격명": "",
                    "수량": actual_qty,
                    "단가": int(item_cost),
                    "외화금액": "",
                    "공급가액": supply_amt,
                    "부가세": vat_amt,
                    "적요": f"{project} {SELLER_NAME}",
                    "판매처": SELLER_NAME
                })
        else:
            # 일반 상품: 기존 로직
            cost_price = float(row.get("cost_price", 0))
            actual_qty = row["actual_quantity"]

            # 총 원가 = 단가 × 수량
            total_cost = int(cost_price * actual_qty)
            supply_amt = int(total_cost / 1.1)
            vat_amt = total_cost - supply_amt

            purchase_list.append({
                "일자": date_obj,
                "순번": "",
                "브랜드": project,
                "판매채널": SELLER_NAME,
                "거래처코드": "",
                "거래처명": SELLER_NAME,
                "입고창고": FIXED_WAREHOUSE_CODE,
                "통화": "",
                "환율": "",
                "품목코드": "",
                "품목명": row["standard_product_name"],
                "규격명": "",
                "수량": actual_qty,
                "단가": int(cost_price),
                "외화금액": "",
                "공급가액": supply_amt,
                "부가세": vat_amt,
                "적요": f"{project} {SELLER_NAME}",
                "판매처": SELLER_NAME
            })

    purchase_df = pd.DataFrame(purchase_list)

    print(f"✅ 판매: {len(sales_df)}건, 매입: {len(purchase_df)}건 변환 완료")

    return sales_df, purchase_df


def build_sales_voucher(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    판매 데이터로부터 매출전표 생성 (월별 합산)

    Args:
        sales_df: 판매 DataFrame

    Returns:
        매출전표 DataFrame
    """
    if sales_df.empty:
        return pd.DataFrame()

    # 월 추출 (YYYY-MM 형식)
    temp_df = sales_df.copy()
    temp_df["월"] = pd.to_datetime(temp_df["일자"]).dt.to_period('M')

    # (월, 브랜드, 판매채널, 거래처명) 기준으로 그룹화하여 공급가액과 부가세 합산
    grouped = temp_df.groupby(["월", "브랜드", "판매채널", "거래처명"], dropna=False, as_index=False).agg({
        "일자": "max",  # 해당 월의 마지막 날짜
        "공급가액": "sum",
        "부가세": "sum"
    })

    vouchers = []
    for _, row in grouped.iterrows():
        vouchers.append({
            "전표일자": row["일자"],
            "브랜드": str(row["브랜드"]),
            "판매채널": str(row["판매채널"]),
            "거래처코드": "",
            "거래처명": str(row["거래처명"]),
            "부가세유형": "",
            "공급가액": int(row["공급가액"]),
            "외화금액": "",
            "환율": "",
            "부가세": int(row["부가세"]),
            "적요": "",
            "매출계정코드": "4019",
            "입금계좌": ""
        })

    voucher_df = pd.DataFrame(vouchers)
    print(f"✅ 매출전표 {len(voucher_df)}건 생성 완료 (월별 합산)")

    return voucher_df


def build_cost_voucher(purchase_df: pd.DataFrame) -> pd.DataFrame:
    """
    매입 데이터로부터 원가매입전표 생성 (월별 합산)

    Args:
        purchase_df: 매입 DataFrame

    Returns:
        원가매입전표 DataFrame
    """
    if purchase_df.empty:
        return pd.DataFrame()

    # 월 추출 (YYYY-MM 형식)
    temp_df = purchase_df.copy()
    temp_df["월"] = pd.to_datetime(temp_df["일자"]).dt.to_period('M')

    # (월, 브랜드, 판매채널, 거래처명) 기준으로 그룹화하여 공급가액과 부가세 합산
    grouped = temp_df.groupby(["월", "브랜드", "판매채널", "거래처명"], dropna=False, as_index=False).agg({
        "일자": "max",  # 해당 월의 마지막 날짜
        "공급가액": "sum",
        "부가세": "sum"
    })

    vouchers = []
    for _, row in grouped.iterrows():
        vouchers.append({
            "전표일자": row["일자"],
            "브랜드": str(row["브랜드"]),
            "판매채널": str(row["판매채널"]),
            "거래처코드": "",
            "거래처명": str(row["거래처명"]),
            "부가세유형": "",
            "신용카드/승인번호": "",
            "공급가액": int(row["공급가액"]),
            "외화금액": "",
            "환율": "",
            "부가세": int(row["부가세"]),
            "적요": "",
            "매입계정코드": "4519",
            "돈나간계좌번호": "",
            "채무번호": "",
            "만기일자": ""
        })

    voucher_df = pd.DataFrame(vouchers)
    print(f"✅ 원가매입전표 {len(voucher_df)}건 생성 완료 (월별 합산)")

    return voucher_df


def build_voucher_from_sales(sales_df: pd.DataFrame, rates_yaml: str = RATES_YAML) -> pd.DataFrame:
    """
    판매 데이터로부터 매입전표(수수료, 운송료) 생성

    Args:
        sales_df: 판매 DataFrame
        rates_yaml: 요율 파일 경로

    Returns:
        매입전표 DataFrame
    """
    if sales_df.empty:
        return pd.DataFrame()

    # rates.yml 로드
    rate_book = load_rate_book_from_yaml(rates_yaml)

    # (일자, 브랜드, 판매채널) 기준으로 그룹화하여 매출액 합계
    grouped = sales_df.groupby(["일자", "브랜드", "거래처명"], dropna=False, as_index=False)["단가(vat포함)"].sum()

    vouchers = []
    for _, row in grouped.iterrows():
        date_val = row["일자"]
        project = str(row["브랜드"])
        dept = SELLER_NAME

        # 요율 조회
        rates = rate_book.get(project, {}).get(dept, {})
        shipping_rate = rates.get("shipping", 0.0)
        commission_rate = rates.get("commission", 0.0)

        total_sales = int(row["단가(vat포함)"])

        # 운송료 계산 (부가세 별도)
        shipping_total = int(total_sales * shipping_rate)
        shipping_supply = int(shipping_total / 1.1)
        shipping_vat = shipping_total - shipping_supply

        # 수수료 계산 (부가세 별도)
        commission_total = int(total_sales * commission_rate)
        commission_supply = int(commission_total / 1.1)
        commission_vat = commission_total - commission_supply

        # 운송료 전표 (매입계정코드 8019)
        if shipping_total > 0:
            vouchers.append({
                "전표일자": date_val,
                "브랜드": project,
                "판매채널": dept,
                "거래처코드": "",
                "거래처명": dept,
                "부가세유형": "과세",
                "신용카드/승인번호": "",
                "공급가액": shipping_supply,
                "외화금액": "",
                "환율": "",
                "부가세": shipping_vat,
                "적요": "운송료",
                "매입계정코드": "8019",
                "돈나간계좌번호": "",
                "채무번호": "",
                "만기일자": ""
            })

        # 수수료 전표 (매입계정코드 8029)
        if commission_total > 0:
            vouchers.append({
                "전표일자": date_val,
                "브랜드": project,
                "판매채널": dept,
                "거래처코드": "",
                "거래처명": dept,
                "부가세유형": "과세",
                "신용카드/승인번호": "",
                "공급가액": commission_supply,
                "외화금액": "",
                "환율": "",
                "부가세": commission_vat,
                "적요": "수수료",
                "매입계정코드": "8029",
                "돈나간계좌번호": "",
                "채무번호": "",
                "만기일자": ""
            })

    voucher_df = pd.DataFrame(vouchers)
    print(f"✅ 매입전표 {len(voucher_df)}건 생성 완료")

    return voucher_df


def load_rate_book_from_yaml(path: str) -> dict:
    """
    YAML에서 요율 정보 로드

    YAML 구조:
    닥터시드_국내:
      로켓그로스: { shipping: 0.13, commission: 0.06 }
    """
    if not os.path.exists(path):
        print(f"[WARN] 요율 파일이 없습니다: {path} — 모든 요율 0으로 처리됩니다.")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    rate_book = {}
    for proj, client_map in raw.items():
        if not isinstance(client_map, dict):
            continue
        rate_book[proj] = {}
        for client, rates in client_map.items():
            if not isinstance(rates, dict):
                continue
            rate_book[proj][client] = {
                "shipping": rates.get("shipping", 0.0),
                "commission": rates.get("commission", 0.0)
            }

    return rate_book


def save_to_excel(sales_df: pd.DataFrame, purchase_df: pd.DataFrame,
                  sales_voucher_df: pd.DataFrame, cost_voucher_df: pd.DataFrame,
                  fee_voucher_df: pd.DataFrame, output_file: str = "output_coupang_rocketgrowth.xlsx"):
    """
    변환 결과를 엑셀 파일로 저장

    Args:
        sales_df: 판매 DataFrame
        purchase_df: 매입 DataFrame
        sales_voucher_df: 매출전표 DataFrame
        cost_voucher_df: 원가매입전표 DataFrame
        fee_voucher_df: 운반비/수수료 매입전표 DataFrame
        output_file: 저장할 파일명
    """
    if sales_df.empty and purchase_df.empty and sales_voucher_df.empty and cost_voucher_df.empty and fee_voucher_df.empty:
        print("❌ 저장할 데이터가 없습니다.")
        return

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        if not sales_df.empty:
            sales_df.to_excel(writer, sheet_name="판매", index=False)
        if not purchase_df.empty:
            purchase_df.to_excel(writer, sheet_name="매입", index=False)
        if not sales_voucher_df.empty:
            sales_voucher_df.to_excel(writer, sheet_name="매출전표", index=False)
        if not cost_voucher_df.empty:
            cost_voucher_df.to_excel(writer, sheet_name="원가매입전표", index=False)
        if not fee_voucher_df.empty:
            fee_voucher_df.to_excel(writer, sheet_name="운반비수수료전표", index=False)

    print(f"✅ {output_file}: 판매 {len(sales_df)}건, 매입 {len(purchase_df)}건")
    print(f"   전표: 매출 {len(sales_voucher_df)}건, 원가매입 {len(cost_voucher_df)}건, 운반비/수수료 {len(fee_voucher_df)}건 저장 완료")


def process_coupang_rocketgrowth(target_date: str, max_retries: int = 5) -> Dict[str, Any]:
    """
    쿠팡 로켓그로스 판매 데이터 처리 메인 함수

    Args:
        target_date: 판매일자 (YYYY-MM-DD)
        max_retries: 최대 재시도 횟수 (웹 에디터 매핑 후 재검증)

    Returns:
        처리 결과
    """
    print("=" * 80)
    print(f"쿠팡 로켓그로스 판매 데이터 처리: {target_date}")
    print("=" * 80)

    result = {
        "fetch": None,
        "validation": None,
        "conversion": None
    }

    # ===== 데이터 조회 및 매핑 재시도 루프 =====
    for attempt in range(1, max_retries + 1):
        try:
            if attempt == 1:
                print(f"\n[1단계] {target_date} 판매 데이터 조회 중...")
                df = fetch_coupang_sales_data(target_date)

                if df.empty:
                    print("❌ 조회된 데이터가 없습니다.")
                    result["fetch"] = {"success": False, "error": "No data"}
                    return {
                        "sales": pd.DataFrame(),
                        "purchase": pd.DataFrame(),
                        "voucher": pd.DataFrame(),
                        "result": result
                    }

                result["fetch"] = {"success": True, "count": len(df)}
            else:
                print(f"\n[1단계-재시도 {attempt}/{max_retries}] 매핑 후 재검증 중...")

            # 2. 상품 매핑 검증
            print(f"\n[2단계] 상품 매핑 검증 중...")
            df_mapped, pending_mappings = validate_and_map_products(df)

            if pending_mappings:
                print("\n" + "=" * 80)
                print(f"⚠️  [수동 매핑 필요] 매핑되지 않은 상품: {len(pending_mappings)}건")
                print("=" * 80)

                # 고유 상품 표시
                unique_options = {}
                for p in pending_mappings:
                    option = p.get("option_name", "")
                    if option not in unique_options:
                        unique_options[option] = p

                for option, info in unique_options.items():
                    print(f"\n  - {option}")
                    if info.get("gpt_suggestion"):
                        print(f"    └ GPT 추천: {info['gpt_suggestion']} "
                              f"(x{info['gpt_multiplier']}, {info['gpt_brand']}, "
                              f"신뢰도: {info['confidence']:.0%})")

                print("\n❌ 업로드를 중단합니다.")
                print("   DB에 없는 상품이 포함된 데이터는 업로드할 수 없습니다.")

                # 세트상품과 일반상품 구분
                has_set_products = any(p.get("is_set_product", False) for p in pending_mappings)
                has_regular_products = any(not p.get("is_set_product", False) for p in pending_mappings)

                try:
                    import threading

                    # 세트상품이 있으면 세트상품 편집기 실행
                    if has_set_products:
                        from set_product_editor import start_editor as start_set_editor

                        print("\n🌐 세트상품 편집기를 실행합니다...")
                        print("   브라우저에서 http://localhost:5002 접속하여 세트상품을 생성하세요.\n")

                        set_editor_thread = threading.Thread(
                            target=start_set_editor,
                            kwargs={"port": 5002, "debug": False},
                            daemon=True
                        )
                        set_editor_thread.start()

                        # 사용자가 세트상품 생성 완료 후 Enter를 누르기를 기다림
                        input("\n세트상품 생성을 완료했다면 Enter를 눌러 계속 진행하세요...")

                    # 일반상품 편집기 실행 (일반상품 또는 세트상품 매핑용)
                    from coupang_product_editor import start_editor

                    print("\n🌐 상품 매핑 편집기를 실행합니다...")
                    print("   브라우저에서 http://localhost:5001 접속하여 상품을 매핑하세요.\n")

                    # 웹 에디터를 백그라운드 스레드로 실행
                    editor_thread = threading.Thread(
                        target=start_editor,
                        kwargs={"pending_list": pending_mappings, "port": 5001, "debug": False},
                        daemon=True
                    )
                    editor_thread.start()

                    # 사용자가 웹에서 매핑 완료 후 Enter를 누르기를 기다림
                    input("\n매핑을 완료했다면 Enter를 눌러 계속 진행하세요...")

                    print("\n✅ 매핑을 저장했습니다.")
                    print("   → 데이터를 다시 검증합니다...\n")

                    # 루프를 계속해서 재검증 시도
                    continue

                except KeyboardInterrupt:
                    print("\n⚠️  사용자가 중단했습니다.")
                    result["validation"] = {"success": False, "pending_count": len(pending_mappings)}
                    return {
                        "sales": pd.DataFrame(),
                        "purchase": pd.DataFrame(),
                        "voucher": pd.DataFrame(),
                        "result": result
                    }
                except Exception as e:
                    print(f"\n⚠️  웹 에디터 실행 실패: {e}")
                    print("   수동으로 coupang_product_mapping.py를 사용하여 매핑을 추가하세요.")
                    print("   매핑 완료 후 프로그램을 다시 실행하세요.")
                    result["validation"] = {"success": False, "pending_count": len(pending_mappings)}
                    return {
                        "sales": pd.DataFrame(),
                        "purchase": pd.DataFrame(),
                        "voucher": pd.DataFrame(),
                        "result": result
                    }
            else:
                # 모든 매핑이 완료됨 - 루프 탈출하고 변환 진행
                print("\n✅ 모든 상품 검증 완료!")
                break

        except Exception as e:
            print(f"❌ 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            result["validation"] = {"success": False, "error": str(e)}
            return {
                "sales": pd.DataFrame(),
                "purchase": pd.DataFrame(),
                "voucher": pd.DataFrame(),
                "result": result
            }
    else:
        # 최대 재시도 횟수 초과
        print(f"\n❌ 최대 재시도 횟수({max_retries}회)를 초과했습니다.")
        print("   매핑을 완료한 후 프로그램을 다시 실행하세요.")
        result["validation"] = {"success": False, "error": "Max retries exceeded"}
        return {
            "sales": pd.DataFrame(),
            "purchase": pd.DataFrame(),
            "voucher": pd.DataFrame(),
            "result": result
        }

    result["validation"] = {"success": True}

    # 3. 이카운트 형식 변환
    print(f"\n[3단계] 이카운트 형식 변환 중...")
    sales_df, purchase_df = convert_to_ecount_format(df_mapped, target_date)

    # 전표 생성
    sales_voucher_df = build_sales_voucher(sales_df)
    cost_voucher_df = build_cost_voucher(purchase_df)
    fee_voucher_df = build_voucher_from_sales(sales_df)

    result["conversion"] = {
        "success": True,
        "sales_count": len(sales_df),
        "purchase_count": len(purchase_df),
        "sales_voucher_count": len(sales_voucher_df),
        "cost_voucher_count": len(cost_voucher_df),
        "fee_voucher_count": len(fee_voucher_df)
    }

    # 4. 엑셀 저장
    save_to_excel(sales_df, purchase_df, sales_voucher_df, cost_voucher_df, fee_voucher_df)

    print("\n" + "=" * 80)
    print("처리 완료")
    print("=" * 80)

    return {
        "sales": sales_df,
        "purchase": purchase_df,
        "sales_voucher": sales_voucher_df,
        "cost_voucher": cost_voucher_df,
        "fee_voucher": fee_voucher_df,
        "voucher": fee_voucher_df,  # 하위 호환성을 위해 유지
        "result": result
    }


def process_coupang_date_range(start_date: str, end_date: str, max_retries: int = 5) -> Dict[str, Any]:
    """
    쿠팡 로켓그로스 판매 데이터 날짜 범위 처리

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        max_retries: 최대 재시도 횟수

    Returns:
        전체 처리 결과
    """
    from datetime import datetime, timedelta

    print("=" * 80)
    print(f"쿠팡 로켓그로스 판매 데이터 범위 처리: {start_date} ~ {end_date}")
    print("=" * 80)

    # 날짜 파싱
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        print(f"❌ 날짜 형식 오류: {e}")
        return {
            "success": False,
            "error": "Invalid date format",
            "dates_processed": []
        }

    if start > end:
        print("❌ 시작 날짜가 종료 날짜보다 늦습니다.")
        return {
            "success": False,
            "error": "Start date is after end date",
            "dates_processed": []
        }

    # 날짜 리스트 생성
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    print(f"\n📅 처리할 날짜: {len(dates)}일")
    print(f"   {', '.join(dates)}\n")

    # 각 날짜별 결과 저장
    all_sales = []
    all_purchase = []
    all_sales_voucher = []
    all_cost_voucher = []
    all_fee_voucher = []
    dates_processed = []
    dates_failed = []

    # 날짜별로 순차 처리
    for idx, target_date in enumerate(dates, 1):
        print("\n" + "=" * 80)
        print(f"[{idx}/{len(dates)}] {target_date} 처리 중...")
        print("=" * 80)

        try:
            result = process_coupang_rocketgrowth(target_date, max_retries)

            # 성공한 경우 데이터 수집
            if result["result"].get("conversion", {}).get("success", False):
                sales_df = result["sales"]
                purchase_df = result["purchase"]
                sales_voucher_df = result["sales_voucher"]
                cost_voucher_df = result["cost_voucher"]
                fee_voucher_df = result["fee_voucher"]

                if not sales_df.empty:
                    all_sales.append(sales_df)
                if not purchase_df.empty:
                    all_purchase.append(purchase_df)
                if not sales_voucher_df.empty:
                    all_sales_voucher.append(sales_voucher_df)
                if not cost_voucher_df.empty:
                    all_cost_voucher.append(cost_voucher_df)
                if not fee_voucher_df.empty:
                    all_fee_voucher.append(fee_voucher_df)

                dates_processed.append(target_date)
                print(f"✅ {target_date} 처리 완료")
            else:
                dates_failed.append(target_date)
                print(f"⚠️  {target_date} 처리 실패 또는 데이터 없음")

        except Exception as e:
            dates_failed.append(target_date)
            print(f"❌ {target_date} 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()

    # 전체 데이터 병합
    print("\n" + "=" * 80)
    print("전체 데이터 병합 중...")
    print("=" * 80)

    merged_sales = pd.concat(all_sales, ignore_index=True) if all_sales else pd.DataFrame()
    merged_purchase = pd.concat(all_purchase, ignore_index=True) if all_purchase else pd.DataFrame()
    merged_sales_voucher = pd.concat(all_sales_voucher, ignore_index=True) if all_sales_voucher else pd.DataFrame()
    merged_cost_voucher = pd.concat(all_cost_voucher, ignore_index=True) if all_cost_voucher else pd.DataFrame()
    merged_fee_voucher = pd.concat(all_fee_voucher, ignore_index=True) if all_fee_voucher else pd.DataFrame()

    # 최종 결과 저장
    output_filename = f"output_coupang_rocketgrowth_{start_date}_to_{end_date}.xlsx"
    save_to_excel(merged_sales, merged_purchase, merged_sales_voucher, merged_cost_voucher, merged_fee_voucher, output_filename)

    # 결과 요약
    print("\n" + "=" * 80)
    print("처리 완료 요약")
    print("=" * 80)
    print(f"총 날짜: {len(dates)}일")
    print(f"성공: {len(dates_processed)}일")
    print(f"실패: {len(dates_failed)}일")
    if dates_processed:
        print(f"\n✅ 처리된 날짜: {', '.join(dates_processed)}")
    if dates_failed:
        print(f"\n⚠️  실패한 날짜: {', '.join(dates_failed)}")
    print(f"\n📊 병합된 데이터:")
    print(f"   판매: {len(merged_sales)}건")
    print(f"   매입: {len(merged_purchase)}건")
    print(f"   전표: 매출 {len(merged_sales_voucher)}건, 원가매입 {len(merged_cost_voucher)}건, 운반비/수수료 {len(merged_fee_voucher)}건")
    print(f"\n💾 저장 파일: {output_filename}")
    print("=" * 80)

    return {
        "success": len(dates_failed) == 0,
        "dates_processed": dates_processed,
        "dates_failed": dates_failed,
        "sales": merged_sales,
        "purchase": merged_purchase,
        "sales_voucher": merged_sales_voucher,
        "cost_voucher": merged_cost_voucher,
        "fee_voucher": merged_fee_voucher,
        "voucher": merged_fee_voucher,  # 하위 호환성을 위해 유지
        "output_file": output_filename
    }


if __name__ == "__main__":
    # 사용자에게 날짜 입력받기
    print("=" * 80)
    print("쿠팡 로켓그로스 판매 데이터 처리")
    print("=" * 80)

    target_date = input("\n처리할 날짜를 입력하세요 (YYYY-MM-DD): ").strip()

    if not target_date:
        print("❌ 날짜를 입력하지 않았습니다.")
    else:
        process_coupang_rocketgrowth(target_date)
