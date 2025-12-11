"""
쿠팡 로켓그로스 차이 보고서 처리

월별보고서와 DB 판매 데이터의 차이를 보정하기 위한 전표 생성
"""

import pandas as pd
import os
from typing import Dict, Any, Optional
from datetime import datetime

from coupang_product_mapping import CoupangProductMappingDB
from coupang_rocketgrowth import (
    build_sales_voucher,
    build_cost_voucher,
    build_voucher_from_sales,
    save_to_excel
)


def process_coupang_difference_report(
    excel_file: str,
    target_date: str,
    max_retries: int = 5
) -> Dict[str, Any]:
    """
    쿠팡 로켓그로스 차이 보고서 처리

    Args:
        excel_file: 차이 보고서 엑셀 파일 경로
        target_date: 전표 날짜 (YYYY-MM-DD, 보통 월말일)
        max_retries: GPT 매핑 최대 재시도 횟수

    Returns:
        처리 결과 딕셔너리
    """
    print("=" * 80)
    print(f"쿠팡 로켓그로스 차이 보고서 처리: {target_date}")
    print("=" * 80)

    result = {}

    # 1. 엑셀 파일 읽기
    print(f"\n[1단계] 차이 보고서 읽기: {excel_file}")

    if not os.path.exists(excel_file):
        print(f"❌ 파일을 찾을 수 없습니다: {excel_file}")
        return {
            "success": False,
            "error": "File not found",
            "result": result
        }

    try:
        df = pd.read_excel(excel_file, sheet_name="차이 있는 항목")
        print(f"✅ {len(df)}건의 차이 항목 읽기 완료")
        result["fetch"] = {"success": True, "count": len(df)}
    except Exception as e:
        print(f"❌ 엑셀 파일 읽기 실패: {e}")
        return {
            "success": False,
            "error": str(e),
            "result": result
        }

    if df.empty:
        print("⚠️  차이 항목이 없습니다.")
        return {
            "success": True,
            "result": result
        }

    # 2. 상품 매핑
    print(f"\n[2단계] 상품 매핑 처리 중...")

    db = CoupangProductMappingDB()
    db.connect()

    # 필요한 컬럼 추가
    df["standard_product_name"] = ""
    df["brand"] = ""
    df["quantity_multiplier"] = 1
    df["cost_price"] = 0.0
    df["is_set_product"] = False
    df["set_items"] = None

    unmapped_items = []
    retry_count = 0

    while retry_count < max_retries:
        unmapped_items = []

        for idx, row in df.iterrows():
            # 이미 매핑된 경우 스킵
            if pd.notna(df.at[idx, "standard_product_name"]) and df.at[idx, "standard_product_name"]:
                continue

            db_option_name = str(row.get("DB_옵션명", "")).strip()
            report_option_name = str(row.get("월별보고서_옵션명", "")).strip()

            # DB_옵션명이 있으면 DB 조회
            if db_option_name:
                mapping = db.get_mapping_with_set(db_option_name)

                if mapping:
                    cost_price = float(mapping.get("cost_price", 0))
                    is_set = bool(mapping.get("is_set_product", False))
                    set_marker = " [세트]" if is_set else ""

                    print(f"  ✅ [DB: {db_option_name}] → {mapping['standard_product_name']}{set_marker} "
                          f"(x{mapping['quantity_multiplier']}, {mapping['brand']}, 원가: {cost_price:,.0f}원)")

                    df.at[idx, "standard_product_name"] = mapping["standard_product_name"]
                    df.at[idx, "brand"] = mapping["brand"]
                    df.at[idx, "quantity_multiplier"] = mapping["quantity_multiplier"]
                    df.at[idx, "cost_price"] = cost_price
                    df.at[idx, "is_set_product"] = is_set
                    if is_set and mapping.get("items"):
                        df.at[idx, "set_items"] = mapping["items"]
                    continue

            # DB_옵션명이 없거나 매핑이 없으면 월별보고서_옵션명으로 시도
            if report_option_name:
                # 먼저 DB에서 조회
                mapping = db.get_mapping_with_set(report_option_name)

                if mapping:
                    # DB에 매핑이 있으면 사용
                    cost_price = float(mapping.get("cost_price", 0))
                    is_set = bool(mapping.get("is_set_product", False))
                    set_marker = " [세트]" if is_set else ""

                    print(f"  ✅ [보고서: {report_option_name}] → {mapping['standard_product_name']}{set_marker} "
                          f"(x{mapping['quantity_multiplier']}, {mapping['brand']}, 원가: {cost_price:,.0f}원)")

                    df.at[idx, "standard_product_name"] = mapping["standard_product_name"]
                    df.at[idx, "brand"] = mapping["brand"]
                    df.at[idx, "quantity_multiplier"] = mapping["quantity_multiplier"]
                    df.at[idx, "cost_price"] = cost_price
                    df.at[idx, "is_set_product"] = is_set
                    if is_set and mapping.get("items"):
                        df.at[idx, "set_items"] = mapping["items"]
                    continue

                # DB에 없으면 GPT 매핑 시도
                print(f"  🤖 [보고서: {report_option_name}] GPT 자동 매칭 시도 중...")

                gpt_result = db.match_product_with_gpt(report_option_name)

                if gpt_result and gpt_result.get("confidence", 0) >= 0.7:
                    # 신뢰도 높은 경우 자동 저장
                    is_set = bool(gpt_result.get("is_set_product", False))
                    set_marker = " [세트]" if is_set else ""
                    print(f"  ✅ [보고서: {report_option_name}] → {gpt_result['standard_product_name']}{set_marker} "
                          f"(x{gpt_result['quantity_multiplier']}, {gpt_result['brand']}) "
                          f"[신뢰도: {gpt_result['confidence']:.0%}]")

                    # DB에 매핑 저장 (월별보고서_옵션명으로)
                    db.add_mapping(
                        coupang_option_name=report_option_name,
                        standard_product_name=gpt_result["standard_product_name"],
                        quantity_multiplier=gpt_result["quantity_multiplier"],
                        brand=gpt_result["brand"],
                        is_set_product=is_set
                    )

                    # 원가 정보 조회
                    saved_mapping = db.get_mapping_with_set(report_option_name)
                    cost_price = float(saved_mapping.get("cost_price", 0)) if saved_mapping else 0.0

                    df.at[idx, "standard_product_name"] = gpt_result["standard_product_name"]
                    df.at[idx, "brand"] = gpt_result["brand"]
                    df.at[idx, "quantity_multiplier"] = gpt_result["quantity_multiplier"]
                    df.at[idx, "cost_price"] = cost_price
                    df.at[idx, "is_set_product"] = is_set
                    if is_set and saved_mapping and saved_mapping.get("items"):
                        df.at[idx, "set_items"] = saved_mapping["items"]
                else:
                    # 신뢰도 낮거나 실패
                    confidence = gpt_result.get("confidence", 0) if gpt_result else 0
                    suggestion = gpt_result.get("standard_product_name") if gpt_result else None

                    print(f"  ⚠️  [보고서: {report_option_name}] 수동 매핑 필요 (신뢰도: {confidence:.0%})")
                    if suggestion:
                        print(f"      제안: {suggestion}")

                    unmapped_items.append({
                        "option_name": report_option_name,
                        "suggestion": suggestion,
                        "confidence": confidence,
                        "is_set_product": gpt_result.get("is_set_product", False) if gpt_result else False
                    })

        # 매핑되지 않은 항목 처리
        if unmapped_items:
            retry_count += 1
            print(f"\n⚠️  매핑되지 않은 항목: {len(unmapped_items)}건")

            if retry_count < max_retries:
                print("\n❌ 업로드를 중단합니다.")
                print("   DB에 없는 상품이 포함된 데이터는 업로드할 수 없습니다.")

                # 세트상품과 일반상품 구분
                has_set_products = any(p.get("is_set_product", False) for p in unmapped_items)
                has_regular_products = any(not p.get("is_set_product", False) for p in unmapped_items)

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
                        kwargs={"pending_list": unmapped_items, "port": 5001, "debug": False},
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
                    db.close()
                    result["validation"] = {"success": False, "error": "User cancelled"}
                    return {
                        "success": False,
                        "result": result
                    }
                except Exception as e:
                    print(f"\n⚠️  웹 에디터 실행 실패: {e}")
                    print("   수동으로 coupang_product_mapping.py를 사용하여 매핑을 추가하세요.")
                    print("   매핑 완료 후 프로그램을 다시 실행하세요.")
                    db.close()
                    result["validation"] = {"success": False, "error": "Editor failed"}
                    return {
                        "success": False,
                        "result": result
                    }
            else:
                print(f"\n❌ 최대 재시도 횟수({max_retries}회)를 초과했습니다.")
                db.close()
                result["validation"] = {"success": False, "error": "Max retries exceeded"}
                return {
                    "success": False,
                    "result": result
                }
        else:
            print("✅ 모든 상품 매핑 완료!")
            break

    result["validation"] = {"success": True}
    db.close()

    # 3. 데이터 변환
    print(f"\n[3단계] 차이 데이터 변환 중...")

    sales_rows = []
    purchase_rows = []

    for idx, row in df.iterrows():
        # 매핑되지 않은 항목은 스킵
        if not row["standard_product_name"]:
            continue

        # 매출_차이, 판매량_차이
        revenue_diff = float(row.get("매출_차이", 0))
        quantity_diff = int(row.get("판매량_차이", 0))

        if revenue_diff <= 0 or quantity_diff <= 0:
            continue

        # 부가세 역계산 (매출_차이가 부가세 포함 금액이라고 가정)
        total_amount = revenue_diff
        supply_value = int(total_amount / 1.1)  # 공급가액
        vat = int(total_amount - supply_value)  # 부가세

        # 실제 수량 계산
        actual_quantity = quantity_diff * row["quantity_multiplier"]

        # 원가 계산
        cost_price = row["cost_price"]
        total_cost = int(cost_price * actual_quantity)
        cost_supply_amt = int(total_cost / 1.1)
        cost_vat_amt = total_cost - cost_supply_amt

        # 판매 데이터
        sales_rows.append({
            "일자": target_date,
            "브랜드": row["brand"],
            "판매채널": "로켓그로스",
            "거래처명": "로켓그로스",
            "상품명": row["standard_product_name"],
            "수량": actual_quantity,
            "공급가액": supply_value,
            "부가세": vat,
            "단가(vat포함)": supply_value + vat,  # 운반비/수수료 계산용
            "is_set_product": row["is_set_product"],
            "set_items": row["set_items"]
        })

        # 매입 데이터
        purchase_rows.append({
            "일자": target_date,
            "브랜드": row["brand"],
            "판매채널": "로켓그로스",
            "거래처명": "로켓그로스",
            "상품명": row["standard_product_name"],
            "수량": actual_quantity,
            "공급가액": cost_supply_amt,
            "부가세": cost_vat_amt,
            "is_set_product": row["is_set_product"],
            "set_items": row["set_items"]
        })

    sales_df = pd.DataFrame(sales_rows)
    purchase_df = pd.DataFrame(purchase_rows)

    print(f"✅ 판매: {len(sales_df)}건, 매입: {len(purchase_df)}건 변환 완료")

    # 4. 전표 생성
    print(f"\n[4단계] 전표 생성 중...")

    sales_voucher_df = build_sales_voucher(sales_df) if not sales_df.empty else pd.DataFrame()
    cost_voucher_df = build_cost_voucher(purchase_df) if not purchase_df.empty else pd.DataFrame()
    fee_voucher_df = build_voucher_from_sales(sales_df) if not sales_df.empty else pd.DataFrame()

    print(f"✅ 매출전표 {len(sales_voucher_df)}건 생성 완료 (월별 합산)")
    print(f"✅ 원가매입전표 {len(cost_voucher_df)}건 생성 완료 (월별 합산)")
    print(f"✅ 운반비수수료전표 {len(fee_voucher_df)}건 생성 완료")

    result["conversion"] = {
        "success": True,
        "sales_count": len(sales_df),
        "purchase_count": len(purchase_df),
        "sales_voucher_count": len(sales_voucher_df),
        "cost_voucher_count": len(cost_voucher_df),
        "fee_voucher_count": len(fee_voucher_df)
    }

    # 5. 엑셀 저장
    output_filename = f"output_coupang_difference_{target_date}.xlsx"
    save_to_excel(sales_df, purchase_df, sales_voucher_df, cost_voucher_df, fee_voucher_df, output_filename)

    print("\n" + "=" * 80)
    print("처리 완료")
    print("=" * 80)
    print(f"✅ {target_date} 차이 보정 완료")
    print(f"📊 판매: {len(sales_df)}건, 매입: {len(purchase_df)}건")
    print(f"📊 전표: 매출 {len(sales_voucher_df)}건, 원가매입 {len(cost_voucher_df)}건, 운반비/수수료 {len(fee_voucher_df)}건")
    print(f"💾 저장 파일: {output_filename}")
    print("=" * 80)

    return {
        "success": True,
        "sales": sales_df,
        "purchase": purchase_df,
        "sales_voucher": sales_voucher_df,
        "cost_voucher": cost_voucher_df,
        "fee_voucher": fee_voucher_df,
        "result": result
    }


if __name__ == "__main__":
    # 테스트용
    import sys

    if len(sys.argv) < 3:
        print("사용법: python coupang_difference_report.py <엑셀파일경로> <날짜(YYYY-MM-DD)>")
        sys.exit(1)

    excel_file = sys.argv[1]
    target_date = sys.argv[2]

    result = process_coupang_difference_report(excel_file, target_date)

    if result["success"]:
        print("\n✅ 처리 성공!")
    else:
        print("\n❌ 처리 실패!")
