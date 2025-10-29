import os
import requests
import json
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime

# ===== 설정값 =====
ZONE = "AD"  # 불변
USE_TEST_SERVER = True  # True면 sboapiAD, False면 oapiAD 로 접속

# 발급 정보 - 환경 변수에서 로드
# 사용법: export ECOUNT_USER_ID="your-user-id"
USER_ID = os.environ.get("ECOUNT_USER_ID")
API_CERT_KEY = os.environ.get("ECOUNT_API_CERT_KEY")

# 로그인 파라미터
COM_CODE = os.environ.get("ECOUNT_COM_CODE")      # 회사코드
LAN_TYPE = os.environ.get("ECOUNT_LAN_TYPE", "ko-KR")      # 언어 (기본: ko-KR)


def build_login_url(zone: str, test: bool = False) -> str:
    """
    zone = "AD" 고정. test=True면 sboapi{ZONE}, 아니면 oapi{ZONE}.
    """
    sub = "sboapi" if test else "oapi"
    return f"https://{sub}{zone}.ecount.com/OAPI/V2/OAPILogin"


def login_ecount(com_code: str, user_id: str, api_cert_key: str,
                 lan_type: str = "ko-KR", zone: str = "AD", test: bool = False,
                 timeout: int = 15) -> dict:
    """
    이카운트 로그인 API 호출.
    성공 시 전체 JSON을 반환하며, session_id는 result['Data']['Datas']['SESSION_ID']에 존재.
    실패 시 상세 에러를 포함한 예외를 발생.
    """
    url = build_login_url(zone, test)

    headers = {
        "Content-Type": "application/json"
        # 로그인 API는 본문에 USER_ID / API_CERT_KEY를 포함하므로 별도 Authorization 헤더 불필요
    }

    payload = {
        "COM_CODE": com_code,
        "USER_ID": user_id,
        "API_CERT_KEY": api_cert_key,
        "LAN_TYPE": lan_type,
        "ZONE": zone,  # 명세상 본문에도 ZONE 전달
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

    # HTTP 레벨 에러 체크
    if resp.status_code != 200:
        raise RuntimeError(f"[HTTP {resp.status_code}] {resp.text}")

    # JSON 파싱
    try:
        result = resp.json()
    except json.JSONDecodeError:
        raise RuntimeError("응답이 JSON 형식이 아닙니다:\n" + resp.text)

    # API 레벨 에러 체크 (Status / Error 규칙)
    status = str(result.get("Status"))
    error = result.get("Error")

    if status != "200" or error:
        code = None if not error else error.get("Code")
        msg = None if not error else error.get("Message")
        detail = None if not error else error.get("MessageDetail")
        raise RuntimeError(f"[API Error] Status={status}, Code={code}, Message={msg}, Detail={detail}")

    return result


def build_api_url(endpoint: str, session_id: str, zone: str = "AD", test: bool = False) -> str:
    """
    이카운트 API URL 생성

    Args:
        endpoint: API 엔드포인트 (예: "Sale/SaveSale", "Purchases/SavePurchases")
        session_id: 로그인 후 받은 세션 ID
        zone: Zone 정보 (기본: AD)
        test: 테스트 서버 사용 여부

    Returns:
        완전한 API URL
    """
    sub = "sboapi" if test else "oapi"
    return f"https://{sub}{zone}.ecount.com/OAPI/V2/{endpoint}?SESSION_ID={session_id}"


def safe_str(value: Any) -> str:
    """안전하게 문자열로 변환"""
    if pd.isna(value) or value is None:
        return ""
    return str(value)


def safe_date(value: Any) -> str:
    """날짜를 YYYYMMDD 형식으로 변환"""
    if pd.isna(value) or value is None:
        return ""
    if isinstance(value, str):
        # 이미 문자열인 경우 그대로 반환 (또는 파싱 시도)
        return value.replace("-", "").replace("/", "")[:8]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y%m%d")
    return str(value)[:8]


def convert_sales_df_to_ecount(sales_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    판매 DataFrame을 이카운트 API 형식으로 변환

    전표 묶음 순번: 같은 브랜드(프로젝트) + 판매채널(부서)을 가진 행들을 하나의 전표로 묶음

    필드 매핑:
    - IO_DATE: 일자
    - UPLOAD_SER_NO: 순번 (자동 할당: 브랜드 + 판매채널 기준)
    - PJT_CD: 브랜드 (프로젝트)
    - SITE: 판매채널 (부서)
    - CUST_DES: 거래처명
    - WH_CD: 출하창고
    - ADD_TXT_03: 주문번호
    - PROD_CD: 상품코드 (품목코드)
    - PROD_DES: 품목명
    - ADD_TXT_04: 옵션
    - QTY: 수량
    - USER_PRICE_VAT: 단가(vat포함)
    - SUPPLY_AMT: 공급가액
    - VAT_AMT: 부가세
    - REMARKS: 송장번호
    - ADD_TXT_01: 수령자주소
    - P_REMARKS1: 수령자이름
    - P_REMARKS2: 수령자전화
    - P_REMARKS3: 수령자휴대폰
    - ADD_TXT_02: 배송메모
    - ADD_TXT_05: 주문상세번호
    """
    if sales_df.empty:
        return []

    # 전표 묶음 순번 자동 할당: 브랜드 + 판매채널 기준으로 그룹화
    # ngroup()은 0부터 시작하므로 +1하여 1부터 시작하도록 설정
    sales_df_copy = sales_df.copy()
    sales_df_copy["전표묶음순번"] = sales_df_copy.groupby(["브랜드", "판매채널"]).ngroup() + 1

    sale_list = []

    for _, row in sales_df_copy.iterrows():
        bulk_data = {
            "IO_DATE": safe_date(row.get("일자")),
            "UPLOAD_SER_NO": str(int(row.get("전표묶음순번"))),  # 그룹 순번 (1부터 시작)
            "CUST": "",  # 거래처코드 (없음)
            "CUST_DES": safe_str(row.get("거래처명")),
            "EMP_CD": "",  # 담당자
            "WH_CD": safe_str(row.get("출하창고")),
            "IO_TYPE": "",  # 거래유형
            "EXCHANGE_TYPE": "",  # 외화종류
            "EXCHANGE_RATE": "",  # 환율
            "SITE": safe_str(row.get("판매채널")),  # 부서
            "PJT_CD": safe_str(row.get("브랜드")),  # 프로젝트
            "DOC_NO": "",  # 판매No.
            "TTL_CTT": "",  # 제목
            "U_MEMO1": "",
            "U_MEMO2": "",
            "U_MEMO3": "",
            "U_MEMO4": "",
            "U_MEMO5": "",
            "ADD_TXT_01": safe_str(row.get("수령자주소")),  # 추가문자형식1
            "ADD_TXT_02": safe_str(row.get("배송메모")),  # 추가문자형식2
            "ADD_TXT_03": safe_str(row.get("주문번호")),  # 추가문자형식3
            "ADD_TXT_04": safe_str(row.get("옵션")),  # 추가문자형식4
            "ADD_TXT_05": safe_str(row.get("주문상세번호")),  # 추가문자형식5
            "ADD_TXT_06": "",
            "ADD_TXT_07": "",
            "ADD_TXT_08": "",
            "ADD_TXT_09": "",
            "ADD_TXT_10": "",
            "U_TXT1": "",  # 장문형식1
            "PROD_CD": safe_str(row.get("상품코드")),  # 품목코드
            "PROD_DES": safe_str(row.get("품목명")),
            "SIZE_DES": safe_str(row.get("규격")),
            "UQTY": "",  # 추가수량
            "QTY": safe_str(row.get("수량")),
            "PRICE": safe_str(row.get("단가")),
            "USER_PRICE_VAT": safe_str(row.get("단가(vat포함)")),
            "SUPPLY_AMT": safe_str(row.get("공급가액")),
            "SUPPLY_AMT_F": "",  # 외화금액
            "VAT_AMT": safe_str(row.get("부가세")),
            "REMARKS": safe_str(row.get("송장번호")),  # 적요
            "ITEM_CD": "",  # 관리항목
            "P_REMARKS1": safe_str(row.get("수령자이름")),  # 적요1
            "P_REMARKS2": safe_str(row.get("수령자전화")),  # 적요2
            "P_REMARKS3": safe_str(row.get("수령자휴대폰")),  # 적요3
            "P_AMT1": "",
            "P_AMT2": "",
        }

        sale_list.append({"BulkDatas": bulk_data})

    return sale_list


def convert_purchase_df_to_ecount(purchase_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    매입 DataFrame을 이카운트 API 형식으로 변환

    전표 묶음 순번: 같은 브랜드(프로젝트) + 판매채널(부서)을 가진 행들을 하나의 전표로 묶음

    필드 매핑:
    - IO_DATE: 일자
    - UPLOAD_SER_NO: 순번 (자동 할당: 브랜드 + 판매채널 기준)
    - PJT_CD: 브랜드 (프로젝트)
    - SITE: 판매채널 (부서)
    - CUST_DES: 거래처명
    - WH_CD: 입고창고
    - PROD_DES: 품목명
    - QTY: 수량
    - PRICE: 단가
    - SUPPLY_AMT: 공급가액
    - VAT_AMT: 부가세
    - REMARKS: 적요
    """
    if purchase_df.empty:
        return []

    # 전표 묶음 순번 자동 할당: 브랜드 + 판매채널 기준으로 그룹화
    # ngroup()은 0부터 시작하므로 +1하여 1부터 시작하도록 설정
    purchase_df_copy = purchase_df.copy()
    purchase_df_copy["전표묶음순번"] = purchase_df_copy.groupby(["브랜드", "판매채널"]).ngroup() + 1

    purchase_list = []

    for _, row in purchase_df_copy.iterrows():
        bulk_data = {
            "ORD_DATE": "",  # 발주일자
            "ORD_NO": "",  # 발주번호
            "IO_DATE": safe_date(row.get("일자")),
            "UPLOAD_SER_NO": str(int(row.get("전표묶음순번"))),  # 그룹 순번 (1부터 시작)
            "CUST": "",  # 거래처코드
            "CUST_DES": safe_str(row.get("거래처명")),
            "EMP_CD": "",  # 담당자
            "WH_CD": safe_str(row.get("입고창고")),
            "IO_TYPE": "",  # 거래유형
            "EXCHANGE_TYPE": "",  # 외화종류
            "EXCHANGE_RATE": "",  # 환율
            "SITE": safe_str(row.get("판매채널")),  # 부서
            "PJT_CD": safe_str(row.get("브랜드")),  # 프로젝트
            "DOC_NO": "",  # 구매No.
            "U_MEMO1": "",
            "U_MEMO2": "",
            "U_MEMO3": "",
            "U_MEMO4": "",
            "U_MEMO5": "",
            "U_TXT1": "",  # 장문형식1
            "TTL_CTT": "",  # 제목
            "PROD_CD": safe_str(row.get("품목코드")),
            "PROD_DES": safe_str(row.get("품목명")),
            "SIZE_DES": safe_str(row.get("규격명")),
            "UQTY": "",  # 추가수량
            "QTY": safe_str(row.get("수량")),
            "PRICE": safe_str(row.get("단가")),
            "USER_PRICE_VAT": "",
            "SUPPLY_AMT": safe_str(row.get("공급가액")),
            "SUPPLY_AMT_F": "",  # 외화금액
            "VAT_AMT": safe_str(row.get("부가세")),
            "REMARKS": safe_str(row.get("적요")),
            "ITEM_CD": "",  # 관리항목
            "P_AMT1": "",
            "P_AMT2": "",
            "P_REMARKS1": "",
            "P_REMARKS2": "",
            "P_REMARKS3": "",
            "CUST_AMT": "",  # 부대비용
        }

        purchase_list.append({"BulkDatas": bulk_data})

    return purchase_list


def save_sale(session_id: str, sales_df: pd.DataFrame,
              zone: str = "AD", test: bool = False, timeout: int = 30) -> dict:
    """
    판매 데이터를 이카운트 API로 전송

    Args:
        session_id: 로그인 후 받은 세션 ID
        sales_df: 판매 DataFrame
        zone: Zone 정보
        test: 테스트 서버 사용 여부
        timeout: 타임아웃 (초)

    Returns:
        API 응답 결과
    """
    url = build_api_url("Sale/SaveSale", session_id, zone, test)

    # DataFrame을 이카운트 형식으로 변환
    sale_list = convert_sales_df_to_ecount(sales_df)

    payload = {"SaleList": sale_list}
    headers = {"Content-Type": "application/json"}

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

    # HTTP 레벨 에러 체크
    if resp.status_code != 200:
        raise RuntimeError(f"[HTTP {resp.status_code}] {resp.text}")

    # JSON 파싱
    try:
        result = resp.json()
    except json.JSONDecodeError:
        raise RuntimeError("응답이 JSON 형식이 아닙니다:\n" + resp.text)

    # API 레벨 에러 체크
    status = str(result.get("Status"))
    error = result.get("Error")

    if status != "200" or error:
        code = None if not error else error.get("Code")
        msg = None if not error else error.get("Message")
        detail = None if not error else error.get("MessageDetail")
        raise RuntimeError(f"[API Error] Status={status}, Code={code}, Message={msg}, Detail={detail}")

    return result


def save_purchase(session_id: str, purchase_df: pd.DataFrame,
                  zone: str = "AD", test: bool = False, timeout: int = 30) -> dict:
    """
    구매 데이터를 이카운트 API로 전송

    Args:
        session_id: 로그인 후 받은 세션 ID
        purchase_df: 구매 DataFrame
        zone: Zone 정보
        test: 테스트 서버 사용 여부
        timeout: 타임아웃 (초)

    Returns:
        API 응답 결과
    """
    url = build_api_url("Purchases/SavePurchases", session_id, zone, test)

    # DataFrame을 이카운트 형식으로 변환
    purchase_list = convert_purchase_df_to_ecount(purchase_df)

    payload = {"PurchasesList": purchase_list}
    headers = {"Content-Type": "application/json"}

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

    # HTTP 레벨 에러 체크
    if resp.status_code != 200:
        raise RuntimeError(f"[HTTP {resp.status_code}] {resp.text}")

    # JSON 파싱
    try:
        result = resp.json()
    except json.JSONDecodeError:
        raise RuntimeError("응답이 JSON 형식이 아닙니다:\n" + resp.text)

    # API 레벨 에러 체크
    status = str(result.get("Status"))
    error = result.get("Error")

    if status != "200" or error:
        code = None if not error else error.get("Code")
        msg = None if not error else error.get("Message")
        detail = None if not error else error.get("MessageDetail")
        raise RuntimeError(f"[API Error] Status={status}, Code={code}, Message={msg}, Detail={detail}")

    return result


def process_and_upload(upload_sales: bool = True, upload_purchase: bool = True,
                       save_excel: bool = True) -> dict:
    """
    이지어드민 엑셀 변환 → 이카운트 API 업로드 통합 처리

    Args:
        upload_sales: 판매 데이터 업로드 여부
        upload_purchase: 구매 데이터 업로드 여부
        save_excel: 엑셀 파일로도 저장할지 여부

    Returns:
        처리 결과 딕셔너리
    """
    from excel_converter import process_ezadmin_to_ecount, save_to_excel

    print("=" * 80)
    print("이지어드민 → 이카운트 통합 처리 시작")
    print("=" * 80)

    results = {
        "excel_conversion": None,
        "login": None,
        "sales_upload": None,
        "purchase_upload": None
    }

    # ===== 1단계: 엑셀 변환 =====
    print("\n[1단계] 이지어드민 엑셀 파일 변환 중...")
    try:
        excel_result = process_ezadmin_to_ecount()
        sales_df = excel_result["sales"]
        purchase_df = excel_result["purchase"]
        voucher_df = excel_result["voucher"]

        results["excel_conversion"] = {
            "success": True,
            "sales_count": len(sales_df),
            "purchase_count": len(purchase_df),
            "voucher_count": len(voucher_df)
        }

        print(f"✅ 변환 완료:")
        print(f"  - 판매: {len(sales_df)}건")
        print(f"  - 매입: {len(purchase_df)}건")
        print(f"  - 매입전표: {len(voucher_df)}건")

        # 선택적: 엑셀 파일로 저장
        if save_excel:
            save_to_excel(excel_result, "output_ecount.xlsx")
            print(f"  - 엑셀 파일 저장: output_ecount.xlsx")

    except Exception as e:
        print(f"❌ 엑셀 변환 실패: {e}")
        results["excel_conversion"] = {"success": False, "error": str(e)}
        return results

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
            results["login"] = {"success": False, "error": "No SESSION_ID"}
            return results

        results["login"] = {"success": True, "session_id": session_id}
        print(f"✅ 로그인 성공: SESSION_ID={session_id[:20]}...")

    except Exception as e:
        print(f"❌ 로그인 실패: {e}")
        results["login"] = {"success": False, "error": str(e)}
        return results

    # ===== 3단계: 판매 데이터 업로드 =====
    if upload_sales and not sales_df.empty:
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

            results["sales_upload"] = {
                "success": True,
                "success_count": success_cnt,
                "fail_count": fail_cnt,
                "slip_nos": slip_nos
            }

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
            results["sales_upload"] = {"success": False, "error": str(e)}
    elif not sales_df.empty:
        print("\n[3단계] 판매 데이터 업로드 건너뜀 (upload_sales=False)")
    else:
        print("\n[3단계] 판매 데이터가 없습니다. 건너뜁니다.")

    # ===== 4단계: 구매 데이터 업로드 =====
    if upload_purchase and not purchase_df.empty:
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

            results["purchase_upload"] = {
                "success": True,
                "success_count": success_cnt,
                "fail_count": fail_cnt,
                "slip_nos": slip_nos
            }

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
            results["purchase_upload"] = {"success": False, "error": str(e)}
    elif not purchase_df.empty:
        print("\n[4단계] 구매 데이터 업로드 건너뜀 (upload_purchase=False)")
    else:
        print("\n[4단계] 구매 데이터가 없습니다. 건너뜁니다.")

    # ===== 완료 =====
    print("\n" + "=" * 80)
    print("통합 처리 완료")
    print("=" * 80)

    return results


if __name__ == "__main__":
    import sys

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
        sys.exit(1)

    # 명령행 인자 처리
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "login":
        # 로그인만 테스트
        print("=" * 80)
        print("이카운트 로그인 테스트")
        print("=" * 80)
        try:
            result = login_ecount(
                com_code=COM_CODE,
                user_id=USER_ID,
                api_cert_key=API_CERT_KEY,
                lan_type=LAN_TYPE,
                zone=ZONE,
                test=USE_TEST_SERVER,
            )

            # SESSION_ID 추출
            data = result.get("Data", {}) or {}
            datas = data.get("Datas", {}) or {}
            session_id = datas.get("SESSION_ID")

            if session_id:
                print(f"\n✅ 로그인 성공")
                print(f"SESSION_ID: {session_id}")
            else:
                print("\n❌ SESSION_ID를 찾을 수 없습니다. 응답 구조를 확인하세요.")

        except Exception as e:
            print(f"\n❌ 로그인 실패: {e}")

    elif mode == "convert":
        # 엑셀 변환만 수행
        print("=" * 80)
        print("이지어드민 엑셀 변환")
        print("=" * 80)
        from excel_converter import process_ezadmin_to_ecount, save_to_excel
        try:
            result = process_ezadmin_to_ecount()
            save_to_excel(result, "output_ecount.xlsx")
            print(f"\n✅ 변환 완료:")
            print(f"  - 판매: {len(result['sales'])}건")
            print(f"  - 매입: {len(result['purchase'])}건")
            print(f"  - 매입전표: {len(result['voucher'])}건")
        except Exception as e:
            print(f"\n❌ 변환 실패: {e}")

    else:
        # 통합 처리 (기본)
        try:
            results = process_and_upload()

            # 최종 요약
            print("\n" + "=" * 80)
            print("처리 결과 요약")
            print("=" * 80)

            if results["excel_conversion"] and results["excel_conversion"]["success"]:
                print(f"✅ 엑셀 변환: 성공")

            if results["login"] and results["login"]["success"]:
                print(f"✅ 로그인: 성공")

            if results["sales_upload"]:
                if results["sales_upload"]["success"]:
                    print(f"✅ 판매 업로드: {results['sales_upload']['success_count']}건 성공")
                else:
                    print(f"❌ 판매 업로드: 실패")

            if results["purchase_upload"]:
                if results["purchase_upload"]["success"]:
                    print(f"✅ 구매 업로드: {results['purchase_upload']['success_count']}건 성공")
                else:
                    print(f"❌ 구매 업로드: 실패")

        except Exception as e:
            print(f"\n❌ 처리 실패: {e}")
            sys.exit(1)
