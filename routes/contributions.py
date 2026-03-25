from flask import Blueprint, jsonify, request
from db import queries

bp = Blueprint('contributions', __name__)


@bp.route('/api/contributions', methods=['POST'])
def submit_contribution():
    data = request.get_json()
    required = ('person_name', 'place_name', 'date_start', 'date_end')
    if not data or not all(k in data for k in required):
        return jsonify({'error': f'Required fields: {", ".join(required)}'}), 400
    cid = queries.create_contribution(data)
    return jsonify({'id': cid}), 201


@bp.route('/api/contributions')
def list_contributions():
    status = request.args.get('status')
    return jsonify(queries.get_contributions(status))


@bp.route('/api/contributions/<int:contribution_id>', methods=['PUT'])
def review_contribution(contribution_id):
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status required'}), 400

    status = data['status']
    notes = data.get('reviewer_notes')

    if status == 'approved':
        result = queries.approve_contribution(contribution_id, notes)
        if result is None:
            return jsonify({'error': 'Contribution not found or not pending'}), 404
        return jsonify({'ok': True, 'whereabout_id': result})
    elif status == 'rejected':
        queries.reject_contribution(contribution_id, notes)
        return jsonify({'ok': True})
    else:
        return jsonify({'error': 'status must be approved or rejected'}), 400
