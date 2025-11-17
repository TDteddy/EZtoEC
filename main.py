import os
import requests
import json
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

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
    """날짜를 YYYYMMDD 형식으로 변환 (예: 20180612)"""
    if pd.isna(value) or value is None:
        return ""

    # datetime.date, datetime.datetime, pd.Timestamp 처리
    if isinstance(value, (datetime, pd.Timestamp, date)):
        return value.strftime("%Y%m%d")

    # 문자열 처리
    if isinstance(value, str):
        # 구분자 제거 후 YYYYMMDD 형식으로 변환
        cleaned = value.replace("-", "").replace("/", "").strip()
        if len(cleaned) >= 8:
            return cleaned[:8]
        return value

    # 기타 타입은 문자열로 변환 시도
    str_value = str(value)
    if len(str_value) >= 8:
        cleaned = str_value.replace("-", "").replace("/", "").strip()
        return cleaned[:8]

    return str_value


def convert_sales_df_to_ecount(sales_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    판매 DataFrame을 이카운트 API 형식으로 변환

    전표 묶음 순번: 같은 일자 + 브랜드(프로젝트) + 판매채널(부서)을 가진 행들을 하나의 전표로 묶음

    필드 매핑:
    - IO_DATE: 일자
    - UPLOAD_SER_NO: 순번 (자동 할당: 일자 + 브랜드 + 판매채널 기준)
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

    # 전표 묶음 순번 자동 할당: 일자 + 브랜드 + 판매채널 기준으로 그룹화
    # ngroup()은 0부터 시작하므로 +1하여 1부터 시작하도록 설정
    sales_df_copy = sales_df.copy()
    sales_df_copy["전표묶음순번"] = sales_df_copy.groupby(["일자", "브랜드", "판매채널"]).ngroup() + 1

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

    전표 묶음 순번: 같은 일자 + 브랜드(프로젝트) + 판매채널(부서)을 가진 행들을 하나의 전표로 묶음

    필드 매핑:
    - IO_DATE: 일자
    - UPLOAD_SER_NO: 순번 (자동 할당: 일자 + 브랜드 + 판매채널 기준)
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

    # 전표 묶음 순번 자동 할당: 일자 + 브랜드 + 판매채널 기준으로 그룹화
    # ngroup()은 0부터 시작하므로 +1하여 1부터 시작하도록 설정
    purchase_df_copy = purchase_df.copy()
    purchase_df_copy["전표묶음순번"] = purchase_df_copy.groupby(["일자", "브랜드", "판매채널"]).ngroup() + 1

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


def split_dataframe_into_batches(df: pd.DataFrame, batch_size: int = 300) -> List[pd.DataFrame]:
    """
    DataFrame을 전표번호별로 그룹화하여 배치로 분할

    - 전표는 "일자" + "브랜드" + "판매채널" 기준으로 그룹화
    - 전표가 중간에 끊기지 않도록 처리
    - 한 전표가 300건을 넘으면 그것도 300건씩 분할

    Args:
        df: 판매 또는 구매 DataFrame
        batch_size: 배치당 최대 건수 (기본 300)

    Returns:
        분할된 DataFrame 리스트
    """
    if df.empty:
        return []

    # 일자 + 브랜드 + 판매채널 기준으로 그룹화
    grouped = df.groupby(["일자", "브랜드", "판매채널"], sort=False)

    batches = []
    current_batch = []
    current_size = 0

    for group_key, group_df in grouped:
        group_size = len(group_df)

        # 그룹 자체가 batch_size를 넘으면 분할
        if group_size > batch_size:
            # 현재 배치가 있으면 먼저 저장
            if current_batch:
                batches.append(pd.concat(current_batch, ignore_index=True))
                current_batch = []
                current_size = 0

            # 그룹을 batch_size씩 분할
            for i in range(0, group_size, batch_size):
                chunk = group_df.iloc[i:i+batch_size].copy()
                batches.append(chunk)

        # 현재 배치에 추가하면 batch_size 초과하는 경우
        elif current_size + group_size > batch_size:
            # 현재 배치 저장
            if current_batch:
                batches.append(pd.concat(current_batch, ignore_index=True))
            # 새 배치 시작
            current_batch = [group_df.copy()]
            current_size = group_size

        # 현재 배치에 추가
        else:
            current_batch.append(group_df.copy())
            current_size += group_size

    # 마지막 배치
    if current_batch:
        batches.append(pd.concat(current_batch, ignore_index=True))

    return batches


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


def upload_dataframes_to_ecount(sales_df: pd.DataFrame, purchase_df: pd.DataFrame,
                                 description: str = "") -> dict:
    """
    이미 준비된 DataFrame을 이카운트 API에 업로드

    Args:
        sales_df: 판매 데이터 DataFrame
        purchase_df: 매입 데이터 DataFrame
        description: 업로드 설명 (로그용)

    Returns:
        업로드 결과 딕셔너리
    """
    results = {
        "login": None,
        "sales_upload": None,
        "purchase_upload": None
    }

    # ===== 1단계: 이카운트 로그인 =====
    print(f"\n[1단계] 이카운트 로그인 중...")
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

    # ===== 2단계: 판매 데이터 업로드 =====
    if not sales_df.empty:
        print(f"\n[2단계] 판매 데이터 업로드 중... (총 {len(sales_df)}건)")

        # 전표번호별로 300건씩 배치 분할
        sales_batches = split_dataframe_into_batches(sales_df, batch_size=300)
        total_batches = len(sales_batches)

        if total_batches > 1:
            print(f"  ⚙️  이카운트 API 제한(300건)으로 인해 {total_batches}개 배치로 분할하여 업로드합니다.")

        total_success_cnt = 0
        total_fail_cnt = 0
        all_slip_nos = []

        try:
            for batch_idx, batch_df in enumerate(sales_batches, 1):
                if total_batches > 1:
                    print(f"\n  📤 배치 {batch_idx}/{total_batches} 업로드 중... ({len(batch_df)}건)")

                sale_result = save_sale(
                    session_id=session_id,
                    sales_df=batch_df,
                    zone=ZONE,
                    test=USE_TEST_SERVER
                )

                result_data = sale_result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if total_batches > 1:
                    print(f"     ✅ 배치 {batch_idx} 완료: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                # 실패 상세
                if fail_cnt > 0:
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"     ⚠️ 오류: {detail.get('TotalError', '')}")

            results["sales_upload"] = {
                "success": True,
                "success_count": total_success_cnt,
                "fail_count": total_fail_cnt,
                "slip_nos": all_slip_nos
            }

            print(f"\n✅ 판매 업로드 완료:")
            print(f"  - 성공: {total_success_cnt}건")
            print(f"  - 실패: {total_fail_cnt}건")

        except Exception as e:
            print(f"❌ 판매 업로드 실패: {e}")
            results["sales_upload"] = {"success": False, "error": str(e)}

    # ===== 3단계: 구매 데이터 업로드 =====
    if not purchase_df.empty:
        print(f"\n[3단계] 구매 데이터 업로드 중... (총 {len(purchase_df)}건)")

        purchase_batches = split_dataframe_into_batches(purchase_df, batch_size=300)
        total_batches = len(purchase_batches)

        if total_batches > 1:
            print(f"  ⚙️  이카운트 API 제한(300건)으로 인해 {total_batches}개 배치로 분할하여 업로드합니다.")

        total_success_cnt = 0
        total_fail_cnt = 0
        all_slip_nos = []

        try:
            for batch_idx, batch_df in enumerate(purchase_batches, 1):
                if total_batches > 1:
                    print(f"\n  📤 배치 {batch_idx}/{total_batches} 업로드 중... ({len(batch_df)}건)")

                purchase_result = save_purchase(
                    session_id=session_id,
                    purchase_df=batch_df,
                    zone=ZONE,
                    test=USE_TEST_SERVER
                )

                result_data = purchase_result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if total_batches > 1:
                    print(f"     ✅ 배치 {batch_idx} 완료: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                # 실패 상세
                if fail_cnt > 0:
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"     ⚠️ 오류: {detail.get('TotalError', '')}")

            results["purchase_upload"] = {
                "success": True,
                "success_count": total_success_cnt,
                "fail_count": total_fail_cnt,
                "slip_nos": all_slip_nos
            }

            print(f"\n✅ 구매 업로드 완료:")
            print(f"  - 성공: {total_success_cnt}건")
            print(f"  - 실패: {total_fail_cnt}건")

        except Exception as e:
            print(f"❌ 구매 업로드 실패: {e}")
            results["purchase_upload"] = {"success": False, "error": str(e)}

    return results


def upload_coupang_to_ecount(target_date: str, upload_sales: bool = True,
                              upload_purchase: bool = True, save_excel: bool = True) -> dict:
    """
    쿠팡 로켓그로스 데이터 처리 → 이카운트 API 업로드

    Args:
        target_date: 판매일자 (YYYY-MM-DD)
        upload_sales: 판매 데이터 업로드 여부
        upload_purchase: 매입 데이터 업로드 여부
        save_excel: 엑셀 파일로도 저장할지 여부

    Returns:
        처리 결과 딕셔너리
    """
    from coupang_rocketgrowth import process_coupang_rocketgrowth

    print("=" * 80)
    print(f"쿠팡 로켓그로스 → 이카운트 통합 처리: {target_date}")
    print("=" * 80)

    results = {
        "coupang_processing": None,
        "login": None,
        "sales_upload": None,
        "purchase_upload": None
    }

    # ===== 1단계: 쿠팡 데이터 처리 =====
    print(f"\n[1단계] 쿠팡 로켓그로스 데이터 처리 중...")
    try:
        coupang_result = process_coupang_rocketgrowth(target_date)

        if not coupang_result["result"]["conversion"]["success"]:
            print("❌ 쿠팡 데이터 처리 실패")
            results["coupang_processing"] = {"success": False}
            return results

        sales_df = coupang_result["sales"]
        purchase_df = coupang_result["purchase"]
        voucher_df = coupang_result["voucher"]

        results["coupang_processing"] = {
            "success": True,
            "sales_count": len(sales_df),
            "purchase_count": len(purchase_df),
            "voucher_count": len(voucher_df)
        }

        print(f"✅ 처리 완료:")
        print(f"  - 판매: {len(sales_df)}건")
        print(f"  - 매입: {len(purchase_df)}건")
        print(f"  - 매입전표: {len(voucher_df)}건")

    except Exception as e:
        print(f"❌ 쿠팡 데이터 처리 실패: {e}")
        results["coupang_processing"] = {"success": False, "error": str(e)}
        return results

    # 선택적: 엑셀 파일로 저장은 이미 process_coupang_rocketgrowth에서 완료됨

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
        print(f"\n[3단계] 판매 데이터 업로드 중... (총 {len(sales_df)}건)")

        # 전표번호별로 300건씩 배치 분할
        sales_batches = split_dataframe_into_batches(sales_df, batch_size=300)
        total_batches = len(sales_batches)

        if total_batches > 1:
            print(f"  ⚙️  이카운트 API 제한(300건)으로 인해 {total_batches}개 배치로 분할하여 업로드합니다.")

        total_success_cnt = 0
        total_fail_cnt = 0
        all_slip_nos = []

        try:
            for batch_idx, batch_df in enumerate(sales_batches, 1):
                if total_batches > 1:
                    print(f"\n  📤 배치 {batch_idx}/{total_batches} 업로드 중... ({len(batch_df)}건)")

                sale_result = save_sale(
                    session_id=session_id,
                    sales_df=batch_df,
                    zone=ZONE,
                    test=USE_TEST_SERVER
                )

                result_data = sale_result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if total_batches > 1:
                    print(f"     ✅ 배치 {batch_idx} 완료: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                # 실패 상세
                if fail_cnt > 0:
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"     ⚠️ 오류: {detail.get('TotalError', '')}")

            results["sales_upload"] = {
                "success": True,
                "success_count": total_success_cnt,
                "fail_count": total_fail_cnt,
                "slip_nos": all_slip_nos
            }

            print(f"\n✅ 판매 업로드 완료:")
            print(f"  - 성공: {total_success_cnt}건")
            print(f"  - 실패: {total_fail_cnt}건")

        except Exception as e:
            print(f"❌ 판매 업로드 실패: {e}")
            results["sales_upload"] = {"success": False, "error": str(e)}

    # ===== 4단계: 구매 데이터 업로드 =====
    if upload_purchase and not purchase_df.empty:
        print(f"\n[4단계] 구매 데이터 업로드 중... (총 {len(purchase_df)}건)")

        purchase_batches = split_dataframe_into_batches(purchase_df, batch_size=300)
        total_batches = len(purchase_batches)

        if total_batches > 1:
            print(f"  ⚙️  이카운트 API 제한(300건)으로 인해 {total_batches}개 배치로 분할하여 업로드합니다.")

        total_success_cnt = 0
        total_fail_cnt = 0
        all_slip_nos = []

        try:
            for batch_idx, batch_df in enumerate(purchase_batches, 1):
                if total_batches > 1:
                    print(f"\n  📤 배치 {batch_idx}/{total_batches} 업로드 중... ({len(batch_df)}건)")

                purchase_result = save_purchase(
                    session_id=session_id,
                    purchase_df=batch_df,
                    zone=ZONE,
                    test=USE_TEST_SERVER
                )

                result_data = purchase_result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if total_batches > 1:
                    print(f"     ✅ 배치 {batch_idx} 완료: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                if fail_cnt > 0:
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"     ⚠️ 오류: {detail.get('TotalError', '')}")

            results["purchase_upload"] = {
                "success": True,
                "success_count": total_success_cnt,
                "fail_count": total_fail_cnt,
                "slip_nos": all_slip_nos
            }

            print(f"\n✅ 구매 업로드 완료:")
            print(f"  - 성공: {total_success_cnt}건")
            print(f"  - 실패: {total_fail_cnt}건")

        except Exception as e:
            print(f"❌ 구매 업로드 실패: {e}")
            results["purchase_upload"] = {"success": False, "error": str(e)}

    print("\n" + "=" * 80)
    print("쿠팡 로켓그로스 통합 처리 완료")
    print("=" * 80)

    return results


def fix_upload_from_batch(excel_file: str, data_type: str, start_batch: int) -> dict:
    """
    엑셀 파일에서 데이터를 읽어 특정 배치부터 업로드

    Args:
        excel_file: 엑셀 파일 경로
        data_type: "sales" 또는 "purchase"
        start_batch: 시작 배치 번호 (1부터 시작)

    Returns:
        업로드 결과 딕셔너리
    """
    print("=" * 80)
    print(f"배치 재업로드: {data_type.upper()} (배치 {start_batch}번부터)")
    print("=" * 80)

    results = {
        "login": None,
        "upload": None
    }

    # ===== 1단계: 엑셀 파일 읽기 =====
    print(f"\n[1단계] 엑셀 파일 읽기: {excel_file}")
    try:
        import os
        if not os.path.exists(excel_file):
            print(f"❌ 파일을 찾을 수 없습니다: {excel_file}")
            return results

        # 시트명 결정
        sheet_name = "판매" if data_type == "sales" else "매입"

        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        print(f"✅ {len(df)}건의 데이터 로드 완료")

        if df.empty:
            print("❌ 데이터가 비어있습니다.")
            return results

    except Exception as e:
        print(f"❌ 파일 읽기 실패: {e}")
        return results

    # ===== 2단계: 배치 분할 =====
    print(f"\n[2단계] 배치 분할 중...")
    batches = split_dataframe_into_batches(df, batch_size=300)
    total_batches = len(batches)

    print(f"✅ 총 {total_batches}개 배치로 분할 완료")

    if start_batch > total_batches:
        print(f"❌ 시작 배치 번호({start_batch})가 전체 배치 수({total_batches})를 초과합니다.")
        return results

    # ===== 3단계: 이카운트 로그인 =====
    print(f"\n[3단계] 이카운트 로그인 중...")
    try:
        login_result = login_ecount(
            com_code=COM_CODE,
            user_id=USER_ID,
            api_cert_key=API_CERT_KEY,
            lan_type=LAN_TYPE,
            zone=ZONE,
            test=USE_TEST_SERVER
        )

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

    # ===== 4단계: 특정 배치부터 업로드 =====
    print(f"\n[4단계] 배치 {start_batch}번부터 {total_batches}번까지 업로드 중...")

    total_success_cnt = 0
    total_fail_cnt = 0
    all_slip_nos = []
    failed_batches = []

    try:
        for batch_idx in range(start_batch - 1, total_batches):
            batch_num = batch_idx + 1
            batch_df = batches[batch_idx]

            print(f"\n  📤 배치 {batch_num}/{total_batches} 업로드 중... ({len(batch_df)}건)")

            try:
                if data_type == "sales":
                    result = save_sale(
                        session_id=session_id,
                        sales_df=batch_df,
                        zone=ZONE,
                        test=USE_TEST_SERVER
                    )
                else:  # purchase
                    result = save_purchase(
                        session_id=session_id,
                        purchase_df=batch_df,
                        zone=ZONE,
                        test=USE_TEST_SERVER
                    )

                result_data = result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if fail_cnt > 0:
                    failed_batches.append(batch_num)
                    print(f"     ⚠️  배치 {batch_num}: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                    # 실패 상세
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"         오류: {detail.get('TotalError', '')}")
                else:
                    print(f"     ✅ 배치 {batch_num}: 성공 {success_cnt}건")

            except Exception as e:
                print(f"     ❌ 배치 {batch_num} 업로드 실패: {e}")
                failed_batches.append(batch_num)
                continue

        results["upload"] = {
            "success": len(failed_batches) == 0,
            "success_count": total_success_cnt,
            "fail_count": total_fail_cnt,
            "slip_nos": all_slip_nos,
            "total_batches": total_batches - (start_batch - 1),
            "failed_batches": failed_batches
        }

        print(f"\n" + "=" * 80)
        print("업로드 완료")
        print("=" * 80)
        print(f"배치 범위: {start_batch}번 ~ {total_batches}번")
        print(f"성공: {total_success_cnt}건")
        print(f"실패: {total_fail_cnt}건")
        if failed_batches:
            print(f"⚠️  실패한 배치: {', '.join(map(str, failed_batches))}")

    except Exception as e:
        print(f"❌ 업로드 실패: {e}")
        results["upload"] = {"success": False, "error": str(e)}

    return results


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

    # ===== 1단계: 엑셀 변환 및 데이터 검증 (매핑 완료될 때까지 반복) =====
    sales_df = None
    purchase_df = None
    voucher_df = None
    excel_result = None

    max_retries = 5  # 최대 5번까지 재시도
    for attempt in range(1, max_retries + 1):
        try:
            if attempt == 1:
                print("\n[1단계] 이지어드민 엑셀 파일 변환 및 데이터 검증 중...")
            else:
                print(f"\n[1단계-재시도 {attempt}/{max_retries}] 매핑 후 재검증 중...")

            excel_result, pending_mappings = process_ezadmin_to_ecount()
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

            # ===== 1-1단계: 정제 불가 데이터 처리 (웹 에디터) =====
            if pending_mappings:
                print("\n" + "=" * 80)
                print(f"⚠️  [데이터 검증 실패] DB에 없는 판매처 발견: {len(pending_mappings)}건")
                print("=" * 80)

                unique_sellers = {}
                for p in pending_mappings:
                    original = p.get("original", "")
                    if original not in unique_sellers:
                        unique_sellers[original] = p

                for seller, info in unique_sellers.items():
                    confidence = info.get("confidence", 0)
                    suggestion = info.get("gpt_suggestion")
                    print(f"  - {seller}")
                    if suggestion:
                        print(f"    └ GPT 추천: {suggestion} (신뢰도: {confidence:.0%})")

                print("\n❌ 업로드를 중단합니다.")
                print("   DB에 없는 판매처가 포함된 데이터는 업로드할 수 없습니다.")
                print("\n🌐 웹 에디터를 실행합니다...")
                print("   브라우저에서 http://localhost:5000 접속하여 판매처 이름을 매핑하세요.\n")

                try:
                    from seller_editor import start_editor
                    import threading

                    # 웹 에디터를 백그라운드 스레드로 실행
                    editor_thread = threading.Thread(
                        target=start_editor,
                        args=(list(unique_sellers.values()),),
                        kwargs={"port": 5000},
                        daemon=True
                    )
                    editor_thread.start()

                    # 사용자가 매핑을 완료할 때까지 대기
                    print("⏳ 매핑 완료 후 Enter를 눌러 재검증 및 업로드를 진행하세요...")
                    input()

                    print("\n✅ 매핑을 저장했습니다.")
                    print("   → 데이터를 다시 검증합니다...\n")

                    # 루프를 계속해서 재검증 시도
                    continue

                except KeyboardInterrupt:
                    print("\n⚠️  사용자가 중단했습니다.")
                    return results
                except Exception as e:
                    print(f"\n⚠️  웹 에디터 실행 실패: {e}")
                    print("   수동으로 seller_mapping.py를 사용하여 매핑을 추가하세요.")
                    print("   매핑 완료 후 프로그램을 다시 실행하세요.")
                    return results
            else:
                # 모든 매핑이 완료됨 - 루프 탈출하고 업로드 진행
                print("\n✅ 모든 판매처 검증 완료!")
                break

        except ValueError as e:
            # ValueError는 사용자가 수정해야 하는 데이터 문제 (traceback 불필요)
            # 예: 수동발주 코드10 빈 값
            results["excel_conversion"] = {"success": False, "error": str(e)}
            return results
        except Exception as e:
            print(f"❌ 엑셀 변환 실패: {e}")
            import traceback
            traceback.print_exc()
            results["excel_conversion"] = {"success": False, "error": str(e)}
            return results
    else:
        # 최대 재시도 횟수 초과
        print(f"\n❌ 최대 재시도 횟수({max_retries}회)를 초과했습니다.")
        print("   매핑을 완료한 후 프로그램을 다시 실행하세요.")
        return results

    # 선택적: 엑셀 파일로 저장
    if save_excel and excel_result:
        save_to_excel(excel_result, "output_ecount.xlsx")
        print(f"  - 엑셀 파일 저장: output_ecount.xlsx")

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
        print(f"\n[3단계] 판매 데이터 업로드 중... (총 {len(sales_df)}건)")

        # 전표번호별로 300건씩 배치 분할
        sales_batches = split_dataframe_into_batches(sales_df, batch_size=300)
        total_batches = len(sales_batches)

        if total_batches > 1:
            print(f"  ⚙️  이카운트 API 제한(300건)으로 인해 {total_batches}개 배치로 분할하여 업로드합니다.")
            for i, batch in enumerate(sales_batches, 1):
                print(f"     배치 {i}/{total_batches}: {len(batch)}건")

        # 누적 결과
        total_success_cnt = 0
        total_fail_cnt = 0
        all_slip_nos = []

        try:
            for batch_idx, batch_df in enumerate(sales_batches, 1):
                if total_batches > 1:
                    print(f"\n  📤 배치 {batch_idx}/{total_batches} 업로드 중... ({len(batch_df)}건)")

                sale_result = save_sale(
                    session_id=session_id,
                    sales_df=batch_df,
                    zone=ZONE,
                    test=USE_TEST_SERVER
                )

                # 결과 분석
                result_data = sale_result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if total_batches > 1:
                    print(f"     ✅ 배치 {batch_idx} 완료: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                # 실패 상세
                if fail_cnt > 0:
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"     ⚠️ 오류: {detail.get('TotalError', '')}")

            results["sales_upload"] = {
                "success": True,
                "success_count": total_success_cnt,
                "fail_count": total_fail_cnt,
                "slip_nos": all_slip_nos,
                "batch_count": total_batches
            }

            print(f"\n✅ 판매 업로드 완료:")
            print(f"  - 총 배치 수: {total_batches}개")
            print(f"  - 성공: {total_success_cnt}건")
            print(f"  - 실패: {total_fail_cnt}건")
            if all_slip_nos:
                print(f"  - 전표번호: {', '.join(all_slip_nos[:10])}" +
                      (f" 외 {len(all_slip_nos) - 10}건..." if len(all_slip_nos) > 10 else ""))

        except Exception as e:
            print(f"❌ 판매 업로드 실패: {e}")
            results["sales_upload"] = {"success": False, "error": str(e)}
    elif not sales_df.empty:
        print("\n[3단계] 판매 데이터 업로드 건너뜀 (upload_sales=False)")
    else:
        print("\n[3단계] 판매 데이터가 없습니다. 건너뜁니다.")

    # ===== 4단계: 구매 데이터 업로드 =====
    if upload_purchase and not purchase_df.empty:
        print(f"\n[4단계] 구매 데이터 업로드 중... (총 {len(purchase_df)}건)")

        # 전표번호별로 300건씩 배치 분할
        purchase_batches = split_dataframe_into_batches(purchase_df, batch_size=300)
        total_batches = len(purchase_batches)

        if total_batches > 1:
            print(f"  ⚙️  이카운트 API 제한(300건)으로 인해 {total_batches}개 배치로 분할하여 업로드합니다.")
            for i, batch in enumerate(purchase_batches, 1):
                print(f"     배치 {i}/{total_batches}: {len(batch)}건")

        # 누적 결과
        total_success_cnt = 0
        total_fail_cnt = 0
        all_slip_nos = []

        try:
            for batch_idx, batch_df in enumerate(purchase_batches, 1):
                if total_batches > 1:
                    print(f"\n  📤 배치 {batch_idx}/{total_batches} 업로드 중... ({len(batch_df)}건)")

                purchase_result = save_purchase(
                    session_id=session_id,
                    purchase_df=batch_df,
                    zone=ZONE,
                    test=USE_TEST_SERVER
                )

                # 결과 분석
                result_data = purchase_result.get("Data", {})
                success_cnt = result_data.get("SuccessCnt", 0)
                fail_cnt = result_data.get("FailCnt", 0)
                slip_nos = result_data.get("SlipNos", [])

                total_success_cnt += success_cnt
                total_fail_cnt += fail_cnt
                all_slip_nos.extend(slip_nos)

                if total_batches > 1:
                    print(f"     ✅ 배치 {batch_idx} 완료: 성공 {success_cnt}건, 실패 {fail_cnt}건")

                # 실패 상세
                if fail_cnt > 0:
                    result_details = result_data.get("ResultDetails", [])
                    for detail in result_details:
                        if not detail.get("IsSuccess", False):
                            print(f"     ⚠️ 오류: {detail.get('TotalError', '')}")

            results["purchase_upload"] = {
                "success": True,
                "success_count": total_success_cnt,
                "fail_count": total_fail_cnt,
                "slip_nos": all_slip_nos,
                "batch_count": total_batches
            }

            print(f"\n✅ 구매 업로드 완료:")
            print(f"  - 총 배치 수: {total_batches}개")
            print(f"  - 성공: {total_success_cnt}건")
            print(f"  - 실패: {total_fail_cnt}건")
            if all_slip_nos:
                print(f"  - 전표번호: {', '.join(all_slip_nos[:10])}" +
                      (f" 외 {len(all_slip_nos) - 10}건..." if len(all_slip_nos) > 10 else ""))

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

    # 메뉴 출력
    print("\n" + "=" * 80)
    print("                     EZAdmin → eCount 통합 처리 시스템")
    print("=" * 80)
    print("\n실행할 기능을 선택하세요:")
    print("  1) 이지어드민 업로드")
    print("  2) 쿠팡 업로드")
    print("  3) 누락건 중간배치부터 업로드")
    print("  4) 이카운트 로그인 테스트")
    print()

    choice = input("선택 (1-4): ").strip()

    if choice == "3":
        # 배치 재업로드 모드
        print("=" * 80)
        print("배치 재업로드 (이지어드민)")
        print("=" * 80)

        # 엑셀 파일 경로 입력
        excel_file = input("\n엑셀 파일 경로를 입력하세요: ").strip()

        if not excel_file:
            print("❌ 파일 경로를 입력하지 않았습니다.")
            sys.exit(1)

        # 판매/매입 선택
        print("\n업로드할 데이터 유형을 선택하세요:")
        print("  1) 판매 (sales)")
        print("  2) 매입 (purchase)")

        data_choice = input("\n선택 (1 또는 2): ").strip()

        if data_choice == "1":
            data_type = "sales"
        elif data_choice == "2":
            data_type = "purchase"
        else:
            print("❌ 잘못된 선택입니다.")
            sys.exit(1)

        # 시작 배치 번호 입력
        start_batch_str = input("\n시작 배치 번호를 입력하세요 (1부터 시작): ").strip()

        try:
            start_batch = int(start_batch_str)
            if start_batch < 1:
                print("❌ 배치 번호는 1 이상이어야 합니다.")
                sys.exit(1)
        except ValueError:
            print("❌ 올바른 숫자를 입력하세요.")
            sys.exit(1)

        # 재업로드 실행
        try:
            result = fix_upload_from_batch(excel_file, data_type, start_batch)

            # 결과 요약
            print("\n" + "=" * 80)
            print("최종 결과")
            print("=" * 80)

            if result["login"] and result["login"]["success"]:
                print("✅ 로그인: 성공")

            if result["upload"]:
                upload = result["upload"]
                if upload["success"]:
                    print(f"✅ 업로드: 성공")
                    print(f"   - 총 배치: {upload['total_batches']}개")
                    print(f"   - 성공: {upload['success_count']}건")
                    print(f"   - 실패: {upload['fail_count']}건")
                else:
                    print(f"⚠️  업로드: 일부 실패")
                    print(f"   - 성공: {upload.get('success_count', 0)}건")
                    print(f"   - 실패: {upload.get('fail_count', 0)}건")
                    if upload.get("failed_batches"):
                        print(f"   - 실패 배치: {', '.join(map(str, upload['failed_batches']))}")

        except Exception as e:
            print(f"\n❌ 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif choice == "2":
        # 쿠팡 로켓그로스 처리
        print("=" * 80)
        print("쿠팡 로켓그로스 판매 데이터 처리")
        print("=" * 80)

        # 날짜 입력 받기
        print("\n날짜 입력 방법:")
        print("  1) 단일 날짜: YYYY-MM-DD")
        print("  2) 날짜 범위: YYYY-MM-DD YYYY-MM-DD (시작 종료)")
        date_input = input("\n처리할 날짜를 입력하세요: ").strip()

        if not date_input:
            print("❌ 날짜를 입력하지 않았습니다.")
            sys.exit(1)

        # 공백으로 분리
        dates = date_input.split()
        if len(dates) == 1:
            start_date = dates[0]
            end_date = None
        elif len(dates) == 2:
            start_date = dates[0]
            end_date = dates[1]
        else:
            print("❌ 올바른 날짜 형식이 아닙니다.")
            sys.exit(1)

        try:
            # 날짜 범위인 경우
            if end_date:
                print(f"\n📅 날짜 범위 처리: {start_date} ~ {end_date}")
                from coupang_rocketgrowth import process_coupang_date_range

                # 날짜 범위 처리 (데이터 처리만, 업로드는 하지 않음)
                range_result = process_coupang_date_range(start_date, end_date)

                if not range_result["success"]:
                    print("\n⚠️  일부 날짜 처리 실패")

                # 업로드 진행
                if range_result["dates_processed"]:
                    print("\n" + "=" * 80)
                    print("이카운트 API 업로드 중...")
                    print("=" * 80)

                    # 병합된 데이터 업로드
                    upload_result = upload_dataframes_to_ecount(
                        sales_df=range_result["sales"],
                        purchase_df=range_result["purchase"],
                        description=f"{start_date}~{end_date}"
                    )

                    # 최종 요약
                    print("\n" + "=" * 80)
                    print("처리 결과 요약")
                    print("=" * 80)
                    print(f"📅 날짜 범위: {start_date} ~ {end_date}")
                    print(f"✅ 처리된 날짜: {len(range_result['dates_processed'])}일")

                    if upload_result["login"] and upload_result["login"]["success"]:
                        print(f"✅ 로그인: 성공")

                    if upload_result["sales_upload"]:
                        if upload_result["sales_upload"]["success"]:
                            print(f"✅ 판매 업로드: {upload_result['sales_upload']['success_count']}건 성공")
                        else:
                            print(f"❌ 판매 업로드: 실패")

                    if upload_result["purchase_upload"]:
                        if upload_result["purchase_upload"]["success"]:
                            print(f"✅ 구매 업로드: {upload_result['purchase_upload']['success_count']}건 성공")
                        else:
                            print(f"❌ 구매 업로드: 실패")

            # 단일 날짜인 경우
            else:
                print(f"\n📅 단일 날짜 처리: {start_date}")
                results = upload_coupang_to_ecount(start_date)

                # 최종 요약
                print("\n" + "=" * 80)
                print("처리 결과 요약")
                print("=" * 80)

                if results["coupang_processing"] and results["coupang_processing"]["success"]:
                    print(f"✅ 쿠팡 데이터 처리: 성공")

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
            import traceback
            traceback.print_exc()
            sys.exit(1)

    elif choice == "1":
        # 이지어드민 업로드
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

    elif choice == "4":
        # 로그인 테스트
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

            # 전체 응답 출력 (디버깅용)
            print("\n[디버깅] 전체 API 응답:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

            # SESSION_ID 추출
            data = result.get("Data", {}) or {}
            datas = data.get("Datas", {}) or {}
            session_id = datas.get("SESSION_ID")

            if session_id:
                print(f"\n✅ 로그인 성공")
                print(f"SESSION_ID: {session_id}")
            else:
                print("\n❌ SESSION_ID를 찾을 수 없습니다.")
                print("응답 구조를 확인하세요:")
                print(f"  - Data 존재: {bool(data)}")
                print(f"  - Datas 존재: {bool(datas)}")
                if datas:
                    print(f"  - Datas 키 목록: {list(datas.keys())}")

        except Exception as e:
            print(f"\n❌ 로그인 실패: {e}")

    else:
        print("\n❌ 잘못된 선택입니다. 1, 2, 3, 4 중 하나를 선택하세요.")
        sys.exit(1)
