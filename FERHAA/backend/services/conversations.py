import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
CONVERSATIONS_DIR = os.path.join(LOGS_DIR, 'conversations')
EVENTS_DIR = os.path.join(LOGS_DIR, 'events')


def _ensure_dirs():
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    os.makedirs(EVENTS_DIR, exist_ok=True)


def _safe_identifiant(user_identifiant):
    return ''.join(ch for ch in str(user_identifiant or 'anonymous') if ch.isalnum() or ch in ('-', '_'))


def _conversation_path(user_identifiant):
    _ensure_dirs()
    return os.path.join(CONVERSATIONS_DIR, f'{_safe_identifiant(user_identifiant)}.json')


def _events_path(user_identifiant):
    _ensure_dirs()
    return os.path.join(EVENTS_DIR, f'{_safe_identifiant(user_identifiant)}.jsonl')


def _sort_conversations(conversations):
    """Trie les conversations du plus récent au plus ancien (ID numérique décroissant)."""
    def sort_key(item):
        item_id = str(item.get('id') or '')
        try:
            return (int(item_id), item.get('time') or '')
        except ValueError:
            return (0, item.get('time') or '')
    conversations.sort(key=sort_key, reverse=True)
    return conversations


def load_conversations(user_identifiant):
    path = _conversation_path(user_identifiant)
    if not os.path.exists(path):
        return []

    with open(path, 'r', encoding='utf-8') as file:
        content = file.read().strip()

    if not content:
        return []

    try:
        data = json.loads(content)
        conversations = data if isinstance(data, list) else []
        return _sort_conversations(conversations)
    except json.JSONDecodeError:
        # Tolerance for older corrupted files containing multiple JSON values
        # appended one after another. We decode them sequentially and merge
        # every list payload we can recover.
        decoder = json.JSONDecoder()
        items = []
        index = 0
        length = len(content)

        while index < length:
            while index < length and content[index].isspace():
                index += 1
            if index >= length:
                break

            try:
                obj, next_index = decoder.raw_decode(content, index)
            except json.JSONDecodeError:
                break

            if isinstance(obj, list):
                items.extend(obj)
            index = next_index

        return _sort_conversations(items)


def _normalize_message(message):
    return {
        'role': str(message.get('role', '')).strip(),
        'text': str(message.get('text', '')).strip(),
        'source': message.get('source'),
        'temps': message.get('temps'),
        'time': str(message.get('time', '')).strip(),
    }


def _normalize_conversation(conversation):
    messages = [
        _normalize_message(message)
        for message in conversation.get('messages', [])
        if isinstance(message, dict) and str(message.get('text', '')).strip()
    ]
    return {
        'id': str(conversation.get('id', '')).strip(),
        'title': str(conversation.get('title', 'Nouvelle discussion')).strip() or 'Nouvelle discussion',
        'time': str(conversation.get('time', '')).strip(),
        'messages': messages,
    }


def _is_error_message(message):
    text = str(message.get('text', '')).lower()
    if not text:
        return False
    return (
        'erreur' in text
        or 'indisponible' in text
        or 'non authentifi' in text
        or 'question vide' in text
        or 'refus rgpd' in text
        or 'connexion au serveur' in text
    )


def is_conversation_usable(conversation):
    messages = conversation.get('messages', [])
    if not messages:
        return False
    return any(
        msg.get('role') == 'ai' and not _is_error_message(msg)
        for msg in messages
    ) or any(msg.get('role') == 'user' for msg in messages[1:])


def _merge_conversations(existing, incoming):
    merged = {}

    for conversation in existing + incoming:
        normalized = _normalize_conversation(conversation)
        if not normalized['id']:
            continue

        current = merged.get(normalized['id'])
        if not current:
            merged[normalized['id']] = normalized
            continue

        by_key = {}
        for message in current['messages'] + normalized['messages']:
            key = (
                message.get('role'),
                message.get('text'),
                message.get('time'),
                message.get('source')
            )
            by_key[key] = message

        current['messages'] = list(by_key.values())
        current['title'] = normalized['title'] if normalized['title'] != 'Nouvelle discussion' else current['title']
        current['time'] = normalized['time'] or current['time']

    conversations = [
        conversation for conversation in merged.values()
        if conversation.get('messages')
    ]
    conversations.sort(key=lambda item: (item.get('time') or '', item.get('id') or ''), reverse=True)
    return conversations


def write_event_log(user_identifiant, action, payload=None):
    path = _events_path(user_identifiant)
    event = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': action,
        'payload': payload or {},
    }
    with open(path, 'a', encoding='utf-8') as file:
        file.write(json.dumps(event, ensure_ascii=False) + '\n')


def sync_conversations(user_identifiant, conversations):
    existing = load_conversations(user_identifiant)
    merged = _merge_conversations(existing, conversations)

    path = _conversation_path(user_identifiant)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(merged, file, ensure_ascii=False, indent=2)

    write_event_log(
        user_identifiant,
        'sync_conversations',
        {
            'conversation_count': len(merged),
            'message_count': sum(len(item.get('messages', [])) for item in merged),
        }
    )
    return merged


def save_conversations(user_identifiant, conversations, action='save_conversations'):
    path = _conversation_path(user_identifiant)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(conversations, file, ensure_ascii=False, indent=2)

    write_event_log(
        user_identifiant,
        action,
        {
            'conversation_count': len(conversations),
            'message_count': sum(len(item.get('messages', [])) for item in conversations),
        }
    )
    return conversations


def delete_conversation(user_identifiant, conversation_id):
    conversations = load_conversations(user_identifiant)
    filtered = [item for item in conversations if item.get('id') != conversation_id]
    save_conversations(user_identifiant, filtered, action='delete_conversation')
    return filtered


def delete_all_conversations(user_identifiant):
    """Supprime toutes les conversations d'un utilisateur."""
    path = _conversation_path(user_identifiant)
    count = len(load_conversations(user_identifiant))
    if os.path.exists(path):
        os.remove(path)
    write_event_log(user_identifiant, 'delete_all_conversations', {'removed': count})
    return count


def delete_error_conversations(user_identifiant):
    conversations = load_conversations(user_identifiant)
    filtered = [item for item in conversations if is_conversation_usable(item)]
    removed = len(conversations) - len(filtered)
    save_conversations(user_identifiant, filtered, action='delete_error_conversations')
    return filtered, removed


def get_log_files_for_user(user_identifiant):
    conversation_path = _conversation_path(user_identifiant)
    events_path = _events_path(user_identifiant)
    return {
        'conversation_file': conversation_path,
        'events_file': events_path,
        'conversation_exists': os.path.exists(conversation_path),
        'events_exists': os.path.exists(events_path),
    }
