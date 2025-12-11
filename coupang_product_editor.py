"""
쿠팡 로켓그로스 상품 수동 매핑 웹 에디터

GPT API로 자동 매칭이 어려운 쿠팡 상품을 수동으로 매핑하는 웹 인터페이스
Flask 기반 경량 웹 애플리케이션
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from coupang_product_mapping import CoupangProductMappingDB
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 수동 매핑이 필요한 상품 목록 (세션 저장용)
pending_mappings = []


# ===== HTML 템플릿 =====
EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>쿠팡 상품 매핑 에디터</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .content {
            padding: 30px;
        }
        .mapping-item {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border: 2px solid #e9ecef;
        }
        .mapping-item:hover {
            border-color: #f093fb;
            box-shadow: 0 4px 12px rgba(240, 147, 251, 0.15);
        }
        .original-name {
            font-size: 18px;
            font-weight: 600;
            color: #495057;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
        }
        .original-name::before {
            content: "🛒";
            margin-right: 10px;
            font-size: 22px;
        }
        .gpt-suggestion {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin-bottom: 15px;
            border-radius: 4px;
            font-size: 14px;
        }
        .gpt-suggestion strong {
            color: #856404;
        }
        .sample-data {
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 12px;
            margin-bottom: 15px;
            border-radius: 4px;
            font-size: 13px;
        }
        .sample-data-title {
            font-weight: 600;
            color: #1565C0;
            margin-bottom: 8px;
        }
        .sample-data-item {
            display: flex;
            padding: 4px 0;
        }
        .sample-data-label {
            font-weight: 600;
            color: #424242;
            min-width: 100px;
        }
        .sample-data-value {
            color: #616161;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #495057;
            font-size: 14px;
        }
        .form-control {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            font-size: 15px;
            transition: all 0.3s;
        }
        .form-control:focus {
            outline: none;
            border-color: #f093fb;
            box-shadow: 0 0 0 3px rgba(240, 147, 251, 0.1);
        }
        select.form-control {
            cursor: pointer;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(240, 147, 251, 0.4);
        }
        .btn-secondary {
            background: #6c757d;
            color: white;
            margin-left: 10px;
        }
        .btn-secondary:hover {
            background: #5a6268;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        .stat-card {
            flex: 1;
            min-width: 150px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-label {
            font-size: 13px;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        .stat-value {
            font-size: 32px;
            font-weight: 700;
        }
        .success-message {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 600;
        }
        .info-box {
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .info-box strong {
            color: #1565C0;
        }
        .quantity-input {
            max-width: 150px;
        }
        .form-row {
            display: flex;
            gap: 15px;
        }
        .form-row .form-group {
            flex: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛒 쿠팡 상품 매핑 에디터</h1>
            <p>쿠팡 로켓그로스 옵션명을 스탠다드 상품과 매핑하세요</p>
        </div>

        <div class="content">
            {% if success %}
            <div class="success-message">
                ✅ 모든 상품 매핑이 완료되었습니다!
                <br>
                <small>터미널로 돌아가서 Enter를 누르면 자동으로 업로드가 진행됩니다.</small>
            </div>
            {% endif %}

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">매핑 필요</div>
                    <div class="stat-value">{{ pending_count }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">스탠다드 상품</div>
                    <div class="stat-value">{{ standard_products|length }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">기존 매핑</div>
                    <div class="stat-value">{{ existing_mappings }}</div>
                </div>
            </div>

            {% if not success and pending_mappings %}
            <div class="info-box">
                <strong>안내:</strong> GPT가 자동 매칭하지 못한 상품입니다.
                아래에서 스탠다드 상품을 선택하고 수량 배수를 입력하세요.
                <br><small>수량 배수: "3개입" → 3, "5+1" → 6</small>
            </div>

            <form method="POST" action="{{ url_for('save_mappings') }}">
                {% for item in pending_mappings %}
                <div class="mapping-item">
                    <div class="original-name">
                        {{ item.option_name }}
                        <span style="margin-left: auto; font-size: 14px; color: #6c757d;">
                            ({{ item.count }}건)
                        </span>
                    </div>

                    {% if item.gpt_suggestion %}
                    <div class="gpt-suggestion">
                        <strong>🤖 GPT 추천:</strong>
                        {{ item.gpt_suggestion }} (x{{ item.gpt_multiplier }}, {{ item.gpt_brand }})
                        <br>
                        <small>신뢰도: {{ (item.confidence * 100)|int }}% - {{ item.reason }}</small>
                    </div>
                    {% endif %}

                    {% if item.sample_data %}
                    <div class="sample-data">
                        <div class="sample-data-title">📊 샘플 데이터</div>
                        <div class="sample-data-item">
                            <span class="sample-data-label">날짜:</span>
                            <span class="sample-data-value">{{ item.sample_data.date }}</span>
                        </div>
                        <div class="sample-data-item">
                            <span class="sample-data-label">상품 ID:</span>
                            <span class="sample-data-value">{{ item.sample_data.product_id }}</span>
                        </div>
                        <div class="sample-data-item">
                            <span class="sample-data-label">판매 수량:</span>
                            <span class="sample-data-value">{{ item.sample_data.qty }}</span>
                        </div>
                        <div class="sample-data-item">
                            <span class="sample-data-label">판매 금액:</span>
                            <span class="sample-data-value">{{ item.sample_data.amount }}</span>
                        </div>
                    </div>
                    {% endif %}

                    <input type="hidden" name="original_{{ loop.index0 }}" value="{{ item.option_name }}">
                    <input type="hidden" name="is_set_{{ loop.index0 }}" id="is_set_{{ loop.index0 }}" value="false">

                    <div class="form-group">
                        <label for="standard_{{ loop.index0 }}">스탠다드 상품 선택</label>
                        <select class="form-control" id="standard_{{ loop.index0 }}" name="standard_{{ loop.index0 }}" required>
                            <option value="">-- 선택하세요 --</option>
                            <optgroup label="개별 상품">
                            {% for product in standard_products %}
                            <option value="{{ product.product_name }}"
                                    data-brand="{{ product.brand }}"
                                    data-cost-price="{{ product.cost_price }}"
                                    data-is-set="false"
                                    {% if item.gpt_suggestion == product.product_name %}selected{% endif %}>
                                {{ product.product_name }} ({{ product.brand }}, 원가: {{ "{:,.0f}".format(product.cost_price) }}원)
                            </option>
                            {% endfor %}
                            </optgroup>
                            {% if set_products %}
                            <optgroup label="세트상품">
                            {% for set_product in set_products %}
                            {% set total_cost = namespace(value=0) %}
                            {% for item_inner in set_product.set_items %}
                                {% set total_cost.value = total_cost.value + (item_inner.cost_price * item_inner.quantity) %}
                            {% endfor %}
                            <option value="{{ set_product.set_name }}"
                                    data-brand="{{ set_product.brand }}"
                                    data-cost-price="{{ total_cost.value }}"
                                    data-is-set="true">
                                [세트] {{ set_product.set_name }} ({{ set_product.brand }}, 원가: {{ "{:,.0f}".format(total_cost.value) }}원)
                            </option>
                            {% endfor %}
                            </optgroup>
                            {% endif %}
                        </select>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="multiplier_{{ loop.index0 }}">수량 배수</label>
                            <input type="number"
                                   class="form-control quantity-input"
                                   id="multiplier_{{ loop.index0 }}"
                                   name="multiplier_{{ loop.index0 }}"
                                   min="1"
                                   value="{{ item.gpt_multiplier or 1 }}"
                                   required>
                        </div>

                        <div class="form-group">
                            <label for="brand_{{ loop.index0 }}">브랜드</label>
                            <select class="form-control" id="brand_{{ loop.index0 }}" name="brand_{{ loop.index0 }}" required>
                                <option value="">-- 선택하세요 --</option>
                                <option value="닥터시드" {% if item.gpt_brand == "닥터시드" %}selected{% endif %}>닥터시드</option>
                                <option value="딸로" {% if item.gpt_brand == "딸로" %}selected{% endif %}>딸로</option>
                                <option value="테르스" {% if item.gpt_brand == "테르스" %}selected{% endif %}>테르스</option>
                                <option value="에이더" {% if item.gpt_brand == "에이더" %}selected{% endif %}>에이더</option>
                            </select>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="cost_price_{{ loop.index0 }}">원가 (부가세 포함)</label>
                        <input type="number"
                               class="form-control"
                               id="cost_price_{{ loop.index0 }}"
                               name="cost_price_{{ loop.index0 }}"
                               min="0"
                               step="0.01"
                               placeholder="원가 입력"
                               readonly
                               style="background-color: #f8f9fa;">
                        <small style="color: #6c757d;">상품 선택 시 자동으로 채워집니다 (읽기 전용)</small>
                    </div>
                </div>
                {% endfor %}

                <input type="hidden" name="count" value="{{ pending_mappings|length }}">
                <button type="submit" class="btn btn-primary">💾 모든 매핑 저장</button>
            </form>
            {% endif %}

            {% if success or not pending_mappings %}
            <div style="text-align: center; padding: 40px 0;">
                <p style="font-size: 18px; color: #6c757d;">
                    {% if success %}
                    모든 매핑이 완료되었습니다! 터미널로 돌아가서 Enter를 눌러주세요.
                    {% else %}
                    매핑이 필요한 상품이 없습니다.
                    {% endif %}
                </p>
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        // 스탠다드 상품 선택 시 브랜드 및 원가 자동 설정
        document.querySelectorAll('select[id^="standard_"]').forEach((select, index) => {
            select.addEventListener('change', function() {
                const selectedOption = this.options[this.selectedIndex];
                const brand = selectedOption.getAttribute('data-brand');
                const costPrice = selectedOption.getAttribute('data-cost-price');
                const isSet = selectedOption.getAttribute('data-is-set');

                if (brand) {
                    document.getElementById('brand_' + index).value = brand;
                }
                if (costPrice) {
                    document.getElementById('cost_price_' + index).value = costPrice;
                }
                if (isSet) {
                    document.getElementById('is_set_' + index).value = isSet;
                }
            });

            // 페이지 로드 시 이미 선택된 상품이 있으면 원가 자동 채우기
            if (select.value) {
                const selectedOption = select.options[select.selectedIndex];
                const costPrice = selectedOption.getAttribute('data-cost-price');
                const isSet = selectedOption.getAttribute('data-is-set');
                if (costPrice) {
                    document.getElementById('cost_price_' + index).value = costPrice;
                }
                if (isSet) {
                    document.getElementById('is_set_' + index).value = isSet;
                }
            }
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """메인 페이지 - 매핑이 필요한 상품 목록 표시"""
    global pending_mappings

    with CoupangProductMappingDB() as db:
        standard_products = db.get_all_standard_products()
        set_products = db.get_all_set_products()
        all_mappings = db.get_all_mappings()

    return render_template_string(
        EDITOR_TEMPLATE,
        pending_mappings=pending_mappings,
        pending_count=len(pending_mappings),
        standard_products=standard_products,
        set_products=set_products,
        existing_mappings=len(all_mappings),
        success=False
    )


@app.route('/save', methods=['POST'])
def save_mappings():
    """매핑 저장 (세트상품 지원)"""
    global pending_mappings

    count = int(request.form.get('count', 0))

    with CoupangProductMappingDB() as db:
        for i in range(count):
            original = request.form.get(f'original_{i}')
            standard = request.form.get(f'standard_{i}')
            multiplier = int(request.form.get(f'multiplier_{i}', 1))
            brand = request.form.get(f'brand_{i}')
            is_set = request.form.get(f'is_set_{i}') == 'true'

            if original and standard and brand:
                db.add_mapping_with_set(original, standard, multiplier, brand, is_set)

    # 저장 완료 후 pending_mappings 초기화
    pending_mappings = []

    with CoupangProductMappingDB() as db:
        standard_products = db.get_all_standard_products()
        set_products = db.get_all_set_products()
        all_mappings = db.get_all_mappings()

    return render_template_string(
        EDITOR_TEMPLATE,
        pending_mappings=[],
        pending_count=0,
        standard_products=standard_products,
        set_products=set_products,
        existing_mappings=len(all_mappings),
        success=True
    )


def start_editor(pending_list: List[Dict] = None, port: int = 5001, debug: bool = False):
    """
    웹 에디터 시작

    Args:
        pending_list: 수동 매핑이 필요한 상품 목록
        port: 포트 번호
        debug: 디버그 모드
    """
    global pending_mappings

    if pending_list:
        pending_mappings = pending_list

    print(f"\n🌐 웹 에디터 시작: http://localhost:{port}")
    print("   브라우저에서 위 주소로 접속하세요.")
    print("   매핑 완료 후 터미널로 돌아와서 Enter를 누르면 자동으로 업로드가 진행됩니다.\n")

    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == "__main__":
    # 테스트용
    test_pending = [
        {
            "option_name": "닥터시드 비타민C 3개입",
            "count": 5,
            "gpt_suggestion": "닥터시드 비타민C 1000mg",
            "gpt_multiplier": 3,
            "gpt_brand": "닥터시드",
            "confidence": 0.65,
            "reason": "유사도가 낮음",
            "sample_data": {
                "date": "2025-01-15",
                "product_id": "12345",
                "qty": "2",
                "amount": "30000"
            }
        }
    ]
    start_editor(test_pending, port=5001, debug=True)
