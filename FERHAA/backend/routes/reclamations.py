"""
Routes pour le systeme de reclamations FERHAA.

Etudiant :
  POST /api/reclamations
  GET  /api/reclamations/mes

Admin pedagogique :
  GET  /api/admin/reclamations
  PUT  /api/admin/reclamations/<id>/repondre

Super Admin :
  GET  /api/admin/reclamations/all
  PUT  /api/admin/reclamations/<id>/reassigner
"""

import os

from flask import Blueprint, jsonify, request, session

from routes.decorators import login_required, permission_required
from services.database import (
    create_reclamation,
    get_reclamation_by_id,
    get_reclamations_all,
    get_reclamations_pedagogique,
    get_reclamations_user,
    log_audit,
    reassign_reclamation,
    resolve_reclamation,
)
from services.mail import (
    notifier_admin_nouvelle_reclamation,
    notifier_etudiant_reclamation_traitee,
)
from services.users import get_user_by_identifiant

reclamations_bp = Blueprint('reclamations', __name__)

ADMIN_PEDAGOGIQUE_EMAIL = os.environ.get(
    'ADMIN_PEDAGOGUE_EMAIL', 'admin.pedagogique@ensabm.ac.ma'
)

ADMIN_ROLES_VALIDES = {
    'admin_pedagogique', 'admin_it', 'super_admin',
}
DECISIONS_PEDAGOGIQUES = {
    'reclamation_fondee',
    'a_surveiller',
    'reclamation_non_fondee',
}


@reclamations_bp.route('/api/reclamations', methods=['POST'])
@login_required
def soumettre_reclamation():
    user = session.get('user')
    data = request.get_json(silent=True) or {}

    reponse_ia = str(data.get('reponse_ia', '')).strip()
    source_ia = str(data.get('source_ia', '')).strip()

    # Accepte soit description directe, soit motif+details (format envoyé par le chat)
    description = str(data.get('description', '')).strip()
    motif = str(data.get('motif', '')).strip()
    details = str(data.get('details', '')).strip()
    question = str(data.get('question', '')).strip()

    if not description and motif:
        parts = [f"Motif : {motif}"]
        if details:
            parts.append(f"Détails : {details}")
        if question:
            parts.append(f"Question posée : {question}")
        description = ' | '.join(parts)

    if not description:
        return jsonify({'erreur': 'La description du probleme est obligatoire.'}), 400
    if not reponse_ia:
        return jsonify({'erreur': 'La reponse IA concernee est obligatoire.'}), 400

    identifiant = user.get('identifiant', '')
    rec_id = create_reclamation(identifiant, reponse_ia, source_ia, description)

    log_audit(
        identifiant,
        user.get('role', 'student'),
        'submit_reclamation',
        target=f'reclamation#{rec_id}',
        details=f'Source IA: {source_ia} | Motif: {motif or "N/A"}',
        severity='info'
    )

    notifier_admin_nouvelle_reclamation(
        ADMIN_PEDAGOGIQUE_EMAIL, rec_id, source_ia, description
    )

    return jsonify({
        'message': 'Votre signalement a ete transmis. Vous recevrez une reponse par email.',
        'id': rec_id,
    }), 201


@reclamations_bp.route('/api/reclamations/mes', methods=['GET'])
@login_required
def mes_reclamations():
    user = session.get('user')
    rows = get_reclamations_user(user.get('identifiant', ''))
    return jsonify({'reclamations': rows})


@reclamations_bp.route('/api/admin/reclamations', methods=['GET'])
@permission_required('review_academic_content')
def reclamations_admin_pedagogique():
    statut = request.args.get('statut') or None
    rows = get_reclamations_pedagogique(statut=statut)
    return jsonify({'reclamations': rows})


@reclamations_bp.route('/api/admin/reclamations/<int:rec_id>/repondre', methods=['PUT'])
@permission_required('correct_ai_answers')
def repondre_reclamation(rec_id: int):
    user = session.get('user')
    data = request.get_json(silent=True) or {}
    reponse_admin = str(data.get('reponse_admin', '')).strip()
    decision_admin = str(data.get('decision_admin', '')).strip()
    improvement_needed = bool(data.get('improvement_needed', False))

    if not reponse_admin:
        return jsonify({'erreur': 'La reponse est obligatoire.'}), 400
    if decision_admin not in DECISIONS_PEDAGOGIQUES:
        return jsonify({'erreur': 'Decision pedagogique invalide.'}), 400

    rec = get_reclamation_by_id(rec_id)
    if not rec:
        return jsonify({'erreur': 'Reclamation introuvable.'}), 404

    resolve_reclamation(
        rec_id,
        reponse_admin,
        decision_admin=decision_admin,
        improvement_needed=improvement_needed,
        reviewed_by=user.get('identifiant', '')
    )

    log_audit(
        user.get('identifiant', ''),
        user.get('role', 'admin'),
        'resolve_reclamation',
        target=f'reclamation#{rec_id}',
        details=f'{decision_admin} | amelioration={improvement_needed} | {reponse_admin[:120]}',
        severity='info'
    )

    student = get_user_by_identifiant(rec.get('user_identifiant', ''))
    if student and student.get('email'):
        notifier_etudiant_reclamation_traitee(
            student['email'], rec_id, rec.get('source_ia', ''), reponse_admin,
            decision_admin=decision_admin,
        )

    return jsonify({
        'message': 'Reclamation resolue.',
        'id': rec_id,
        'decision_admin': decision_admin,
        'improvement_needed': improvement_needed,
    })


@reclamations_bp.route('/api/admin/reclamations/all', methods=['GET'])
@permission_required('full_access')
def reclamations_all():
    rows = get_reclamations_all()
    return jsonify({'reclamations': rows})


@reclamations_bp.route('/api/admin/reclamations/<int:rec_id>/reassigner', methods=['PUT'])
@permission_required('full_access')
def reassigner_reclamation(rec_id: int):
    user = session.get('user')
    data = request.get_json(silent=True) or {}
    admin_assigned = str(data.get('admin_assigned', '')).strip()

    if admin_assigned not in ADMIN_ROLES_VALIDES:
        return jsonify({'erreur': f'Role invalide. Valeurs acceptees : {", ".join(sorted(ADMIN_ROLES_VALIDES))}'}), 400

    rec = get_reclamation_by_id(rec_id)
    if not rec:
        return jsonify({'erreur': 'Reclamation introuvable.'}), 404

    reassign_reclamation(rec_id, admin_assigned)

    log_audit(
        user.get('identifiant', ''),
        user.get('role', 'super_admin'),
        'reassign_reclamation',
        target=f'reclamation#{rec_id}',
        details=f'Reassigne a {admin_assigned}',
        severity='info'
    )

    return jsonify({'message': 'Reclamation reassignée.', 'id': rec_id})
