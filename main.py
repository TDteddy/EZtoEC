import os
import requests
import json

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
