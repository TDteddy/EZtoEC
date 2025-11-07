"""
쿠팡 상품 매핑 DB에서 잘못된 상품명 정리

standard_product_name에 "(브랜드: ...)" 패턴이 포함된 데이터를 정리합니다.
예: "ADWRB01 손목 보호대 T1 (브랜드: 에이더)" → "ADWRB01 손목 보호대 T1"
"""

import re
from coupang_product_mapping import CoupangProductMappingDB


def clean_product_name(product_name: str) -> str:
    """
    상품명에서 "(브랜드: ...)" 패턴 제거

    Args:
        product_name: 원본 상품명

    Returns:
        정리된 상품명
    """
    # "(브랜드: 브랜드명)" 패턴 제거
    cleaned = re.sub(r'\s*\(브랜드:\s*[^)]+\)', '', product_name)
    return cleaned.strip()


def fix_mapping_table():
    """coupang_product_mapping 테이블의 상품명 정리"""
    print("=" * 80)
    print("쿠팡 상품 매핑 테이블 정리 중...")
    print("=" * 80)

    with CoupangProductMappingDB() as db:
        # 모든 매핑 조회
        mappings = db.get_all_mappings()

        if not mappings:
            print("⚠️  매핑 데이터가 없습니다.")
            return

        print(f"\n총 {len(mappings)}건의 매핑 확인 중...\n")

        fixed_count = 0

        for mapping in mappings:
            coupang_option = mapping['coupang_option_name']
            standard_name = mapping['standard_product_name']
            multiplier = mapping['quantity_multiplier']
            brand = mapping['brand']

            # 상품명 정리
            cleaned_name = clean_product_name(standard_name)

            # 변경이 필요한 경우만 업데이트
            if cleaned_name != standard_name:
                print(f"🔧 수정 필요:")
                print(f"   쿠팡 옵션: {coupang_option}")
                print(f"   변경 전: {standard_name}")
                print(f"   변경 후: {cleaned_name}")

                # 업데이트
                success = db.update_mapping(
                    coupang_option_name=coupang_option,
                    standard_product_name=cleaned_name,
                    quantity_multiplier=multiplier,
                    brand=brand
                )

                if success:
                    fixed_count += 1
                    print(f"   ✅ 수정 완료\n")
                else:
                    print(f"   ❌ 수정 실패\n")

        print("=" * 80)
        print(f"정리 완료: {fixed_count}건 수정됨")
        print("=" * 80)


def fix_standard_products_table():
    """standard_products 테이블의 상품명 정리"""
    print("\n" + "=" * 80)
    print("스탠다드 상품 테이블 정리 중...")
    print("=" * 80)

    with CoupangProductMappingDB() as db:
        # 모든 스탠다드 상품 조회
        products = db.get_all_standard_products()

        if not products:
            print("⚠️  스탠다드 상품 데이터가 없습니다.")
            return

        print(f"\n총 {len(products)}건의 상품 확인 중...\n")

        fixed_count = 0

        for product in products:
            product_id = product['id']
            product_name = product['product_name']
            brand = product['brand']

            # 상품명 정리
            cleaned_name = clean_product_name(product_name)

            # 변경이 필요한 경우만 업데이트
            if cleaned_name != product_name:
                print(f"🔧 수정 필요:")
                print(f"   변경 전: {product_name}")
                print(f"   변경 후: {cleaned_name}")

                try:
                    # UPDATE 쿼리 실행
                    db.cursor.execute(
                        "UPDATE standard_products SET product_name = %s WHERE id = %s",
                        (cleaned_name, product_id)
                    )
                    db.conn.commit()

                    fixed_count += 1
                    print(f"   ✅ 수정 완료\n")
                except Exception as e:
                    print(f"   ❌ 수정 실패: {e}\n")

        print("=" * 80)
        print(f"정리 완료: {fixed_count}건 수정됨")
        print("=" * 80)


if __name__ == "__main__":
    print("\n쿠팡 상품 매핑 DB 정리 시작\n")

    # 1. 매핑 테이블 정리
    fix_mapping_table()

    # 2. 스탠다드 상품 테이블 정리
    fix_standard_products_table()

    print("\n✅ 모든 정리 작업 완료!\n")
