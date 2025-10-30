"""
판매처 이름 통일 관리 시스템

같은 판매처를 여러 이름으로 부르는 경우 표준 이름으로 통합:
- "지마켓", "G마켓", "gmarket" → "G마켓"
- "카카오", "선물하기", "카카오선물하기" → "카카오선물하기"

MySQL 기반 DB로 매핑 정보 관리
"""

import mysql.connector
from mysql.connector import Error
import os
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===== 설정 =====
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "seller_mapping")


class SellerMappingDB:
    """판매처 이름 매핑 관리 클래스"""

    def __init__(self, host: str = DB_HOST, user: str = DB_USER,
                 password: str = DB_PASSWORD, database: str = DB_NAME):
        """
        Args:
            host: MySQL 호스트
            user: MySQL 사용자
            password: MySQL 비밀번호
            database: 데이터베이스 이름
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """컨텍스트 매니저: with 문 지원"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저: 자동 종료"""
        self.close()

    def connect(self):
        """DB 연결 및 데이터베이스/테이블 자동 생성"""
        try:
            # 먼저 DB 없이 연결하여 데이터베이스 생성
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            self.cursor = self.conn.cursor(dictionary=True)

            # 데이터베이스가 없으면 생성
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            self.cursor.execute(f"USE {self.database}")

            # 테이블이 없으면 자동 생성
            self._ensure_table_exists()

            print(f"✅ 데이터베이스 연결: {self.database}")
        except Error as e:
            print(f"❌ DB 연결 실패: {e}")
            raise

    def _ensure_table_exists(self):
        """테이블 존재 확인 및 자동 생성"""
        try:
            # 테이블 존재 확인
            self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'seller_mapping'
            """, (self.database,))

            result = self.cursor.fetchone()

            if result['count'] == 0:
                # 테이블이 없으면 생성
                print(f"[INFO] 테이블이 없습니다. 자동 생성 중...")
                create_table_sql = """
                CREATE TABLE seller_mapping (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    alias VARCHAR(255) NOT NULL UNIQUE,
                    standard_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_alias (alias),
                    INDEX idx_standard (standard_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                self.cursor.execute(create_table_sql)
                self.conn.commit()
                print(f"✅ 테이블 생성 완료")
        except Exception as e:
            print(f"⚠️  테이블 확인/생성 중 오류: {e}")
            # 치명적이지 않으므로 계속 진행

    def close(self):
        """DB 연결 종료"""
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def init_db(self):
        """
        DB 초기화: 테이블 생성

        테이블 구조:
        - seller_mapping: 판매처 이름 매핑
          - id: 자동 증가 ID
          - alias: 원본/별칭 이름
          - standard_name: 표준 이름
          - created_at: 생성 시각
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS seller_mapping (
            id INT AUTO_INCREMENT PRIMARY KEY,
            alias VARCHAR(255) NOT NULL UNIQUE,
            standard_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_alias (alias),
            INDEX idx_standard (standard_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        self.cursor.execute(create_table_sql)
        self.conn.commit()
        print(f"✅ DB 초기화 완료: {self.database}")

    def add_mapping(self, alias: str, standard_name: str) -> bool:
        """
        판매처 매핑 추가

        Args:
            alias: 원본/별칭 이름
            standard_name: 표준 이름

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                "INSERT INTO seller_mapping (alias, standard_name) VALUES (%s, %s)",
                (alias.strip(), standard_name.strip())
            )
            self.conn.commit()
            print(f"✅ 매핑 추가: '{alias}' → '{standard_name}'")
            return True
        except mysql.connector.IntegrityError:
            print(f"⚠️ 이미 존재하는 별칭: '{alias}'")
            return False
        except Exception as e:
            print(f"❌ 매핑 추가 실패: {e}")
            return False

    def add_group(self, aliases: List[str], standard_name: str) -> int:
        """
        여러 별칭을 한 번에 추가 (그룹으로 묶기)

        Args:
            aliases: 별칭 리스트
            standard_name: 표준 이름

        Returns:
            성공한 개수
        """
        success_count = 0

        # 표준 이름 자체도 매핑에 추가 (자기 자신으로)
        if self.add_mapping(standard_name, standard_name):
            success_count += 1

        # 별칭들 추가
        for alias in aliases:
            if alias != standard_name:  # 표준 이름과 다른 경우만
                if self.add_mapping(alias, standard_name):
                    success_count += 1

        print(f"✅ 그룹 추가 완료: {success_count}개 매핑 추가됨")
        return success_count

    def get_standard_name(self, alias: str) -> Optional[str]:
        """
        별칭으로 표준 이름 조회

        Args:
            alias: 원본/별칭 이름

        Returns:
            표준 이름 (없으면 None)
        """
        self.cursor.execute(
            "SELECT standard_name FROM seller_mapping WHERE alias = %s",
            (alias.strip(),)
        )
        row = self.cursor.fetchone()
        return row["standard_name"] if row else None

    def normalize_name(self, name: str) -> str:
        """
        판매처 이름 정규화

        Args:
            name: 원본 이름

        Returns:
            표준 이름 (매핑이 없으면 원본 그대로 반환)
        """
        standard = self.get_standard_name(name)
        return standard if standard else name

    def update_mapping(self, alias: str, new_standard_name: str) -> bool:
        """
        기존 매핑 수정

        Args:
            alias: 별칭
            new_standard_name: 새로운 표준 이름

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                "UPDATE seller_mapping SET standard_name = %s WHERE alias = %s",
                (new_standard_name.strip(), alias.strip())
            )
            self.conn.commit()

            if self.cursor.rowcount > 0:
                print(f"✅ 매핑 수정: '{alias}' → '{new_standard_name}'")
                return True
            else:
                print(f"⚠️ 매핑을 찾을 수 없음: '{alias}'")
                return False
        except Exception as e:
            print(f"❌ 매핑 수정 실패: {e}")
            return False

    def delete_mapping(self, alias: str) -> bool:
        """
        매핑 삭제

        Args:
            alias: 삭제할 별칭

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                "DELETE FROM seller_mapping WHERE alias = %s",
                (alias.strip(),)
            )
            self.conn.commit()

            if self.cursor.rowcount > 0:
                print(f"✅ 매핑 삭제: '{alias}'")
                return True
            else:
                print(f"⚠️ 매핑을 찾을 수 없음: '{alias}'")
                return False
        except Exception as e:
            print(f"❌ 매핑 삭제 실패: {e}")
            return False

    def list_all_mappings(self) -> List[Dict[str, str]]:
        """
        모든 매핑 조회

        Returns:
            매핑 리스트 [{alias, standard_name, created_at}]
        """
        self.cursor.execute(
            "SELECT alias, standard_name, created_at FROM seller_mapping ORDER BY standard_name, alias"
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_groups(self) -> Dict[str, List[str]]:
        """
        표준 이름별로 그룹화된 별칭 조회

        Returns:
            {표준이름: [별칭1, 별칭2, ...]}
        """
        self.cursor.execute(
            "SELECT standard_name, alias FROM seller_mapping ORDER BY standard_name, alias"
        )

        groups = {}
        for row in self.cursor.fetchall():
            standard = row["standard_name"]
            alias = row["alias"]

            if standard not in groups:
                groups[standard] = []
            groups[standard].append(alias)

        return groups

    def get_all_standard_names(self) -> List[str]:
        """
        모든 표준 이름 조회 (중복 제거)

        Returns:
            표준 이름 리스트
        """
        try:
            self.cursor.execute(
                "SELECT DISTINCT standard_name FROM seller_mapping ORDER BY standard_name"
            )
            return [row["standard_name"] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"⚠️  표준 이름 조회 실패: {e}")
            return []

    def find_similar_with_gpt(self, seller_name: str, threshold: float = 0.7) -> Optional[Dict[str, any]]:
        """
        GPT API를 사용하여 오타 교정 (수동발주 케이스용)

        Args:
            seller_name: 매칭할 판매처 이름
            threshold: 신뢰도 임계값 (0.0 ~ 1.0)

        Returns:
            {
                "original": 원본 이름,
                "matched": 매칭된 표준 이름,
                "confidence": 신뢰도 (0.0 ~ 1.0),
                "requires_manual": 수동 수정 필요 여부
            }
            매칭 실패 시 None
        """
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            # DB에서 모든 표준 이름 가져오기
            standard_names = self.get_all_standard_names()

            if not standard_names:
                return None

            # GPT에게 가장 유사한 이름 찾기 요청
            prompt = f"""다음 판매처 이름을 아래 목록 중 가장 유사한 이름으로 매칭해주세요.
오타나 띄어쓰기 차이를 고려하여 가장 적절한 것을 찾아주세요.

입력 이름: "{seller_name}"

표준 이름 목록:
{chr(10).join(f"- {name}" for name in standard_names)}

응답 형식 (JSON):
{{
  "matched_name": "매칭된 표준 이름 (목록에 없으면 null)",
  "confidence": 0.0~1.0 사이의 신뢰도,
  "reason": "매칭 이유 간단 설명"
}}

주의: matched_name은 반드시 위 목록에 있는 이름 중 하나여야 합니다. 확신이 없으면 confidence를 낮게 설정하세요."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 판매처 이름 매칭 전문가입니다. 주어진 목록에서만 선택해야 합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)

            matched_name = result.get("matched_name")
            confidence = float(result.get("confidence", 0.0))

            if matched_name and confidence >= threshold:
                return {
                    "original": seller_name,
                    "matched": matched_name,
                    "confidence": confidence,
                    "requires_manual": False,
                    "reason": result.get("reason", "")
                }
            else:
                return {
                    "original": seller_name,
                    "matched": None,
                    "confidence": confidence,
                    "requires_manual": True,
                    "reason": result.get("reason", "신뢰도가 낮아 수동 확인이 필요합니다.")
                }

        except Exception as e:
            error_msg = str(e)
            # proxies 에러인 경우 더 자세한 안내
            if "proxies" in error_msg.lower():
                print(f"⚠️ GPT 매칭 실패: OpenAI 라이브러리 버전 호환성 문제")
                print(f"   해결방법: pip install --upgrade openai")
            else:
                print(f"⚠️ GPT 매칭 실패: {error_msg}")
            return None

    def export_to_csv(self, csv_path: str = "seller_mapping.csv") -> bool:
        """
        매핑을 CSV로 내보내기

        Args:
            csv_path: CSV 파일 경로

        Returns:
            성공 여부
        """
        try:
            import csv

            mappings = self.list_all_mappings()

            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                if mappings:
                    writer = csv.DictWriter(f, fieldnames=['alias', 'standard_name', 'created_at'])
                    writer.writeheader()
                    writer.writerows(mappings)

            print(f"✅ CSV 내보내기 완료: {csv_path} ({len(mappings)}건)")
            return True
        except Exception as e:
            print(f"❌ CSV 내보내기 실패: {e}")
            return False

    def import_from_csv(self, csv_path: str) -> int:
        """
        CSV에서 매핑 가져오기

        Args:
            csv_path: CSV 파일 경로

        Returns:
            가져온 개수
        """
        try:
            import csv

            count = 0
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if self.add_mapping(row['alias'], row['standard_name']):
                        count += 1

            print(f"✅ CSV 가져오기 완료: {count}건")
            return count
        except Exception as e:
            print(f"❌ CSV 가져오기 실패: {e}")
            return 0


# ===== CLI 인터페이스 =====
def cli_init():
    """DB 초기화"""
    with SellerMappingDB() as db:
        db.init_db()


def cli_add():
    """매핑 추가"""
    print("\n=== 판매처 매핑 추가 ===")
    alias = input("별칭 입력: ").strip()
    standard = input("표준 이름 입력: ").strip()

    if alias and standard:
        with SellerMappingDB() as db:
            db.add_mapping(alias, standard)
    else:
        print("❌ 별칭과 표준 이름을 모두 입력하세요.")


def cli_add_group():
    """그룹으로 매핑 추가"""
    print("\n=== 판매처 그룹 추가 ===")
    standard = input("표준 이름 입력: ").strip()
    aliases_str = input("별칭들 입력 (쉼표로 구분): ").strip()

    if standard and aliases_str:
        aliases = [a.strip() for a in aliases_str.split(',') if a.strip()]
        with SellerMappingDB() as db:
            db.add_group(aliases, standard)
    else:
        print("❌ 표준 이름과 별칭을 모두 입력하세요.")


def cli_list():
    """전체 매핑 조회"""
    with SellerMappingDB() as db:
        groups = db.get_groups()

        if not groups:
            print("\n등록된 매핑이 없습니다.")
            return

        print("\n=== 판매처 매핑 목록 ===")
        for standard, aliases in groups.items():
            print(f"\n[{standard}]")
            for alias in aliases:
                if alias == standard:
                    print(f"  ✓ {alias} (표준)")
                else:
                    print(f"  → {alias}")


def cli_test():
    """매핑 테스트"""
    print("\n=== 판매처 이름 정규화 테스트 ===")
    name = input("변환할 이름 입력: ").strip()

    if name:
        with SellerMappingDB() as db:
            normalized = db.normalize_name(name)
            if normalized != name:
                print(f"✅ '{name}' → '{normalized}'")
            else:
                print(f"ℹ️ 매핑 없음: '{name}' (그대로 사용)")
    else:
        print("❌ 이름을 입력하세요.")


def cli_export():
    """CSV로 내보내기"""
    csv_path = input("CSV 파일 경로 (기본: seller_mapping.csv): ").strip()
    if not csv_path:
        csv_path = "seller_mapping.csv"

    with SellerMappingDB() as db:
        db.export_to_csv(csv_path)


def cli_import():
    """CSV에서 가져오기"""
    csv_path = input("CSV 파일 경로: ").strip()

    if csv_path and os.path.exists(csv_path):
        with SellerMappingDB() as db:
            db.import_from_csv(csv_path)
    else:
        print("❌ 파일을 찾을 수 없습니다.")


def cli_menu():
    """메인 메뉴"""
    while True:
        print("\n" + "=" * 50)
        print("판매처 이름 통일 관리 시스템")
        print("=" * 50)
        print("1. DB 초기화")
        print("2. 매핑 추가 (개별)")
        print("3. 매핑 추가 (그룹)")
        print("4. 전체 매핑 보기")
        print("5. 매핑 테스트")
        print("6. CSV로 내보내기")
        print("7. CSV에서 가져오기")
        print("0. 종료")
        print("=" * 50)

        choice = input("선택: ").strip()

        if choice == "1":
            cli_init()
        elif choice == "2":
            cli_add()
        elif choice == "3":
            cli_add_group()
        elif choice == "4":
            cli_list()
        elif choice == "5":
            cli_test()
        elif choice == "6":
            cli_export()
        elif choice == "7":
            cli_import()
        elif choice == "0":
            print("종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")


# ===== 기본 데이터 초기화 =====
def init_default_mappings():
    """
    기본 판매처 매핑 초기화
    자주 사용되는 판매처 매핑을 미리 등록
    """
    with SellerMappingDB() as db:
        db.init_db()

        # G마켓
        db.add_group(
            aliases=["지마켓", "G마켓", "gmarket", "GMARKET", "Gmarket"],
            standard_name="G마켓"
        )

        # 카카오선물하기
        db.add_group(
            aliases=["카카오", "선물하기", "카카오선물하기", "카카오 선물하기"],
            standard_name="카카오선물하기"
        )

        # 네이버 스마트스토어
        db.add_group(
            aliases=["네이버", "스마트스토어", "네이버 스마트스토어", "smartstore"],
            standard_name="스마트스토어"
        )

        # 쿠팡
        db.add_group(
            aliases=["쿠팡", "Coupang", "coupang", "COUPANG"],
            standard_name="쿠팡"
        )

        print("\n✅ 기본 매핑 초기화 완료")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        # 기본 데이터로 초기화
        init_default_mappings()
    else:
        # CLI 메뉴 실행
        cli_menu()
