import hashlib
import os
import re
import sqlite3
from pathlib import Path

from werkzeug.utils import secure_filename

from services.database import DB_PATH

BASE_DIR = Path(__file__).resolve().parent.parent
COURSE_DIR = BASE_DIR / 'data' / 'course_materials'
ALLOWED_EXTENSIONS = {'.pdf'}


def ensure_course_dir():
    COURSE_DIR.mkdir(parents=True, exist_ok=True)


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def _safe_title(filename: str) -> str:
    stem = Path(filename or '').stem
    return _normalize_text(stem.replace('_', ' ').replace('-', ' ')) or 'Document de cours'


def _clean_extracted_text(text: str) -> str:
    """Nettoie le texte extrait des PDFs : artefacts d'encodage courants."""
    if not text:
        return ''
    replacements = [
        ('\x00', ''), ('\ufffd', ''),
        ('\u0092', "'"), ('\u0091', "'"), ('\u0093', '"'), ('\u0094', '"'),
        ('\u0096', '-'), ('\u0097', '-'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _extract_pdf_text(path: Path) -> tuple[str, int, str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return '', 0, 'missing_pypdf'

    try:
        reader = PdfReader(str(path))
        texts = []
        for page in reader.pages:
            try:
                page_text = _clean_extracted_text(page.extract_text() or '')
                texts.append(page_text)
            except Exception:
                continue
        content = _normalize_text('\n'.join(texts))
        if content:
            return content, len(reader.pages), 'ready'
        # PDF scanné/image sans couche texte
        return '', len(reader.pages), 'scanned_pdf'
    except Exception:
        return '', 0, 'extract_error'


def save_course_material(file_storage, uploaded_by: str, department: str = '') -> dict:
    ensure_course_dir()
    original_name = secure_filename(file_storage.filename or '')
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError('format_non_supporte')

    raw = file_storage.read()
    file_storage.stream.seek(0)
    digest = hashlib.sha256(raw).hexdigest()
    stored_name = f'{digest[:16]}_{original_name}'
    path = COURSE_DIR / stored_name
    if not path.exists():
        file_storage.save(path)

    text_content, page_count, status = _extract_pdf_text(path)
    excerpt = text_content[:1200]

    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO course_materials (
            title, filename, stored_name, file_path, mime_type, sha256,
            uploaded_by, department, page_count, text_excerpt, content_text, status, uploaded_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
        ''',
        (
            _safe_title(original_name),
            original_name,
            stored_name,
            str(path),
            'application/pdf',
            digest,
            uploaded_by,
            department,
            page_count,
            excerpt,
            text_content,
            status,
        )
    )
    material_id = cur.lastrowid
    conn.commit()
    conn.close()
    return get_course_material(material_id)


def list_course_materials():
    ensure_course_dir()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT id, title, filename, uploaded_by, department, page_count,
               text_excerpt, status, uploaded_at
        FROM course_materials
        ORDER BY id DESC
        '''
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_course_material(material_id: int):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT id, title, filename, uploaded_by, department, page_count,
               text_excerpt, status, uploaded_at
        FROM course_materials WHERE id = ?
        ''',
        (material_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def count_course_materials() -> int:
    conn = _get_connection()
    cur = conn.cursor()
    count = cur.execute('SELECT COUNT(*) FROM course_materials').fetchone()[0]
    conn.close()
    return count


def search_course_materials(question: str, limit: int = 2):
    question = _normalize_text(question).lower()
    if not question:
        return []
    keywords = [token for token in re.findall(r'[a-zA-Z0-9]{4,}', question) if len(token) >= 4]
    if not keywords:
        return []

    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT id, title, filename, text_excerpt, content_text, status
        FROM course_materials
        WHERE status = 'ready' AND content_text != ''
        '''
    )
    candidates = []
    for row in cur.fetchall():
        item = dict(row)
        haystack = (item.get('content_text') or '').lower()
        score = sum(haystack.count(keyword) for keyword in keywords)
        if score <= 0:
            continue
        snippet = item.get('text_excerpt') or ''
        if len(haystack) > 200:
            for keyword in keywords:
                idx = haystack.find(keyword)
                if idx >= 0:
                    start = max(0, idx - 120)
                    end = min(len(item['content_text']), idx + 280)
                    snippet = _normalize_text(item['content_text'][start:end])
                    break
        candidates.append({
            'id': item['id'],
            'title': item['title'],
            'filename': item['filename'],
            'score': score,
            'snippet': snippet[:500],
        })
    conn.close()
    candidates.sort(key=lambda x: (-x['score'], x['title']))
    return candidates[:limit]


def build_course_context(question: str) -> tuple[str, list[str], str]:
    matches = search_course_materials(question)
    if not matches:
        return '', [], f'materials:{count_course_materials()}'
    blocks = []
    labels = []
    for match in matches:
        labels.append(match['title'])
        blocks.append(f"Source: {match['title']}\nExtrait: {match['snippet']}")
    context = (
        "Corpus pedagogique local a privilegier si pertinent.\n"
        "Ne cite pas ces extraits comme verite absolue si le contenu est ambigu.\n\n"
        + "\n\n".join(blocks)
    )
    cache_token = 'materials:' + '|'.join(str(match['id']) for match in matches)
    return context, labels, cache_token
