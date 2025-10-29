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

    필드 매핑:
    - IO_DATE: 일자
    - UPLOAD_SER_NO: 순번
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
    sale_list = []

    for _, row in sales_df.iterrows():
        bulk_data = {
            "IO_DATE": safe_date(row.get("일자")),
            "UPLOAD_SER_NO": safe_str(row.get("순번")),
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

    필드 매핑:
    - IO_DATE: 일자
    - UPLOAD_SER_NO: 순번
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
    purchase_list = []

    for _, row in purchase_df.iterrows():
        bulk_data = {
            "ORD_DATE": "",  # 발주일자
            "ORD_NO": "",  # 발주번호
            "IO_DATE": safe_date(row.get("일자")),
            "UPLOAD_SER_NO": safe_str(row.get("순번")),
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


if __name__ == "__main__":
    try:
        result = login_ecount(
            com_code=COM_CODE,
            user_id=USER_ID,
            api_cert_key=API_CERT_KEY,
            lan_type=LAN_TYPE,
            zone=ZONE,
            test=USE_TEST_SERVER,
        )

        # 전체 결과 출력
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # SESSION_ID 추출
        data = result.get("Data", {}) or {}
        datas = data.get("Datas", {}) or {}
        session_id = datas.get("SESSION_ID")

        if session_id:
            print("\n✨ SESSION_ID:", session_id)
        else:
            print("\nSESSION_ID를 찾을 수 없습니다. 응답 구조를 확인하세요.")

    except Exception as e:
        print("로그인 실패:", e)
