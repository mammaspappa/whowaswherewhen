from flask import Blueprint, jsonify, request
from db import queries

bp = Blueprint('revisions', __name__)


@bp.route('/api/revisions')
def list_revisions():
    target_type = request.args.get('target_type')
    target_id = request.args.get('target_id', type=int)
    if not target_type or not target_id:
        return jsonify({'error': 'target_type and target_id required'}), 400
    return jsonify(queries.get_revisions(target_type, target_id))


@bp.route('/api/revisions/<int:revision_id>')
def get_revision(revision_id):
    r = queries.get_revision(revision_id)
    if not r:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(r)
