from flask import Blueprint, jsonify, request, session

from routes.decorators import login_required
from services.cache import chercher_cache, sauvegarder_cache
from services.course_materials import build_course_context
from services.database import DAILY_QUESTION_LIMIT, count_questions_today, log_audit, sauvegarder
from services.rgpd import verifier_rgpd
from services.router import router

ask_bp = Blueprint('ask', __name__)


@ask_bp.route('/ask', methods=['POST'])
@login_required
def ask():
    user = session.get('user')
    try:
        question = request.json.get('question', '').strip()
        if not question:
            return jsonify({'erreur': 'Question vide.'})

        identifiant = user.get('identifiant', '')
        course_context, course_sources, course_cache_token = build_course_context(question)
        user_context = f"{user.get('filiere', '')}|{user.get('annee', '')}|{course_cache_token}"
        question_for_model = question
        if course_context:
            question_for_model = (
                f"{course_context}\n\n"
                f"Question de l'utilisateur : {question}\n\n"
                "Si les extraits sont pertinents, appuie-toi dessus en priorite."
            )

        # ── Quota journalier ─────────────────────────────────────────────────
        if count_questions_today(identifiant) >= DAILY_QUESTION_LIMIT:
            log_audit(
                identifiant, user.get('role', 'student'),
                'quota_exceeded', target='ask',
                details=f'Limite journaliere de {DAILY_QUESTION_LIMIT} questions atteinte',
                severity='warning'
            )
            return jsonify({
                'erreur': f'Limite journaliere atteinte ({DAILY_QUESTION_LIMIT} questions/jour). Revenez demain.'
            }), 429

        # ── Filtre RGPD ──────────────────────────────────────────────────────
        # Données personnelles détectées → on force le traitement local (Edge) pour garder les données en local
        donnees_sensibles = verifier_rgpd(question)
        if donnees_sensibles:
            log_audit(
                identifiant, user.get('role', 'student'),
                'rgpd_flag', target='ask',
                details='Donnees personnelles detectees — traitement route vers Edge local',
                severity='warning'
            )

        # ── Cache ────────────────────────────────────────────────────────────
        cached = chercher_cache(question_for_model, user_context)
        if cached:
            log_audit(
                identifiant, user.get('role', 'student'),
                'cache_hit', target='ask',
                details='Reponse servie depuis le cache local'
            )
            return jsonify({
                'reponse': cached,
                'source': 'cache_local',
                'temps': 0.0,
                'sources_documentaires': course_sources,
            })

        # ── Routage Cloud / Edge ─────────────────────────────────────────────
        # donnees_sensibles=True force l'Edge — les données restent en local
        reponse, duree, source, raison = router(
            question_for_model,
            user=user,
            donnees_sensibles=donnees_sensibles,
        )

        # Ne pas mettre en cache les réponses prédéfinies (fallback hors-ligne)
        if source != 'fallback_predefined':
            sauvegarder_cache(question_for_model, reponse, user_context)
        sauvegarder(question, reponse, '', duree, 0, source, identifiant)
        log_audit(
            identifiant, user.get('role', 'student'),
            'ask_ai', target=source,
            details=f'[{raison}] Question traitee via {source} en {duree}s | sources: {", ".join(course_sources) if course_sources else "aucune"}'
        )
        return jsonify({
            'reponse': reponse,
            'source': source,
            'temps': duree,
            'sources_documentaires': course_sources,
        })

    except Exception as error:
        log_audit(
            user.get('identifiant', ''), user.get('role', 'student'),
            'ask_error', target='ask',
            details=str(error), severity='critical'
        )
        return jsonify({'erreur': str(error)})
