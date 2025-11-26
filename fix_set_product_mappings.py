#!/usr/bin/env python3
"""
잘못 분류된 세트상품 매핑 일괄 수정 스크립트

세트상품 DB에 있는데 is_set_product=0으로 잘못 분류된 매핑을 찾아서
is_set_product=1로 자동 수정합니다.

사용법:
    python fix_set_product_mappings.py

주의:
    - DB 백업 후 실행하세요
    - 수정 내역을 확인 후 진행합니다
"""

from coupang_product_mapping import CoupangProductMappingDB


def main():
    print("=" * 80)
    print("잘못 분류된 세트상품 매핑 일괄 수정")
    print("=" * 80)
    print("\n이 스크립트는 다음 작업을 수행합니다:")
    print("  1. coupang_product_mapping 테이블에서 is_set_product=0인 매핑 조회")
    print("  2. 해당 매핑의 standard_product_name이 set_products 테이블에 있는지 확인")
    print("  3. 세트상품인데 잘못 분류된 경우 is_set_product=1로 수정")
    print()

    # 사용자 확인
    response = input("계속하시겠습니까? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("\n❌ 취소되었습니다.")
        return

    # 수정 실행
    print("\n" + "=" * 80)
    print("수정 시작")
    print("=" * 80)

    with CoupangProductMappingDB() as db:
        fixed_count = db.fix_misclassified_set_products()

    print("\n" + "=" * 80)
    print("작업 완료")
    print("=" * 80)

    if fixed_count > 0:
        print(f"\n✅ {fixed_count}건의 매핑을 세트상품으로 수정했습니다.")
        print("\n다음 단계:")
        print("  1. 수정된 매핑을 확인하세요:")
        print("     SELECT * FROM coupang_product_mapping WHERE is_set_product = 1;")
        print("  2. 다음번 쿠팡 데이터 처리 시 세트상품이 올바르게 분해됩니다.")
    else:
        print("\n✅ 잘못 분류된 매핑이 없습니다. DB가 정상 상태입니다.")


if __name__ == "__main__":
    main()
