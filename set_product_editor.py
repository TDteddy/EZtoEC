"""
세트상품 관리 웹 에디터

이카운트 개별 상품들을 조합하여 세트상품을 만들고 관리하는 웹 UI
"""

from flask import Flask, request, render_template_string, jsonify, redirect, url_for
from coupang_product_mapping import CoupangProductMappingDB
from typing import List, Dict

app = Flask(__name__)

# HTML 템플릿
EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>세트상품 관리</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .stat-card h3 {
            color: #764ba2;
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .stat-card p {
            color: #666;
            font-size: 1em;
        }

        .card {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .card h2 {
            color: #333;
            margin-bottom: 20px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }

        .form-control {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }

        .form-control:focus {
            border-color: #667eea;
            outline: none;
        }

        select.form-control {
            cursor: pointer;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .btn-danger {
            background: #dc3545;
            color: white;
        }

        .btn-danger:hover {
            background: #c82333;
        }

        .btn-success {
            background: #28a745;
            color: white;
        }

        .btn-success:hover {
            background: #218838;
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-sm {
            padding: 6px 12px;
            font-size: 0.85em;
        }

        .items-container {
            border: 2px solid #eee;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            max-height: 300px;
            overflow-y: auto;
        }

        .item-row {
            display: grid;
            grid-template-columns: 1fr 100px 40px;
            gap: 10px;
            margin-bottom: 10px;
            align-items: center;
        }

        .item-row:last-child {
            margin-bottom: 0;
        }

        .set-product-list {
            display: grid;
            gap: 15px;
        }

        .set-product-item {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #667eea;
        }

        .set-product-item h4 {
            color: #333;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .set-product-item .brand-badge {
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
        }

        .set-product-item .items-list {
            margin: 10px 0;
            padding-left: 20px;
        }

        .set-product-item .items-list li {
            color: #666;
            margin-bottom: 5px;
        }

        .set-product-item .cost-info {
            color: #28a745;
            font-weight: 600;
            margin-top: 10px;
        }

        .set-product-item .actions {
            margin-top: 15px;
            display: flex;
            gap: 10px;
        }

        .product-selector {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .product-list-panel {
            border: 2px solid #eee;
            border-radius: 8px;
            padding: 15px;
        }

        .product-list-panel h4 {
            margin-bottom: 15px;
            color: #333;
        }

        .product-checkbox-list {
            max-height: 400px;
            overflow-y: auto;
        }

        .product-checkbox-item {
            display: flex;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }

        .product-checkbox-item:hover {
            background: #f8f9fa;
        }

        .product-checkbox-item input[type="checkbox"] {
            margin-right: 10px;
            transform: scale(1.2);
        }

        .product-checkbox-item .product-info {
            flex: 1;
        }

        .product-checkbox-item .product-name {
            font-weight: 500;
        }

        .product-checkbox-item .product-meta {
            font-size: 0.85em;
            color: #666;
        }

        .product-checkbox-item .quantity-input {
            width: 60px;
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            text-align: center;
        }

        .selected-items-panel {
            border: 2px solid #667eea;
        }

        .selected-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: #f0f4ff;
            border-radius: 6px;
            margin-bottom: 8px;
        }

        .selected-item .remove-btn {
            background: none;
            border: none;
            color: #dc3545;
            cursor: pointer;
            font-size: 1.2em;
        }

        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }

        .modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-content {
            background: white;
            border-radius: 15px;
            padding: 30px;
            max-width: 900px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .modal-header h3 {
            color: #333;
        }

        .modal-close {
            background: none;
            border: none;
            font-size: 1.5em;
            cursor: pointer;
            color: #666;
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }

        .empty-state i {
            font-size: 3em;
            margin-bottom: 15px;
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>세트상품 관리</h1>

        <div class="stats-container">
            <div class="stat-card">
                <h3>{{ set_products|length }}</h3>
                <p>등록된 세트상품</p>
            </div>
            <div class="stat-card">
                <h3>{{ standard_products|length }}</h3>
                <p>개별 상품 수</p>
            </div>
        </div>

        {% if message %}
        <div class="alert alert-{{ message_type }}">
            {{ message }}
        </div>
        {% endif %}

        <!-- 새 세트상품 추가 카드 -->
        <div class="card">
            <h2>새 세트상품 추가</h2>
            <form action="/create" method="post" id="createForm">
                <div class="form-group">
                    <label>세트상품명</label>
                    <input type="text" name="set_name" class="form-control"
                           placeholder="예: 닥터시드 비타민 3종 세트" required>
                </div>

                <div class="form-group">
                    <label>브랜드</label>
                    <select name="brand" class="form-control" required>
                        <option value="">선택하세요</option>
                        <option value="닥터시드">닥터시드</option>
                        <option value="딸로">딸로</option>
                        <option value="테르스">테르스</option>
                        <option value="에이더">에이더</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>구성 상품 선택</label>
                    <div class="items-container" id="newSetItems">
                        <div class="item-row">
                            <select name="item_0" class="form-control item-select" required>
                                <option value="">상품 선택</option>
                                {% for product in standard_products %}
                                <option value="{{ product.product_name }}"
                                        data-brand="{{ product.brand }}"
                                        data-cost="{{ product.cost_price }}">
                                    {{ product.product_name }} ({{ product.brand }}, {{ product.cost_price|int }}원)
                                </option>
                                {% endfor %}
                            </select>
                            <input type="number" name="qty_0" class="form-control"
                                   value="1" min="1" placeholder="수량">
                            <button type="button" class="btn btn-danger btn-sm"
                                    onclick="removeItemRow(this)">X</button>
                        </div>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm"
                            onclick="addItemRow()">+ 상품 추가</button>
                </div>

                <button type="submit" class="btn btn-primary">세트상품 저장</button>
            </form>
        </div>

        <!-- 기존 세트상품 목록 -->
        <div class="card">
            <h2>등록된 세트상품</h2>

            {% if set_products %}
            <div class="set-product-list">
                {% for set_product in set_products %}
                <div class="set-product-item">
                    <h4>
                        {{ set_product.set_name }}
                        <span class="brand-badge">{{ set_product.brand }}</span>
                    </h4>

                    <ul class="items-list">
                        {% for item in set_product.set_items %}
                        <li>{{ item.standard_product_name }} x {{ item.quantity }}
                            ({{ item.cost_price|int }}원)</li>
                        {% endfor %}
                    </ul>

                    {% set total_cost = namespace(value=0) %}
                    {% for item in set_product.set_items %}
                        {% set total_cost.value = total_cost.value + (item.cost_price * item.quantity) %}
                    {% endfor %}
                    <div class="cost-info">
                        총 원가: {{ total_cost.value|int }}원
                    </div>

                    <div class="actions">
                        <button class="btn btn-primary btn-sm"
                                onclick="editSetProduct({{ set_product.id }})">수정</button>
                        <form action="/delete/{{ set_product.id }}" method="post"
                              style="display:inline"
                              onsubmit="return confirm('정말 삭제하시겠습니까?')">
                            <button type="submit" class="btn btn-danger btn-sm">삭제</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">
                <span>📦</span>
                <p>등록된 세트상품이 없습니다.</p>
                <p>위에서 새 세트상품을 추가해주세요.</p>
            </div>
            {% endif %}
        </div>
    </div>

    <!-- 수정 모달 -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>세트상품 수정</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <form action="/update" method="post" id="editForm">
                <input type="hidden" name="set_id" id="edit_set_id">

                <div class="form-group">
                    <label>세트상품명</label>
                    <input type="text" name="set_name" id="edit_set_name"
                           class="form-control" required>
                </div>

                <div class="form-group">
                    <label>브랜드</label>
                    <select name="brand" id="edit_brand" class="form-control" required>
                        <option value="닥터시드">닥터시드</option>
                        <option value="딸로">딸로</option>
                        <option value="테르스">테르스</option>
                        <option value="에이더">에이더</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>구성 상품</label>
                    <div class="items-container" id="editSetItems">
                        <!-- 동적으로 채워짐 -->
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm"
                            onclick="addEditItemRow()">+ 상품 추가</button>
                </div>

                <button type="submit" class="btn btn-primary">수정 저장</button>
            </form>
        </div>
    </div>

    <script>
        let itemIndex = 1;
        let editItemIndex = 0;

        const standardProducts = {{ standard_products|tojson }};
        const setProducts = {{ set_products|tojson }};

        function getProductOptions(selectedValue = '') {
            let options = '<option value="">상품 선택</option>';
            standardProducts.forEach(p => {
                const selected = p.product_name === selectedValue ? 'selected' : '';
                options += `<option value="${p.product_name}"
                                   data-brand="${p.brand}"
                                   data-cost="${p.cost_price}" ${selected}>
                    ${p.product_name} (${p.brand}, ${Math.floor(p.cost_price)}원)
                </option>`;
            });
            return options;
        }

        function addItemRow() {
            const container = document.getElementById('newSetItems');
            const row = document.createElement('div');
            row.className = 'item-row';
            row.innerHTML = `
                <select name="item_${itemIndex}" class="form-control item-select" required>
                    ${getProductOptions()}
                </select>
                <input type="number" name="qty_${itemIndex}" class="form-control"
                       value="1" min="1" placeholder="수량">
                <button type="button" class="btn btn-danger btn-sm"
                        onclick="removeItemRow(this)">X</button>
            `;
            container.appendChild(row);
            itemIndex++;
        }

        function removeItemRow(btn) {
            const container = btn.closest('.items-container');
            if (container.querySelectorAll('.item-row').length > 1) {
                btn.closest('.item-row').remove();
            } else {
                alert('최소 1개의 상품이 필요합니다.');
            }
        }

        function editSetProduct(setId) {
            const setProduct = setProducts.find(s => s.id === setId);
            if (!setProduct) return;

            document.getElementById('edit_set_id').value = setId;
            document.getElementById('edit_set_name').value = setProduct.set_name;
            document.getElementById('edit_brand').value = setProduct.brand;

            const container = document.getElementById('editSetItems');
            container.innerHTML = '';
            editItemIndex = 0;

            setProduct.items.forEach((item, i) => {
                const row = document.createElement('div');
                row.className = 'item-row';
                row.innerHTML = `
                    <select name="edit_item_${i}" class="form-control" required>
                        ${getProductOptions(item.standard_product_name)}
                    </select>
                    <input type="number" name="edit_qty_${i}" class="form-control"
                           value="${item.quantity}" min="1">
                    <button type="button" class="btn btn-danger btn-sm"
                            onclick="removeItemRow(this)">X</button>
                `;
                container.appendChild(row);
                editItemIndex++;
            });

            document.getElementById('editModal').classList.add('active');
        }

        function addEditItemRow() {
            const container = document.getElementById('editSetItems');
            const row = document.createElement('div');
            row.className = 'item-row';
            row.innerHTML = `
                <select name="edit_item_${editItemIndex}" class="form-control" required>
                    ${getProductOptions()}
                </select>
                <input type="number" name="edit_qty_${editItemIndex}" class="form-control"
                       value="1" min="1">
                <button type="button" class="btn btn-danger btn-sm"
                        onclick="removeItemRow(this)">X</button>
            `;
            container.appendChild(row);
            editItemIndex++;
        }

        function closeModal() {
            document.getElementById('editModal').classList.remove('active');
        }

        // 모달 바깥 클릭시 닫기
        document.getElementById('editModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    </script>
</body>
</html>
"""

# 완료 페이지 템플릿
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>완료 - 세트상품 관리</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .success-container {
            background: white;
            border-radius: 20px;
            padding: 60px 40px;
            max-width: 600px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            animation: slideIn 0.5s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .success-icon {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 30px;
            animation: scaleIn 0.6s ease-out 0.2s both;
        }

        @keyframes scaleIn {
            from {
                transform: scale(0);
            }
            to {
                transform: scale(1);
            }
        }

        .success-icon svg {
            width: 60px;
            height: 60px;
            stroke: white;
            stroke-width: 3;
            fill: none;
            stroke-dasharray: 100;
            stroke-dashoffset: 100;
            animation: drawCheck 0.8s ease-out 0.5s forwards;
        }

        @keyframes drawCheck {
            to {
                stroke-dashoffset: 0;
            }
        }

        h1 {
            color: #333;
            font-size: 2.5em;
            margin-bottom: 20px;
            animation: fadeIn 0.6s ease-out 0.4s both;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }

        .message {
            color: #666;
            font-size: 1.2em;
            margin-bottom: 10px;
            line-height: 1.6;
            animation: fadeIn 0.6s ease-out 0.6s both;
        }

        .details {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin: 30px 0;
            animation: fadeIn 0.6s ease-out 0.8s both;
        }

        .details h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }

        .detail-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e0e0e0;
        }

        .detail-item:last-child {
            border-bottom: none;
        }

        .detail-label {
            color: #666;
            font-weight: 500;
        }

        .detail-value {
            color: #333;
            font-weight: 600;
        }

        .items-list {
            list-style: none;
            padding: 0;
            margin: 10px 0;
        }

        .items-list li {
            padding: 8px 0;
            color: #555;
            border-bottom: 1px solid #f0f0f0;
        }

        .items-list li:last-child {
            border-bottom: none;
        }

        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 40px;
            animation: fadeIn 0.6s ease-out 1s both;
        }

        .btn {
            padding: 15px 40px;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }

        .btn-secondary {
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
        }

        .btn-secondary:hover {
            background: #f8f9ff;
            transform: translateY(-3px);
        }

        .stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 2px solid #f0f0f0;
            animation: fadeIn 0.6s ease-out 1.2s both;
        }

        .stat-item {
            text-align: center;
        }

        .stat-number {
            display: block;
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }

        .stat-label {
            color: #999;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="success-container">
        <div class="success-icon">
            <svg viewBox="0 0 52 52">
                <path d="M14 27l7 7 16-16"/>
            </svg>
        </div>

        <h1>{{ title }}</h1>

        <p class="message">{{ message }}</p>

        {% if set_product %}
        <div class="details">
            <h3>{{ action_text }} 상세 정보</h3>
            <div class="detail-item">
                <span class="detail-label">세트상품명</span>
                <span class="detail-value">{{ set_product.set_name }}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">브랜드</span>
                <span class="detail-value">{{ set_product.brand }}</span>
            </div>
            {% if set_product.set_items %}
            <div class="detail-item" style="display: block;">
                <span class="detail-label" style="display: block; margin-bottom: 10px;">구성 상품</span>
                <ul class="items-list">
                    {% for item in set_product.set_items %}
                    <li>{{ item.standard_product_name }} × {{ item.quantity }}개 ({{ item.cost_price|int }}원)</li>
                    {% endfor %}
                </ul>
            </div>
            {% set total_cost = namespace(value=0) %}
            {% for item in set_product.set_items %}
                {% set total_cost.value = total_cost.value + (item.cost_price * item.quantity) %}
            {% endfor %}
            <div class="detail-item">
                <span class="detail-label">총 원가</span>
                <span class="detail-value" style="color: #28a745; font-size: 1.2em;">{{ total_cost.value|int }}원</span>
            </div>
            {% endif %}
        </div>
        {% endif %}

        <div class="button-group">
            <a href="/" class="btn btn-primary">추가로 등록하기</a>
            <a href="/" class="btn btn-secondary">목록으로 돌아가기</a>
        </div>

        <div class="stats">
            <div class="stat-item">
                <span class="stat-number">{{ total_sets }}</span>
                <span class="stat-label">총 세트상품</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">{{ total_products }}</span>
                <span class="stat-label">개별 상품</span>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    """메인 페이지 - 세트상품 목록"""
    message = request.args.get('message', '')
    message_type = request.args.get('type', 'success')

    try:
        with CoupangProductMappingDB() as db:
            standard_products = db.get_all_standard_products()
            set_products = db.get_all_set_products()

        # 디버깅: 데이터 타입 확인
        print(f"[DEBUG] standard_products type: {type(standard_products)}, length: {len(standard_products) if isinstance(standard_products, list) else 'N/A'}")
        print(f"[DEBUG] set_products type: {type(set_products)}, length: {len(set_products) if isinstance(set_products, list) else 'N/A'}")

        # 리스트가 아닌 경우 빈 리스트로 초기화
        if not isinstance(standard_products, list):
            print(f"[WARNING] standard_products is not a list, resetting to empty list")
            standard_products = []
        if not isinstance(set_products, list):
            print(f"[WARNING] set_products is not a list, resetting to empty list")
            set_products = []

    except Exception as e:
        print(f"[ERROR] Failed to fetch data from DB: {e}")
        import traceback
        traceback.print_exc()
        standard_products = []
        set_products = []
        message = f"데이터베이스 조회 중 오류가 발생했습니다: {str(e)}"
        message_type = 'danger'

    return render_template_string(
        EDITOR_TEMPLATE,
        standard_products=standard_products,
        set_products=set_products,
        message=message,
        message_type=message_type
    )


@app.route('/success')
def success():
    """완료 페이지"""
    action = request.args.get('action', 'create')  # create, update, delete
    set_id = request.args.get('set_id', None)

    # 액션별 타이틀 및 메시지
    action_map = {
        'create': {
            'title': '세트상품 등록 완료',
            'action_text': '등록된 세트상품',
            'message': '세트상품이 성공적으로 등록되었습니다.'
        },
        'update': {
            'title': '세트상품 수정 완료',
            'action_text': '수정된 세트상품',
            'message': '세트상품 정보가 성공적으로 수정되었습니다.'
        },
        'delete': {
            'title': '세트상품 삭제 완료',
            'action_text': '삭제된 세트상품',
            'message': '세트상품이 성공적으로 삭제되었습니다.'
        }
    }

    action_info = action_map.get(action, action_map['create'])

    try:
        with CoupangProductMappingDB() as db:
            set_product = None
            if set_id and action != 'delete':
                set_product = db.get_set_product(int(set_id))

            # 통계 정보
            all_set_products = db.get_all_set_products()
            all_standard_products = db.get_all_standard_products()

            # 리스트가 아닌 경우 빈 리스트로 초기화
            if not isinstance(all_set_products, list):
                all_set_products = []
            if not isinstance(all_standard_products, list):
                all_standard_products = []

            total_sets = len(all_set_products)
            total_products = len(all_standard_products)

    except Exception as e:
        print(f"[ERROR] Failed to fetch data in success page: {e}")
        import traceback
        traceback.print_exc()
        set_product = None
        total_sets = 0
        total_products = 0

    return render_template_string(
        SUCCESS_TEMPLATE,
        title=action_info['title'],
        action_text=action_info['action_text'],
        message=action_info['message'],
        action=action,
        set_product=set_product,
        total_sets=total_sets,
        total_products=total_products
    )


@app.route('/create', methods=['POST'])
def create_set_product():
    """새 세트상품 생성"""
    set_name = request.form.get('set_name', '').strip()
    brand = request.form.get('brand', '').strip()

    if not set_name or not brand:
        return redirect(url_for('index', message='세트상품명과 브랜드를 입력해주세요.', type='danger'))

    # 구성 상품 수집
    items = []
    i = 0
    while True:
        item_name = request.form.get(f'item_{i}', '').strip()
        qty = request.form.get(f'qty_{i}', '1')

        if not item_name:
            break

        try:
            quantity = int(qty)
        except ValueError:
            quantity = 1

        items.append({
            'standard_product_name': item_name,
            'quantity': quantity
        })
        i += 1

    if not items:
        return redirect(url_for('index', message='최소 1개의 구성 상품이 필요합니다.', type='danger'))

    with CoupangProductMappingDB() as db:
        set_id = db.add_set_product(set_name, brand)

        if set_id:
            for item in items:
                db.add_set_product_item(set_id, item['standard_product_name'], item['quantity'])

            return redirect(url_for('success', action='create', set_id=set_id))
        else:
            return redirect(url_for('index',
                                    message=f"세트상품 생성 실패. 이미 존재하는 이름인지 확인해주세요.",
                                    type='danger'))


@app.route('/update', methods=['POST'])
def update_set_product():
    """세트상품 수정"""
    set_id = request.form.get('set_id')
    set_name = request.form.get('set_name', '').strip()
    brand = request.form.get('brand', '').strip()

    if not set_id or not set_name or not brand:
        return redirect(url_for('index', message='필수 정보가 누락되었습니다.', type='danger'))

    # 구성 상품 수집
    items = []
    i = 0
    while True:
        item_name = request.form.get(f'edit_item_{i}', '').strip()
        qty = request.form.get(f'edit_qty_{i}', '1')

        if not item_name:
            break

        try:
            quantity = int(qty)
        except ValueError:
            quantity = 1

        items.append({
            'standard_product_name': item_name,
            'quantity': quantity
        })
        i += 1

    if not items:
        return redirect(url_for('index', message='최소 1개의 구성 상품이 필요합니다.', type='danger'))

    with CoupangProductMappingDB() as db:
        success = db.update_set_product(int(set_id), set_name, brand, items)

        if success:
            return redirect(url_for('success', action='update', set_id=set_id))
        else:
            return redirect(url_for('index',
                                    message='세트상품 수정에 실패했습니다.',
                                    type='danger'))


@app.route('/delete/<int:set_id>', methods=['POST'])
def delete_set_product(set_id):
    """세트상품 삭제"""
    with CoupangProductMappingDB() as db:
        success = db.delete_set_product(set_id)

        if success:
            return redirect(url_for('success', action='delete'))
        else:
            return redirect(url_for('index',
                                    message='세트상품 삭제에 실패했습니다.',
                                    type='danger'))


@app.route('/api/set-products')
def api_get_set_products():
    """API: 모든 세트상품 조회"""
    with CoupangProductMappingDB() as db:
        set_products = db.get_all_set_products()
    return jsonify(set_products)


@app.route('/api/set-products/<int:set_id>')
def api_get_set_product(set_id):
    """API: 특정 세트상품 조회"""
    with CoupangProductMappingDB() as db:
        set_product = db.get_set_product(set_id)

    if set_product:
        return jsonify(set_product)
    else:
        return jsonify({'error': 'Set product not found'}), 404


def start_editor(port: int = 5002, debug: bool = False):
    """
    세트상품 에디터 웹 서버 시작

    Args:
        port: 서버 포트 (기본값: 5002)
        debug: 디버그 모드
    """
    print(f"\n{'=' * 60}")
    print(f"  세트상품 관리 에디터")
    print(f"{'=' * 60}")
    print(f"  URL: http://localhost:{port}")
    print(f"{'=' * 60}\n")

    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == "__main__":
    start_editor(debug=True)
