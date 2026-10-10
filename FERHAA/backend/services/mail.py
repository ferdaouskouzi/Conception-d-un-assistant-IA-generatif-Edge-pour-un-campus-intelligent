"""
Service d'envoi d'emails pour FERHAA.

Utilise Flask-Mail. Si les variables SMTP ne sont pas configurées,
les emails sont simulés (affichés dans les logs) sans lever d'exception.
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_mail = None   # instance Flask-Mail, initialisée dans init_mail()
_app  = None   # référence à l'app Flask pour le contexte d'application


def init_mail(app):
    """Appelé une fois depuis app.py après la création de l'instance Flask."""
    global _mail, _app
    _app = app

    mail_server = os.environ.get('MAIL_SERVER', '')
    if not mail_server:
        logger.warning('[mail] MAIL_SERVER non configuré — emails désactivés (mode log).')
        return

    try:
        from flask_mail import Mail
        app.config.update(
            MAIL_SERVER=mail_server,
            MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
            MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true',
            MAIL_USERNAME=os.environ.get('MAIL_USERNAME', ''),
            MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', ''),
            MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER',
                                                os.environ.get('MAIL_USERNAME', 'noreply@ferhaa.ma')),
        )
        _mail = Mail(app)
        logger.info(f'[mail] Flask-Mail initialisé via {mail_server}.')
    except ImportError:
        logger.warning('[mail] Flask-Mail non installé — emails désactivés (mode log).')
    except Exception as exc:
        logger.error(f'[mail] Erreur initialisation Flask-Mail : {exc}')


def _send(subject: str, recipients: list[str], body: str) -> bool:
    """
    Envoie un email en texte brut.
    Retourne True si l'envoi a réussi (ou simulé), False en cas d'erreur SMTP.
    """
    if not recipients:
        return False

    if _mail is None:
        # Mode log — pratique en développement ou sans SMTP configuré
        logger.info(
            f'[mail:SIMULÉ] À: {recipients} | Sujet: {subject}\n{body}'
        )
        return True

    try:
        from flask_mail import Message
        with _app.app_context():
            msg = Message(subject=subject, recipients=recipients, body=body)
            _mail.send(msg)
        logger.info(f'[mail] Email envoyé à {recipients} — {subject}')
        return True
    except Exception as exc:
        logger.error(f'[mail] Erreur envoi à {recipients} : {exc}')
        return False


# ── Templates métier ──────────────────────────────────────────────────────────

def notifier_admin_nouvelle_reclamation(
    admin_email: str,
    reclamation_id: int,
    source_ia: str,
    description: str,
) -> bool:
    """Notifie l'admin pédagogique qu'une nouvelle réclamation est en attente."""
    subject = f'[FERHAA] Nouvelle réclamation #{reclamation_id} — réponse IA signalée'
    body = (
        f'Une réponse IA a été signalée par un utilisateur.\n\n'
        f'  Source IA  : {source_ia or "inconnue"}\n'
        f'  Date       : {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n'
        f'Problème signalé par l\'utilisateur :\n'
        f'  "{description[:300]}{"..." if len(description) > 300 else ""}"\n\n'
        f'Accéder au tableau de bord :\n'
        f'  http://localhost:5000/admin\n\n'
        f'Identité de l\'étudiant masquée conformément au RGPD.\n'
        f'---\nFERHAA — Assistant IA ENSABM'
    )
    return _send(subject, [admin_email], body)


_DECISION_LABELS = {
    'reclamation_fondee':      'Réclamation acceptée',
    'a_surveiller':            'Réclamation à surveiller',
    'reclamation_non_fondee':  'Réclamation non fondée',
}


def notifier_etudiant_reclamation_traitee(
    student_email: str,
    reclamation_id: int,
    source_ia: str,
    reponse_admin: str,
    decision_admin: str = '',
) -> bool:
    """Notifie l'étudiant que sa réclamation a été traitée par l'admin."""
    statut_label = _DECISION_LABELS.get(decision_admin, 'Traitée')
    subject = f'[FERHAA] Réponse à votre réclamation #{reclamation_id} — {statut_label}'
    body = (
        f'Bonjour,\n\n'
        f'Votre réclamation #{reclamation_id} a été traitée par l\'équipe pédagogique.\n\n'
        f'  Statut   : {statut_label}\n'
        f'  Date     : {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n'
        f'Réponse de l\'administrateur :\n'
        f'  "{reponse_admin}"\n\n'
        f'Si vous avez d\'autres questions, vous pouvez soumettre\n'
        f'une nouvelle réclamation depuis votre espace personnel.\n'
        f'---\nFERHAA — Assistant IA ENSABM'
    )
    return _send(subject, [student_email], body)
