import re

PATTERNS_SENSIBLES = [
    r'\b\d{8,}\b',                                              # CIN / numéro étudiant
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    r'\b(0[5-7]\d{8})\b',                                      # Téléphone marocain
    r'\b(mot de passe|password|mdp)\b',                        # Mots sensibles
    r'\b(cin|cnie)\s*:?\s*[A-Z]{1,2}\d{6}\b',                 # Format CIN marocain
]

def verifier_rgpd(texte):
    """
    Retourne True si le texte contient une donnée personnelle sensible.
    """
    for pattern in PATTERNS_SENSIBLES:
        if re.search(pattern, texte, re.IGNORECASE):
            return True
    return False