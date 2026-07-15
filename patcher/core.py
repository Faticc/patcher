import os
import glob
import json
import hashlib
import zipfile
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

STATE_FILE = "patch_state.json"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state() -> Dict:
    if not os.path.exists(STATE_FILE):
        return {}
    return json.loads(Path(STATE_FILE).read_text())


def save_state(state: Dict):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))


def already_patched(jar: str, key: str, state: Dict) -> bool:
    if not os.path.exists(jar):
        return False
    return state.get(key) == sha256(jar)


def update_state(jar: str, key: str, state: Dict):
    state[key] = sha256(jar)


@dataclass
class PatchRule:
    name: str
    search_mask: str
    delete_files: List[str]
    replace_files: Dict[str, str]
    add_files: Dict[str, str]


def find_mod(mask: str) -> Optional[str]:
    files = glob.glob(mask)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def decode_base64(data: str) -> bytes:
    """Безопасное декодирование Base64."""
    return base64.b64decode(data)


def apply_patch(jar_path: str, rule: PatchRule) -> bool:
    if not os.path.exists(jar_path):
        print(f"[!] Файл {jar_path} не найден")
        return False

    tmp = jar_path + ".tmp"
    replaced = set()

    with zipfile.ZipFile(jar_path, "r") as src, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:

        for item in src.infolist():

            # Удаление по полному пути
            if item.filename in rule.delete_files:
                print(f"  - Удалён: {item.filename}")
                continue

            # Замена по полному пути
            if item.filename in rule.replace_files:
                data = decode_base64(rule.replace_files[item.filename])
                dst.writestr(item.filename, data)
                print(f"  - Заменён: {item.filename}")
                replaced.add(item.filename)
                continue

            # Обычная копия
            with src.open(item) as f:
                dst.writestr(item, f.read())


        # Добавление новых файлов (Base64 → bytes)
        for name, data_b64 in rule.add_files.items():
            if name not in replaced:
                data = decode_base64(data_b64)
                dst.writestr(name, data)
                print(f"  - Добавлен: {name}")

    os.replace(tmp, jar_path)
    return True


def run_patcher(rules: List[PatchRule]):
    print("=== ПАТЧЕР МОДОВ ===")

    state = load_state()

    for rule in rules:
        print(f"\n>>> Патч: {rule.name}")

        jar = find_mod(rule.search_mask)
        if not jar:
            print(f"  [!] Мод по маске {rule.search_mask} не найден")
            continue

        print(f"  Найден файл: {jar}")

        if already_patched(jar, rule.name, state):
            print("  -> Уже пропатчен — пропуск")
            continue

        print("  -> Применение патча...")
        if apply_patch(jar, rule):
            update_state(jar, rule.name, state)
            print("  -> Патч применён и хеш сохранён")

    save_state(state)
    print("\n=== ГОТОВО ===\n")
