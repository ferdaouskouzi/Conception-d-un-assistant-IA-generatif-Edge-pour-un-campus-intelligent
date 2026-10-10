ROLE_LABELS = {
    'student':           'Etudiant',
    'admin_it':          'Admin IT & Sécurité',
    'admin_pedagogique': 'Admin Pédagogique',
    'super_admin':       'Super Admin',
}

ROLE_PERMISSIONS = {
    'student': [
        'ask_ai',
        'generate_summary',
        'view_personal_history',
        'submit_feedback',
        'view_personal_profile',
    ],
    'admin_it': [
        'ask_ai',
        'view_personal_history',
        'submit_feedback',
        'view_admin_dashboard',
        'manage_accounts',
        'monitor_performance',
        'manage_edge_cloud',
        'view_audit_logs',
        'detect_anomalies',
        'protect_sensitive_data',
        'manage_security_risks',
    ],
    'admin_pedagogique': [
        'ask_ai',
        'view_personal_history',
        'submit_feedback',
        'view_admin_dashboard',
        'review_academic_content',
        'correct_ai_answers',
        'validate_pedagogical_quality',
    ],
    'super_admin': [
        'ask_ai',
        'generate_summary',
        'view_personal_history',
        'submit_feedback',
        'view_personal_profile',
        'view_admin_dashboard',
        'manage_accounts',
        'monitor_performance',
        'manage_edge_cloud',
        'view_audit_logs',
        'review_academic_content',
        'correct_ai_answers',
        'validate_pedagogical_quality',
        'detect_anomalies',
        'protect_sensitive_data',
        'manage_security_risks',
        'validate_ai_governance',
        'full_access',
    ],
}

DEFAULT_ADMIN_ACCOUNTS = [
    {
        'email': 'admin.it@ensabm.ac.ma',
        'prenom': 'Admin',
        'nom': 'IT',
        'role': 'admin_it',
        'filiere': 'SI',
        'annee': 'STAFF',
        'department': 'IT',
    },
    {
        'email': 'admin.pedagogique@ensabm.ac.ma',
        'prenom': 'Admin',
        'nom': 'Pedagogique',
        'role': 'admin_pedagogique',
        'filiere': 'PEDA',
        'annee': 'STAFF',
        'department': 'Pedagogie',
    },
    {
        'email': 'directeur@usms.ac.ma',
        'prenom': 'Super',
        'nom': 'Admin',
        'role': 'super_admin',
        'filiere': 'GOV',
        'annee': 'STAFF',
        'department': 'Direction',
    },
]


def get_permissions_for_role(role):
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['student'])


def has_permission(user, permission):
    permissions = user.get('permissions') or get_permissions_for_role(user.get('role', 'student'))
    return permission in permissions or 'full_access' in permissions


def generate_admin_identifiers(role, index):
    role_code = {
        'admin_it': 'AIT',
        'admin_pedagogique': 'APD',
        'super_admin': 'SUP',
    }.get(role, 'ADM')
    return {
        'special_apogee': f'{role_code}-APOGEE-{index:03d}',
        'special_cin': f'{role_code}-CIN-{index:03d}',
    }
