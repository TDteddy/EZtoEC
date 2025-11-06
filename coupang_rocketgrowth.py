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

        # 날짜 조회
        query = """
        SELECT
            Date,
            ID_product_coupang_2p_at_sales_report_coupang_2p,
            ID_option_coupang_2p_at_sales_report_coupang_2p,
            Name_option_coupang_at_sales_report_coupang_2p,
            Qty_sales_net_at_sales_report_coupang_2p,
            Sales_total_amount_at_sales_report_coupang_2p
        FROM sales_report_coupang_2p
        WHERE Date = %s AND Qty_sales_net_at_sales_report_coupang_2p > 0
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
    상품 매핑 검증 및 자동 매칭

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
            # DB에서 매핑 조회
            mapping = db.get_mapping(option_name)

            if mapping:
                # 매핑 존재
                print(f"  ✅ [{option_name}] → {mapping['standard_product_name']} "
                      f"(x{mapping['quantity_multiplier']}, {mapping['brand']})")

                # 모든 해당 행 업데이트
                for idx in indices:
                    qty_net = int(df.at[idx, "Qty_sales_net_at_sales_report_coupang_2p"] or 0)
                    df.at[idx, "standard_product_name"] = mapping["standard_product_name"]
                    df.at[idx, "quantity_multiplier"] = mapping["quantity_multiplier"]
                    df.at[idx, "brand"] = mapping["brand"]
                    df.at[idx, "actual_quantity"] = qty_net * mapping["quantity_multiplier"]
            else:
                # 매핑 없음 - GPT 자동 매칭 시도
                print(f"  🤖 [{option_name}] GPT 자동 매칭 시도 중...")

                gpt_result = db.match_product_with_gpt(option_name)

                if gpt_result and gpt_result.get("confidence", 0) >= 0.7:
                    # 신뢰도 높은 경우 자동 저장
                    print(f"  ✅ [{option_name}] → {gpt_result['standard_product_name']} "
                          f"(x{gpt_result['quantity_multiplier']}, {gpt_result['brand']}) "
                          f"[신뢰도: {gpt_result['confidence']:.0%}]")

                    # DB에 매핑 저장
                    db.add_mapping(
                        coupang_option_name=option_name,
                        standard_product_name=gpt_result["standard_product_name"],
                        quantity_multiplier=gpt_result["quantity_multiplier"],
                        brand=gpt_result["brand"]
                    )

                    # 모든 해당 행 업데이트
                    for idx in indices:
                        qty_net = int(df.at[idx, "Qty_sales_net_at_sales_report_coupang_2p"] or 0)
                        df.at[idx, "standard_product_name"] = gpt_result["standard_product_name"]
                        df.at[idx, "quantity_multiplier"] = gpt_result["quantity_multiplier"]
                        df.at[idx, "brand"] = gpt_result["brand"]
                        df.at[idx, "actual_quantity"] = qty_net * gpt_result["quantity_multiplier"]
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
                        "confidence": confidence,
                        "reason": gpt_result.get("reason") if gpt_result else "매칭 실패",
                        "sample_data": {
                            "date": str(row_data.get("Date", "")),
                            "product_id": str(row_data.get("ID_product_coupang_2p_at_sales_report_coupang_2p", "")),
                            "qty": str(row_data.get("Qty_sales_net_at_sales_report_coupang_2p", "")),
                            "amount": str(row_data.get("Sales_total_amount_at_sales_report_coupang_2p", ""))
                        }
                    })

    return df, pending_mappings


def convert_to_ecount_format(df: pd.DataFrame, target_date: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    쿠팡 판매 데이터를 이카운트 형식으로 변환

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

    # 판매 데이터 생성
    sales_list = []
    for _, row in df_mapped.iterrows():
        brand = row["brand"]
        project = f"{brand}_국내"

        # 매출액 (부가세 포함)
        total_amount = int(row.get("Sales_total_amount_at_sales_report_coupang_2p", 0) or 0)
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
            "옵션": row.get("Name_option_coupang_at_sales_report_coupang_2p", ""),
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

    # 매입 데이터도 동일하게 생성 (구매 원가 기준)
    purchase_list = []
    for _, row in df_mapped.iterrows():
        brand = row["brand"]
        project = f"{brand}_국내"

        # 여기서는 매출액을 그대로 매입원가로 사용 (실제로는 원가 DB가 있어야 함)
        total_amount = int(row.get("Sales_total_amount_at_sales_report_coupang_2p", 0) or 0)
        supply_amt = int(total_amount / 1.1)
        vat_amt = total_amount - supply_amt

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
            "수량": row["actual_quantity"],
            "단가": int(total_amount / row["actual_quantity"]) if row["actual_quantity"] > 0 else 0,
            "외화금액": "",
            "공급가액": supply_amt,
            "부가세": vat_amt,
            "적요": f"{project} {SELLER_NAME}",
            "판매처": SELLER_NAME
        })

    purchase_df = pd.DataFrame(purchase_list)

    print(f"✅ 판매: {len(sales_df)}건, 매입: {len(purchase_df)}건 변환 완료")

    return sales_df, purchase_df


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

        # 운송료 전표
        if shipping_total > 0:
            vouchers.append({
                "전표일자": date_val,
                "브랜드": project,
                "판매채널": dept,
                "거래처코드": "",
                "거래처명": dept,
                "부가세유형": "과세",
                "품목명": "운송료",
                "수량": 1,
                "단가": shipping_supply,
                "공급가액": shipping_supply,
                "부가세": shipping_vat,
                "합계": shipping_total
            })

        # 수수료 전표
        if commission_total > 0:
            vouchers.append({
                "전표일자": date_val,
                "브랜드": project,
                "판매채널": dept,
                "거래처코드": "",
                "거래처명": dept,
                "부가세유형": "과세",
                "품목명": "수수료",
                "수량": 1,
                "단가": commission_supply,
                "공급가액": commission_supply,
                "부가세": commission_vat,
                "합계": commission_total
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
                  voucher_df: pd.DataFrame, output_file: str = "output_coupang_rocketgrowth.xlsx"):
    """
    변환 결과를 엑셀 파일로 저장

    Args:
        sales_df: 판매 DataFrame
        purchase_df: 매입 DataFrame
        voucher_df: 매입전표 DataFrame
        output_file: 저장할 파일명
    """
    if sales_df.empty and purchase_df.empty and voucher_df.empty:
        print("❌ 저장할 데이터가 없습니다.")
        return

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        if not sales_df.empty:
            sales_df.to_excel(writer, sheet_name="판매", index=False)
        if not purchase_df.empty:
            purchase_df.to_excel(writer, sheet_name="매입", index=False)
        if not voucher_df.empty:
            voucher_df.to_excel(writer, sheet_name="매입전표", index=False)

    print(f"✅ {output_file}: 판매 {len(sales_df)}건, 매입 {len(purchase_df)}건, 매입전표 {len(voucher_df)}건 저장 완료")


def process_coupang_rocketgrowth(target_date: str) -> Dict[str, Any]:
    """
    쿠팡 로켓그로스 판매 데이터 처리 메인 함수

    Args:
        target_date: 판매일자 (YYYY-MM-DD)

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

    # 1. 데이터 조회
    print(f"\n[1단계] {target_date} 판매 데이터 조회 중...")
    df = fetch_coupang_sales_data(target_date)

    if df.empty:
        print("❌ 조회된 데이터가 없습니다.")
        result["fetch"] = {"success": False, "error": "No data"}
        return result

    result["fetch"] = {"success": True, "count": len(df)}

    # 2. 상품 매핑 검증
    print(f"\n[2단계] 상품 매핑 검증 중...")
    df_mapped, pending_mappings = validate_and_map_products(df)

    if pending_mappings:
        print("\n" + "=" * 80)
        print(f"⚠️  [수동 매핑 필요] 매핑되지 않은 상품: {len(pending_mappings)}건")
        print("=" * 80)

        for p in pending_mappings:
            print(f"\n  [{p['option_name']}] ({p['count']}건)")
            if p.get("gpt_suggestion"):
                print(f"    GPT 추천: {p['gpt_suggestion']} (x{p['gpt_multiplier']}, {p['gpt_brand']})")
                print(f"    신뢰도: {p['confidence']:.0%}")
            print(f"    샘플: {p['sample_data']}")

        print("\n❌ 매핑이 필요한 상품이 있습니다.")
        print("   coupang_product_mapping.py를 사용하여 매핑을 추가하세요.")

        result["validation"] = {"success": False, "pending_count": len(pending_mappings)}
        return result

    result["validation"] = {"success": True}

    # 3. 이카운트 형식 변환
    print(f"\n[3단계] 이카운트 형식 변환 중...")
    sales_df, purchase_df = convert_to_ecount_format(df_mapped, target_date)
    voucher_df = build_voucher_from_sales(sales_df)

    result["conversion"] = {
        "success": True,
        "sales_count": len(sales_df),
        "purchase_count": len(purchase_df),
        "voucher_count": len(voucher_df)
    }

    # 4. 엑셀 저장
    save_to_excel(sales_df, purchase_df, voucher_df)

    print("\n" + "=" * 80)
    print("처리 완료")
    print("=" * 80)

    return {
        "sales": sales_df,
        "purchase": purchase_df,
        "voucher": voucher_df,
        "result": result
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
