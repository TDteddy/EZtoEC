"""
통합 실행 예제: 이지어드민 엑셀 변환 → 이카운트 API 업로드

사용 흐름:
1. 이지어드민 엑셀 파일을 data/ 폴더에 저장
2. 엑셀 파일을 이카운트 형식으로 변환
3. 이카운트 로그인
4. 판매/구매 데이터를 이카운트 API로 전송
"""

import os
from excel_converter import process_ezadmin_to_ecount, save_to_excel
from main import login_ecount, save_sale, save_purchase

# ===== 설정 =====
# 환경 변수에서 로드
USER_ID = os.environ.get("ECOUNT_USER_ID")
API_CERT_KEY = os.environ.get("ECOUNT_API_CERT_KEY")
COM_CODE = os.environ.get("ECOUNT_COM_CODE")
LAN_TYPE = os.environ.get("ECOUNT_LAN_TYPE", "ko-KR")
ZONE = "AD"
USE_TEST_SERVER = True  # 테스트 서버 사용


def main():
    print("=" * 80)
    print("이지어드민 → 이카운트 통합 처리 시작")
    print("=" * 80)

    # ===== 1단계: 엑셀 변환 =====
    print("\n[1단계] 이지어드민 엑셀 파일 변환 중...")
    try:
        result = process_ezadmin_to_ecount()

        sales_df = result["sales"]
        purchase_df = result["purchase"]
        voucher_df = result["voucher"]

        print(f"✅ 변환 완료:")
        print(f"  - 판매: {len(sales_df)}건")
        print(f"  - 매입: {len(purchase_df)}건")
        print(f"  - 매입전표: {len(voucher_df)}건")

        # 선택적: 엑셀 파일로 저장
        save_to_excel(result, "output_ecount.xlsx")

    except Exception as e:
        print(f"❌ 엑셀 변환 실패: {e}")
        return

    # ===== 2단계: 이카운트 로그인 =====
    print("\n[2단계] 이카운트 로그인 중...")
    try:
        login_result = login_ecount(
            com_code=COM_CODE,
            user_id=USER_ID,
            api_cert_key=API_CERT_KEY,
            lan_type=LAN_TYPE,
            zone=ZONE,
            test=USE_TEST_SERVER
        )

        # SESSION_ID 추출
        data = login_result.get("Data", {}) or {}
        datas = data.get("Datas", {}) or {}
        session_id = datas.get("SESSION_ID")

        if not session_id:
            print("❌ SESSION_ID를 찾을 수 없습니다.")
            return

        print(f"✅ 로그인 성공: SESSION_ID={session_id}")

    except Exception as e:
        print(f"❌ 로그인 실패: {e}")
        return

    # ===== 3단계: 판매 데이터 업로드 =====
    if not sales_df.empty:
        print(f"\n[3단계] 판매 데이터 업로드 중... ({len(sales_df)}건)")
        try:
            sale_result = save_sale(
                session_id=session_id,
                sales_df=sales_df,
                zone=ZONE,
                test=USE_TEST_SERVER
            )

            # 결과 분석
            result_data = sale_result.get("Data", {})
            success_cnt = result_data.get("SuccessCnt", 0)
            fail_cnt = result_data.get("FailCnt", 0)
            slip_nos = result_data.get("SlipNos", [])

            print(f"✅ 판매 업로드 완료:")
            print(f"  - 성공: {success_cnt}건")
            print(f"  - 실패: {fail_cnt}건")
            if slip_nos:
                print(f"  - 전표번호: {', '.join(slip_nos)}")

            # 실패 상세
            if fail_cnt > 0:
                result_details = result_data.get("ResultDetails", [])
                for detail in result_details:
                    if not detail.get("IsSuccess", False):
                        print(f"  ⚠️ 오류: {detail.get('TotalError', '')}")

        except Exception as e:
            print(f"❌ 판매 업로드 실패: {e}")
    else:
        print("\n[3단계] 판매 데이터가 없습니다. 건너뜁니다.")

    # ===== 4단계: 구매 데이터 업로드 =====
    if not purchase_df.empty:
        print(f"\n[4단계] 구매 데이터 업로드 중... ({len(purchase_df)}건)")
        try:
            purchase_result = save_purchase(
                session_id=session_id,
                purchase_df=purchase_df,
                zone=ZONE,
                test=USE_TEST_SERVER
            )

            # 결과 분석
            result_data = purchase_result.get("Data", {})
            success_cnt = result_data.get("SuccessCnt", 0)
            fail_cnt = result_data.get("FailCnt", 0)
            slip_nos = result_data.get("SlipNos", [])

            print(f"✅ 구매 업로드 완료:")
            print(f"  - 성공: {success_cnt}건")
            print(f"  - 실패: {fail_cnt}건")
            if slip_nos:
                print(f"  - 전표번호: {', '.join(slip_nos)}")

            # 실패 상세
            if fail_cnt > 0:
                result_details = result_data.get("ResultDetails", [])
                for detail in result_details:
                    if not detail.get("IsSuccess", False):
                        print(f"  ⚠️ 오류: {detail.get('TotalError', '')}")

        except Exception as e:
            print(f"❌ 구매 업로드 실패: {e}")
    else:
        print("\n[4단계] 구매 데이터가 없습니다. 건너뜁니다.")

    # ===== 완료 =====
    print("\n" + "=" * 80)
    print("통합 처리 완료")
    print("=" * 80)


if __name__ == "__main__":
    # 환경 변수 확인
    if not all([USER_ID, API_CERT_KEY, COM_CODE]):
        print("❌ 환경 변수가 설정되지 않았습니다.")
        print("다음 환경 변수를 설정하세요:")
        print("  - ECOUNT_USER_ID")
        print("  - ECOUNT_API_CERT_KEY")
        print("  - ECOUNT_COM_CODE")
        print("\n예시:")
        print("  export ECOUNT_USER_ID='your-user-id'")
        print("  export ECOUNT_API_CERT_KEY='your-api-key'")
        print("  export ECOUNT_COM_CODE='your-company-code'")
        exit(1)

    main()
