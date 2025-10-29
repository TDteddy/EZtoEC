"""
판매처 이름 통일 관리 시스템

같은 판매처를 여러 이름으로 부르는 경우 표준 이름으로 통합:
- "지마켓", "G마켓", "gmarket" → "G마켓"
- "카카오", "선물하기", "카카오선물하기" → "카카오선물하기"

SQLite 기반 DB로 매핑 정보 관리
"""

import sqlite3
import os
from typing import List, Dict, Optional, Tuple


# ===== 설정 =====
DB_PATH = "seller_mapping.db"


class SellerMappingDB:
    """판매처 이름 매핑 관리 클래스"""

    def __init__(self, db_path: str = DB_PATH):
        """
        Args:
            db_path: SQLite DB 파일 경로
        """
        self.db_path = db_path
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
        """DB 연결"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        self.cursor = self.conn.cursor()

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL UNIQUE,
            standard_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_alias ON seller_mapping(alias);
        CREATE INDEX IF NOT EXISTS idx_standard ON seller_mapping(standard_name);
        """

        self.cursor.executescript(create_table_sql)
        self.conn.commit()
        print(f"✅ DB 초기화 완료: {self.db_path}")

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
                "INSERT INTO seller_mapping (alias, standard_name) VALUES (?, ?)",
                (alias.strip(), standard_name.strip())
            )
            self.conn.commit()
            print(f"✅ 매핑 추가: '{alias}' → '{standard_name}'")
            return True
        except sqlite3.IntegrityError:
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
            "SELECT standard_name FROM seller_mapping WHERE alias = ?",
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
                "UPDATE seller_mapping SET standard_name = ? WHERE alias = ?",
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
                "DELETE FROM seller_mapping WHERE alias = ?",
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
