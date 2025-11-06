"""
쿠팡 로켓그로스 상품 매핑 관리 시스템

쿠팡 옵션명을 이지어드민 스탠다드 상품명으로 매핑:
- 상품명 매핑
- 수량 배수 (N개 묶음 상품)
- 브랜드 정보
"""

import mysql.connector
from mysql.connector import Error
import os
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# ===== 설정 =====
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "seller_mapping")  # 같은 DB 사용

# OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY


class CoupangProductMappingDB:
    """쿠팡 상품 매핑 관리 클래스"""

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
            self._ensure_tables_exist()

            print(f"✅ 쿠팡 상품 매핑 DB 연결: {self.database}")
        except Error as e:
            print(f"❌ DB 연결 실패: {e}")
            raise

    def _ensure_tables_exist(self):
        """테이블 존재 확인 및 자동 생성"""
        try:
            # 1. 이지어드민 스탠다드 상품 목록 테이블
            self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'standard_products'
            """, (self.database,))

            result = self.cursor.fetchone()

            if result['count'] == 0:
                print(f"[INFO] standard_products 테이블 생성 중...")
                create_table_sql = """
                CREATE TABLE standard_products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    product_name VARCHAR(500) NOT NULL UNIQUE COMMENT '이지어드민 스탠다드 상품명',
                    brand VARCHAR(100) NOT NULL COMMENT '브랜드 (닥터시드/딸로/테르스/에이더)',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_product_name (product_name),
                    INDEX idx_brand (brand)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
                self.cursor.execute(create_table_sql)
                print(f"✅ standard_products 테이블 생성 완료")

            # 2. 쿠팡-이지어드민 매핑 테이블
            self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'coupang_product_mapping'
            """, (self.database,))

            result = self.cursor.fetchone()

            if result['count'] == 0:
                print(f"[INFO] coupang_product_mapping 테이블 생성 중...")
                create_table_sql = """
                CREATE TABLE coupang_product_mapping (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    coupang_option_name VARCHAR(500) NOT NULL UNIQUE COMMENT '쿠팡 옵션명',
                    standard_product_name VARCHAR(500) NOT NULL COMMENT '이지어드민 스탠다드 상품명',
                    quantity_multiplier INT NOT NULL DEFAULT 1 COMMENT '수량 배수 (N개 묶음)',
                    brand VARCHAR(100) NOT NULL COMMENT '브랜드',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_coupang_option (coupang_option_name),
                    INDEX idx_standard_product (standard_product_name),
                    INDEX idx_brand (brand)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
                self.cursor.execute(create_table_sql)
                print(f"✅ coupang_product_mapping 테이블 생성 완료")

            self.conn.commit()

        except Error as e:
            print(f"❌ 테이블 생성 실패: {e}")
            raise

    def close(self):
        """DB 연결 종료"""
        if self.cursor:
            self.cursor.close()
        if self.conn and self.conn.is_connected():
            self.conn.close()

    # ===== 스탠다드 상품 관리 =====

    def add_standard_product(self, product_name: str, brand: str) -> bool:
        """
        이지어드민 스탠다드 상품 추가

        Args:
            product_name: 상품명
            brand: 브랜드 (닥터시드/딸로/테르스/에이더)

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                "INSERT INTO standard_products (product_name, brand) VALUES (%s, %s)",
                (product_name.strip(), brand.strip())
            )
            self.conn.commit()
            print(f"✅ 스탠다드 상품 추가: '{product_name}' ({brand})")
            return True
        except Error as e:
            if "Duplicate entry" in str(e):
                print(f"⚠️  이미 존재하는 상품: '{product_name}'")
            else:
                print(f"❌ 상품 추가 실패: {e}")
            return False

    def get_all_standard_products(self) -> List[Dict]:
        """
        모든 스탠다드 상품 조회

        Returns:
            상품 리스트 [{id, product_name, brand, created_at}]
        """
        try:
            self.cursor.execute(
                "SELECT id, product_name, brand, created_at FROM standard_products ORDER BY brand, product_name"
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ 상품 조회 실패: {e}")
            return []

    def get_standard_products_by_brand(self, brand: str) -> List[Dict]:
        """
        브랜드별 스탠다드 상품 조회

        Args:
            brand: 브랜드명

        Returns:
            상품 리스트
        """
        try:
            self.cursor.execute(
                "SELECT id, product_name, brand, created_at FROM standard_products WHERE brand = %s ORDER BY product_name",
                (brand,)
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ 상품 조회 실패: {e}")
            return []

    # ===== 쿠팡 상품 매핑 관리 =====

    def add_mapping(self, coupang_option_name: str, standard_product_name: str,
                    quantity_multiplier: int, brand: str) -> bool:
        """
        쿠팡 상품 매핑 추가

        Args:
            coupang_option_name: 쿠팡 옵션명
            standard_product_name: 이지어드민 스탠다드 상품명
            quantity_multiplier: 수량 배수
            brand: 브랜드

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                """INSERT INTO coupang_product_mapping
                   (coupang_option_name, standard_product_name, quantity_multiplier, brand)
                   VALUES (%s, %s, %s, %s)""",
                (coupang_option_name.strip(), standard_product_name.strip(), quantity_multiplier, brand.strip())
            )
            self.conn.commit()
            print(f"✅ 매핑 추가: '{coupang_option_name}' → '{standard_product_name}' (x{quantity_multiplier}, {brand})")
            return True
        except Error as e:
            if "Duplicate entry" in str(e):
                print(f"⚠️  이미 존재하는 매핑: '{coupang_option_name}'")
            else:
                print(f"❌ 매핑 추가 실패: {e}")
            return False

    def get_mapping(self, coupang_option_name: str) -> Optional[Dict]:
        """
        쿠팡 옵션명에 대한 매핑 조회

        Args:
            coupang_option_name: 쿠팡 옵션명

        Returns:
            매핑 정보 {standard_product_name, quantity_multiplier, brand} 또는 None
        """
        try:
            self.cursor.execute(
                """SELECT standard_product_name, quantity_multiplier, brand
                   FROM coupang_product_mapping
                   WHERE coupang_option_name = %s""",
                (coupang_option_name,)
            )
            row = self.cursor.fetchone()
            return row if row else None
        except Error as e:
            print(f"❌ 매핑 조회 실패: {e}")
            return None

    def get_all_mappings(self) -> List[Dict]:
        """
        모든 매핑 조회

        Returns:
            매핑 리스트
        """
        try:
            self.cursor.execute(
                """SELECT coupang_option_name, standard_product_name, quantity_multiplier, brand, created_at
                   FROM coupang_product_mapping
                   ORDER BY brand, standard_product_name"""
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ 매핑 조회 실패: {e}")
            return []

    def update_mapping(self, coupang_option_name: str, standard_product_name: str,
                       quantity_multiplier: int, brand: str) -> bool:
        """
        기존 매핑 수정

        Args:
            coupang_option_name: 쿠팡 옵션명
            standard_product_name: 새로운 스탠다드 상품명
            quantity_multiplier: 새로운 수량 배수
            brand: 새로운 브랜드

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                """UPDATE coupang_product_mapping
                   SET standard_product_name = %s, quantity_multiplier = %s, brand = %s
                   WHERE coupang_option_name = %s""",
                (standard_product_name.strip(), quantity_multiplier, brand.strip(), coupang_option_name.strip())
            )
            self.conn.commit()

            if self.cursor.rowcount > 0:
                print(f"✅ 매핑 수정: '{coupang_option_name}' → '{standard_product_name}' (x{quantity_multiplier}, {brand})")
                return True
            else:
                print(f"⚠️  매핑을 찾을 수 없음: '{coupang_option_name}'")
                return False
        except Error as e:
            print(f"❌ 매핑 수정 실패: {e}")
            return False

    def delete_mapping(self, coupang_option_name: str) -> bool:
        """
        매핑 삭제

        Args:
            coupang_option_name: 쿠팡 옵션명

        Returns:
            성공 여부
        """
        try:
            self.cursor.execute(
                "DELETE FROM coupang_product_mapping WHERE coupang_option_name = %s",
                (coupang_option_name,)
            )
            self.conn.commit()

            if self.cursor.rowcount > 0:
                print(f"✅ 매핑 삭제: '{coupang_option_name}'")
                return True
            else:
                print(f"⚠️  매핑을 찾을 수 없음: '{coupang_option_name}'")
                return False
        except Error as e:
            print(f"❌ 매핑 삭제 실패: {e}")
            return False

    # ===== GPT 자동 매칭 =====

    def match_product_with_gpt(self, coupang_option_name: str) -> Optional[Dict]:
        """
        GPT를 사용하여 쿠팡 옵션명을 스탠다드 상품과 매칭

        Args:
            coupang_option_name: 쿠팡 옵션명

        Returns:
            {
                "standard_product_name": str,
                "quantity_multiplier": int,
                "brand": str,
                "confidence": float,
                "reason": str
            } 또는 None
        """
        if not OPENAI_API_KEY:
            print("⚠️  OPENAI_API_KEY가 설정되지 않았습니다.")
            return None

        try:
            # 모든 스탠다드 상품 목록 가져오기
            standard_products = self.get_all_standard_products()

            if not standard_products:
                print("⚠️  스탠다드 상품 목록이 비어있습니다.")
                return None

            # GPT에게 매칭 요청
            product_list = "\n".join([
                f"- {p['product_name']} (브랜드: {p['brand']})"
                for p in standard_products
            ])

            prompt = f"""
다음은 쿠팡 로켓그로스에서 판매된 상품의 옵션명입니다:
"{coupang_option_name}"

아래는 이지어드민의 스탠다드 상품 목록입니다:
{product_list}

이 쿠팡 옵션명이 어떤 스탠다드 상품에 해당하는지 분석하고, 다음 정보를 JSON 형식으로 반환해주세요:

1. standard_product_name: 매칭되는 스탠다드 상품명 (정확히 위 목록에서 선택)
2. quantity_multiplier: 수량 배수 (예: "3개입"이면 3, "5+1"이면 6, "1개"면 1)
3. brand: 브랜드명 (닥터시드/딸로/테르스/에이더 중 하나)
4. confidence: 매칭 신뢰도 (0.0 ~ 1.0)
5. reason: 매칭 이유 설명

응답 형식:
{{
  "standard_product_name": "상품명",
  "quantity_multiplier": 숫자,
  "brand": "브랜드명",
  "confidence": 0.0~1.0,
  "reason": "설명"
}}

매칭이 불확실하면 confidence를 낮게 설정하세요.
매칭할 수 없으면 null을 반환하세요.
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 상품명 매칭 전문가입니다. 쿠팡 옵션명을 분석하여 정확한 스탠다드 상품명, 수량 배수, 브랜드를 찾아주세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content.strip()

            import json
            result = json.loads(result_text)

            # null 응답 처리
            if result is None or result.get("standard_product_name") is None:
                return None

            # 신뢰도 체크
            confidence = result.get("confidence", 0.0)

            return result

        except Exception as e:
            print(f"❌ GPT 매칭 실패: {e}")
            return None


# ===== 편의 함수 =====

def import_standard_products_from_excel(excel_path: str, sheet_name: str = "상품목록"):
    """
    엑셀에서 스탠다드 상품 목록 가져오기

    엑셀 형식:
    | 상품명 | 브랜드 |
    """
    import pandas as pd

    with CoupangProductMappingDB() as db:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)

        for _, row in df.iterrows():
            product_name = str(row.get("상품명", "")).strip()
            brand = str(row.get("브랜드", "")).strip()

            if product_name and brand:
                db.add_standard_product(product_name, brand)

        print(f"✅ {len(df)}건의 상품 가져오기 완료")


if __name__ == "__main__":
    print("=" * 80)
    print("쿠팡 상품 매핑 DB 테스트")
    print("=" * 80)

    with CoupangProductMappingDB() as db:
        # 테스트: 스탠다드 상품 추가
        db.add_standard_product("닥터시드 비타민C 1000mg", "닥터시드")
        db.add_standard_product("딸로 컬러케어 샴푸", "딸로")

        # 테스트: 매핑 추가
        db.add_mapping(
            coupang_option_name="닥터시드 비타민C 3개입",
            standard_product_name="닥터시드 비타민C 1000mg",
            quantity_multiplier=3,
            brand="닥터시드"
        )

        # 테스트: 매핑 조회
        mapping = db.get_mapping("닥터시드 비타민C 3개입")
        print(f"\n매핑 조회 결과: {mapping}")

        print("\n✅ 테스트 완료")
