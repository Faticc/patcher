import os
import glob
import json
import hashlib
import zipfile
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
    replace_files: Dict[str, bytes]
    add_files: Dict[str, bytes]


def find_mod(mask: str) -> Optional[str]:
    files = glob.glob(mask)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def apply_patch(jar_path: str, rule: PatchRule) -> bool:
    if not os.path.exists(jar_path):
        print(f"[!] Файл {jar_path} не найден")
        return False

    tmp = jar_path + ".tmp"
    replaced = set()

    with zipfile.ZipFile(jar_path, "r") as src, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:

        for item in src.infolist():
            base = os.path.basename(item.filename)

            if base in rule.delete_files:
                print(f"  - Удалён: {item.filename}")
                continue

            if base in rule.replace_files:
                dst.writestr(item.filename, rule.replace_files[base])
                print(f"  - Заменён: {item.filename}")
                replaced.add(base)
                continue

            with src.open(item) as f:
                dst.writestr(item, f.read())

        for name, data in rule.add_files.items():
            if name not in replaced:
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
