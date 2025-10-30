"""
판매처 이름 수동 매핑 웹 에디터

GPT API로 자동 매칭이 어려운 판매처 이름을 수동으로 매핑하는 웹 인터페이스
Flask 기반 경량 웹 애플리케이션
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from seller_mapping import SellerMappingDB
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 수동 매핑이 필요한 판매처 목록 (세션 저장용)
pending_mappings = []


# ===== HTML 템플릿 =====
EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>판매처 이름 매핑 에디터</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
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
            content: "📝";
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
        .order-info {
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 12px;
            margin-bottom: 15px;
            border-radius: 4px;
            font-size: 13px;
        }
        .order-info-title {
            font-weight: 600;
            color: #1565C0;
            margin-bottom: 8px;
        }
        .order-info-item {
            display: flex;
            padding: 4px 0;
        }
        .order-info-label {
            font-weight: 600;
            color: #424242;
            min-width: 80px;
        }
        .order-info-value {
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
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        select.form-control {
            cursor: pointer;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .btn-success {
            background: #28a745;
            color: white;
        }
        .btn-success:hover {
            background: #218838;
        }
        .action-buttons {
            display: flex;
            gap: 10px;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        .empty-state h2 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        .empty-state p {
            font-size: 16px;
        }
        .success-icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .stat-item {
            text-align: center;
        }
        .stat-value {
            font-size: 32px;
            font-weight: 700;
            color: #667eea;
        }
        .stat-label {
            font-size: 14px;
            color: #6c757d;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏪 판매처 이름 매핑 에디터</h1>
            <p>GPT가 자동으로 매칭하지 못한 판매처 이름을 수동으로 매핑하세요</p>
        </div>

        <div class="content">
            {% if pending_items %}
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value">{{ pending_items|length }}</div>
                        <div class="stat-label">매핑 대기</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{{ standard_names|length }}</div>
                        <div class="stat-label">표준 이름</div>
                    </div>
                </div>

                <form method="POST" action="/save_mappings">
                    {% for item in pending_items %}
                    <div class="mapping-item">
                        <div class="original-name">{{ item.original }}</div>

                        {% if item.order_info %}
                        <div class="order-info">
                            <div class="order-info-title">📦 주문 정보</div>
                            {% if item.order_info.주문번호 %}
                            <div class="order-info-item">
                                <div class="order-info-label">주문번호:</div>
                                <div class="order-info-value">{{ item.order_info.주문번호 }}</div>
                            </div>
                            {% endif %}
                            {% if item.order_info.품목명 %}
                            <div class="order-info-item">
                                <div class="order-info-label">품목명:</div>
                                <div class="order-info-value">{{ item.order_info.품목명 }}</div>
                            </div>
                            {% endif %}
                            {% if item.order_info.브랜드 %}
                            <div class="order-info-item">
                                <div class="order-info-label">브랜드:</div>
                                <div class="order-info-value">{{ item.order_info.브랜드 }}</div>
                            </div>
                            {% endif %}
                            {% if item.order_info.수량 %}
                            <div class="order-info-item">
                                <div class="order-info-label">수량:</div>
                                <div class="order-info-value">{{ item.order_info.수량 }}</div>
                            </div>
                            {% endif %}
                            {% if item.order_info.일자 %}
                            <div class="order-info-item">
                                <div class="order-info-label">일자:</div>
                                <div class="order-info-value">{{ item.order_info.일자 }}</div>
                            </div>
                            {% endif %}
                        </div>
                        {% endif %}

                        {% if item.gpt_suggestion %}
                        <div class="gpt-suggestion">
                            <strong>🤖 GPT 추천:</strong> {{ item.gpt_suggestion }}
                            (신뢰도: {{ "%.0f"|format(item.confidence * 100) }}%)
                            <br>
                            <small>{{ item.reason }}</small>
                        </div>
                        {% endif %}

                        <div class="form-group">
                            <label>표준 이름 선택 또는 신규 입력</label>
                            <select class="form-control" name="mapping_{{ loop.index0 }}"
                                    onchange="toggleCustomInput({{ loop.index0 }}, this.value)">
                                <option value="">-- 선택하세요 --</option>
                                {% for std_name in standard_names %}
                                <option value="{{ std_name }}"
                                        {% if item.gpt_suggestion == std_name %}selected{% endif %}>
                                    {{ std_name }}
                                </option>
                                {% endfor %}
                                <option value="__custom__">➕ 새로운 표준 이름 입력</option>
                            </select>
                        </div>

                        <div class="form-group" id="custom_{{ loop.index0 }}" style="display: none;">
                            <label>새 표준 이름</label>
                            <input type="text" class="form-control"
                                   name="custom_{{ loop.index0 }}"
                                   placeholder="새로운 표준 이름을 입력하세요">
                        </div>

                        <input type="hidden" name="original_{{ loop.index0 }}" value="{{ item.original }}">
                    </div>
                    {% endfor %}

                    <div class="action-buttons">
                        <button type="submit" class="btn btn-primary">
                            💾 모든 매핑 저장
                        </button>
                    </div>
                </form>
            {% else %}
                <div class="empty-state">
                    <div class="success-icon">✅</div>
                    <h2>매핑이 완료되었습니다!</h2>
                    <p>모든 판매처 이름이 표준 이름으로 매핑되었습니다.</p>
                </div>
            {% endif %}
        </div>
    </div>

    <script>
        function toggleCustomInput(index, value) {
            const customDiv = document.getElementById('custom_' + index);
            if (value === '__custom__') {
                customDiv.style.display = 'block';
            } else {
                customDiv.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """메인 페이지: 매핑 대기 중인 항목 표시"""
    with SellerMappingDB() as db:
        standard_names = db.get_all_standard_names()

    return render_template_string(
        EDITOR_TEMPLATE,
        pending_items=pending_mappings,
        standard_names=standard_names
    )


@app.route('/save_mappings', methods=['POST'])
def save_mappings():
    """매핑 저장"""
    global pending_mappings

    saved_count = 0

    with SellerMappingDB() as db:
        for i, item in enumerate(pending_mappings):
            mapping_value = request.form.get(f'mapping_{i}')

            if mapping_value == '__custom__':
                # 사용자 정의 표준 이름
                custom_name = request.form.get(f'custom_{i}')
                if custom_name and custom_name.strip():
                    standard_name = custom_name.strip()
                else:
                    continue
            elif mapping_value:
                standard_name = mapping_value
            else:
                continue

            # DB에 매핑 추가
            original = item['original']
            if db.add_mapping(original, standard_name):
                saved_count += 1

    # 저장 완료 후 목록 초기화
    pending_mappings.clear()

    return redirect(url_for('index'))


@app.route('/api/add_pending', methods=['POST'])
def api_add_pending():
    """매핑 대기 항목 추가 (API)"""
    global pending_mappings

    data = request.json

    if not data or 'original' not in data:
        return jsonify({"success": False, "error": "Missing original name"}), 400

    pending_item = {
        "original": data['original'],
        "gpt_suggestion": data.get('gpt_suggestion'),
        "confidence": data.get('confidence', 0.0),
        "reason": data.get('reason', '')
    }

    # 중복 체크
    if not any(p['original'] == pending_item['original'] for p in pending_mappings):
        pending_mappings.append(pending_item)

    return jsonify({"success": True, "pending_count": len(pending_mappings)})


@app.route('/api/clear_pending', methods=['POST'])
def api_clear_pending():
    """매핑 대기 항목 초기화 (API)"""
    global pending_mappings
    pending_mappings.clear()
    return jsonify({"success": True})


def start_editor(sellers_to_map: List[Dict] = None, port: int = 5000):
    """
    웹 에디터 시작

    Args:
        sellers_to_map: 매핑할 판매처 목록 [{"original": "...", "gpt_suggestion": "...", ...}]
        port: 웹 서버 포트
    """
    global pending_mappings

    if sellers_to_map:
        pending_mappings = sellers_to_map

    print(f"\n🌐 판매처 매핑 에디터 시작...")
    print(f"   URL: http://localhost:{port}")
    print(f"   매핑 대기: {len(pending_mappings)}건")
    print(f"\n브라우저에서 위 URL을 열어 매핑을 진행하세요.")
    print(f"종료하려면 Ctrl+C를 누르세요.\n")

    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    # 테스트용 실행
    test_data = [
        {
            "original": "지마켓",
            "gpt_suggestion": "G마켓",
            "confidence": 0.95,
            "reason": "오타 및 표기 차이로 판단됨"
        },
        {
            "original": "알수없는판매처",
            "gpt_suggestion": None,
            "confidence": 0.2,
            "reason": "유사한 이름을 찾을 수 없음"
        }
    ]

    start_editor(test_data, port=5000)
