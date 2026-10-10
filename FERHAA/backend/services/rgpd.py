import re


PATTERNS_SENSIBLES = [
    ("adresse e-mail", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("telephone", r"\b(?:\+212|0)[5-7]\d{8}\b"),
    ("numero long", r"\b\d{8,}\b"),
    ("mot de passe", r"\b(?:mot de passe|password|mdp)\b|(?=[^\s]*[A-Za-z])(?=[^\s]*\d)(?=[^\s]*[@#$%^&+=!*])[^\s]{8,}"),
    ("cin", r"\b(?:(?:cin|cnie)\s*:?\s*)?[A-Z]{1,2}\d{5,7}\b"),
]


def normaliser_texte(texte):
    texte = texte or ""
    texte = texte.strip()
    normalise = texte.lower()

    # Couvre quelques tentatives simples d'obfuscation d'e-mail.
    normalise = re.sub(r"\s*(?:\[at\]|\(at\)|arobase|at)\s*", "@", normalise)
    normalise = re.sub(r"\s*(?:\[dot\]|\(dot\)|point|dot)\s*", ".", normalise)
    return normalise.strip()


def detecter_donnee_sensible(texte):
    normalise = normaliser_texte(texte)
    normalise_compact = re.sub(r"\s+", "", normalise)
    for label, pattern in PATTERNS_SENSIBLES:
        if re.search(pattern, normalise, re.IGNORECASE):
            return label
        if normalise_compact != normalise and re.search(pattern, normalise_compact, re.IGNORECASE):
            return label
    return None


def verifier_rgpd(texte):
    """Retourne True si le texte contient une donnee personnelle sensible."""
    return detecter_donnee_sensible(texte) is not None
