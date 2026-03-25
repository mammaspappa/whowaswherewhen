from flask import Blueprint, jsonify, request
from db import queries

bp = Blueprint('discussions', __name__)


@bp.route('/api/discussions')
def list_discussions():
    target_type = request.args.get('target_type')
    target_id = request.args.get('target_id', type=int)
    if not target_type or not target_id:
        return jsonify({'error': 'target_type and target_id required'}), 400
    return jsonify(queries.get_discussions(target_type, target_id))


@bp.route('/api/discussions', methods=['POST'])
def create_discussion():
    data = request.get_json()
    required = ('target_type', 'target_id', 'body')
    if not data or not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {", ".join(required)}'}), 400
    if data['target_type'] not in ('person', 'whereabout'):
        return jsonify({'error': 'target_type must be person or whereabout'}), 400
    did = queries.create_discussion(data)
    return jsonify({'id': did}), 201


@bp.route('/api/discussions/<int:discussion_id>', methods=['PUT'])
def update_discussion(discussion_id):
    data = request.get_json()
    if not data or 'body' not in data:
        return jsonify({'error': 'body required'}), 400
    existing = queries.get_discussion(discussion_id)
    if not existing:
        return jsonify({'error': 'Not found'}), 404
    queries.update_discussion(discussion_id, data)
    return jsonify({'ok': True})
