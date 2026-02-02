import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, jsonify, current_app, Response, flash
)
from app import db
from app.models import Cultivar, CultivarHistory
from app.backup import backup_database

bp = Blueprint('main', __name__)


@bp.route('/', endpoint='index')
def index():
    return redirect(url_for('main.cultivar_list'))


@bp.route('/table')
def table_view():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    per_page = min(per_page, 100)
    search = request.args.get('q', '').strip()

    query = Cultivar.query
    if search:
        query = query.filter(Cultivar.cultivar.ilike(f'%{search}%'))

    pagination = query.order_by(Cultivar.id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        'index.html',
        cultivars=pagination.items,
        pagination=pagination,
        per_page=per_page,
        search=search,
        authenticated=session.get('authenticated', False),
    )


@bp.route('/login', methods=['POST'])
def login():
    password = request.form.get('password', '')
    if password == current_app.config['ADMIN_PASSWORD']:
        session['authenticated'] = True
        try:
            uri = current_app.config['SQLALCHEMY_DATABASE_URI']
            db_path = uri.replace('sqlite:///', '')
            backup_database(db_path)
        except Exception:
            pass
    else:
        flash('Incorrect password.', 'error')
    return redirect(url_for('main.index'))


@bp.route('/logout', methods=['POST'])
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('main.index'))


@bp.route('/api/cultivar/<int:cultivar_id>', methods=['PUT'])
def update_cultivar(cultivar_id):
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401

    cultivar = db.get_or_404(Cultivar, cultivar_id)
    data = request.get_json()

    for bool_field in ('validated', 'priority'):
        if bool_field in data:
            old_val = getattr(cultivar, bool_field)
            new_val = bool(data[bool_field])
            if old_val != new_val:
                db.session.add(CultivarHistory(
                    cultivar_id=cultivar.id,
                    field_name=bool_field,
                    old_value=str(old_val),
                    new_value=str(new_val),
                    timestamp=datetime.now(timezone.utc),
                ))
            setattr(cultivar, bool_field, new_val)

    editable = ['epithet', 'category', 'color_form', 'tagline', 'description', 'notes', 'image_url', 'photo_url']
    for field in editable:
        if field in data:
            old_value = getattr(cultivar, field) or ''
            new_value = data[field] or ''
            if old_value != new_value:
                db.session.add(CultivarHistory(
                    cultivar_id=cultivar.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=new_value,
                    timestamp=datetime.now(timezone.utc),
                ))
            setattr(cultivar, field, data[field])

    db.session.commit()
    return jsonify(cultivar.to_dict())


@bp.route('/api/cultivar/<int:cultivar_id>/history')
def cultivar_history(cultivar_id):
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401

    db.get_or_404(Cultivar, cultivar_id)
    records = (CultivarHistory.query
               .filter_by(cultivar_id=cultivar_id)
               .order_by(CultivarHistory.timestamp.desc())
               .limit(100)
               .all())

    return jsonify([{
        'field_name': r.field_name,
        'old_value': r.old_value,
        'new_value': r.new_value,
        'timestamp': r.timestamp.isoformat() + 'Z',
    } for r in records])


@bp.route('/edit/<int:cultivar_id>')
def edit_cultivar(cultivar_id):
    cultivar = db.get_or_404(Cultivar, cultivar_id)

    prev_cultivar = Cultivar.query.filter(Cultivar.id < cultivar_id).order_by(Cultivar.id.desc()).first()
    next_cultivar = Cultivar.query.filter(Cultivar.id > cultivar_id).order_by(Cultivar.id.asc()).first()

    return render_template(
        'edit.html',
        cultivar=cultivar,
        prev_id=prev_cultivar.id if prev_cultivar else None,
        next_id=next_cultivar.id if next_cultivar else None,
        authenticated=session.get('authenticated', False),
    )


@bp.route('/summary')
def summary_view():
    search = request.args.get('q', '').strip()

    query = Cultivar.query
    if search:
        query = query.filter(Cultivar.cultivar.ilike(f'%{search}%'))

    cultivars = query.order_by(Cultivar.id).all()

    return render_template(
        'summary.html',
        cultivars=cultivars,
        search=search,
        view='summary',
        authenticated=session.get('authenticated', False),
    )


@bp.route('/list')
def cultivar_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 500, type=int)
    per_page = min(per_page, 2000)

    pagination = Cultivar.query.order_by(Cultivar.cultivar).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        'list.html',
        cultivars=pagination.items,
        pagination=pagination,
        per_page=per_page,
        view='list',
        authenticated=session.get('authenticated', False),
    )


@bp.route('/api/export')
def export_csv():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401

    cultivars = Cultivar.query.order_by(Cultivar.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Cultivar', 'Epithet', 'Category', 'Color / Form', 'Tagline', 'Description', 'Notes', 'Image URL'])
    for c in cultivars:
        writer.writerow([c.cultivar, c.epithet, c.category, c.color_form, c.tagline, c.description, c.notes, c.image_url])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=genes_enriched.csv'}
    )
