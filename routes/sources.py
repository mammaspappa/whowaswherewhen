from flask import Blueprint, jsonify, request
from db import queries

bp = Blueprint('sources', __name__)


@bp.route('/api/sources')
def list_sources():
    whereabout_id = request.args.get('whereabout_id', type=int)
    if not whereabout_id:
        return jsonify({'error': 'whereabout_id required'}), 400
    return jsonify(queries.get_sources(whereabout_id))


@bp.route('/api/sources', methods=['POST'])
def create_source():
    data = request.get_json()
    if not data or 'whereabout_id' not in data or 'title' not in data:
        return jsonify({'error': 'whereabout_id and title required'}), 400
    sid = queries.create_source(data)
    return jsonify({'id': sid}), 201
