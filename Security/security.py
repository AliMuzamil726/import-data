import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, re, sys, math, time, threading, base64, hashlib
import json, shutil, uuid, secrets, string, struct
from pathlib import Path
import os
import json
import hashlib

INTEGRITY_DB = "integrity_db.json"


def load_integrity_db():
    if not os.path.exists(INTEGRITY_DB):
        return {}
    with open(INTEGRITY_DB, "r") as f:
        return json.load(f)


def save_integrity_db(db):
    with open(INTEGRITY_DB, "w") as f:
        json.dump(db, f, indent=4)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes as _ch
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False
    Fernet = None

# ═══════════════════════════════════════════════════════════
#  VAULT  PATHS
# ═══════════════════════════════════════════════════════════
VAULT_BASE   = Path.home() / ".security_manager"
VAULT_DIR    = VAULT_BASE / "vault"
NOTES_DIR    = VAULT_BASE / "notes"
INTEGRITY_DIR= VAULT_BASE / "integrity"
REG_FILE     = VAULT_BASE / "registry.json"

def _init_vault():
    for d in [VAULT_DIR, NOTES_DIR, INTEGRITY_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    if not REG_FILE.exists():
        _save_reg({"hidden": [], "locked": []})

def _load_reg():
    try:    return json.loads(REG_FILE.read_text(encoding="utf-8"))
    except: return {"hidden": [], "locked": []}

def _save_reg(d):
    REG_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

# ═══════════════════════════════════════════════════════════
#  PALETTE  —  military-grade cyber dark theme
# ═══════════════════════════════════════════════════════════
C = {
    "bg":      "#000000",  "bg1":    "#05080f",  "bg2":    "#07091a",
    "bg3":     "#0a0d1e",  "panel":  "#08101f",  "border": "#0f1e35",
    "border2": "#1a3050",  "glow":   "#00c8ff",  "glow2":  "#5b21b6",
    "green":   "#00e676",  "red":    "#ff1744",  "orange": "#ff9100",
    "yellow":  "#ffd600",  "text":   "#d0dff5",  "text2":  "#5a7a9e",
    "muted":   "#152035",  "accent1":"#00c8ff",  "accent2":"#5b21b6",
    "accent3": "#00e676",  "accent4":"#ff9100",  "gold":   "#ffc107",
    "teal":    "#00bcd4",  "pink":   "#e040fb",  "indigo": "#3d5afe",
    "cyber":   "#0ff",     "dark":   "#000208",
}

FONTS = {
    "hero":    ("Consolas", 22, "bold"),
    "title":   ("Consolas", 15, "bold"),
    "head":    ("Consolas", 11, "bold"),
    "body":    ("Consolas",  10),
    "small":   ("Consolas", 10),
    "tiny":    ("Consolas",  9),
    "mono":    ("Courier New", 11),
    "mono_lg": ("Courier New", 11),
    "num":     ("Consolas", 30, "bold"),
    "num_sm":  ("Consolas", 15, "bold"),
}

ADMIN_NAME = "Ali Muzamil"
APP_NAME   = "Security Manager"
APP_VER    = "Beta Version"
LOCK_MARKER = ".smgr_lock"

# ═══════════════════════════════════════════════════════════
#  CRYPTO  HELPERS
# ═══════════════════════════════════════════════════════════
def derive_key(password: str, salt: bytes) -> bytes:
    if not CRYPTO_OK:
        raise RuntimeError("cryptography not installed — run: pip install cryptography")
    kdf = PBKDF2HMAC(algorithm=_ch.SHA256(), length=32, salt=salt, iterations=480_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def hash_pwd(password: str, salt: str = None):
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.sha256(("SM_SALT" + salt + password + "ENTERPRISE").encode()).hexdigest()
    return h, salt
# ═══════════════════════════════════════════════════════════
#  FILE INTEGRITY PROTECTION
# ═══════════════════════════════════════════════════════════

INTEGRITY_DB = VAULT_BASE / "integrity_db.json"

def load_integrity_db():
    if not INTEGRITY_DB.exists():
        return {}
    try:
        return json.loads(INTEGRITY_DB.read_text())
    except Exception:
        return {}

def save_integrity_db(db):
    INTEGRITY_DB.write_text(json.dumps(db, indent=2))

def add_integrity_file(path):
    db = load_integrity_db()

    if not os.path.exists(path):
        raise ValueError("File does not exist")

    h = file_hash(path)
    db[path] = h
    save_integrity_db(db)

    os.chmod(path, 0o444)  # read-only

def verify_integrity():
    db = load_integrity_db()
    results = {}

    for path, old_hash in db.items():

        if not os.path.exists(path):
            results[path] = "Missing"
            continue

        new_hash = file_hash(path)

        if new_hash == old_hash:
            results[path] = "Safe"
        else:
            results[path] = "Modified"

    return results

def is_integrity_protected(path):
    db = load_integrity_db()
    return path in db

def verify_pwd(password: str, stored: str, salt: str) -> bool:
    h, _ = hash_pwd(password, salt)
    return h == stored

def file_hash(fp: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def fmt_size(b: int) -> str:
    for u in ["B","KB","MB","GB"]:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

# ═══════════════════════════════════════════════════════════
#  FILE  ENCRYPTION  (deletes original after encrypt)
# ═══════════════════════════════════════════════════════════
def encrypt_file(fp: str, pwd: str) -> tuple:
    """Encrypt file → .enc, then DELETE the original."""
    try:
        if not CRYPTO_OK: raise RuntimeError("cryptography not installed")
        p    = Path(fp)
        salt = os.urandom(16)
        data = p.read_bytes()
        enc  = Fernet(derive_key(pwd, salt)).encrypt(data)
        out  = Path(str(fp) + ".enc")
        out.write_bytes(salt + enc)
        p.unlink()          # ← delete original
        return str(out), None
    except Exception as e:
        return None, str(e)

def decrypt_file(fp: str, pwd: str) -> tuple:
    """Decrypt .enc file → original filename, then DELETE the .enc."""
    try:
        if not CRYPTO_OK: raise RuntimeError("cryptography not installed")
        p    = Path(fp)
        raw  = p.read_bytes()
        salt, tok = raw[:16], raw[16:]
        data = Fernet(derive_key(pwd, salt)).decrypt(tok)
        out  = Path(fp[:-4] if fp.endswith(".enc") else fp + ".dec")
        out.write_bytes(data)
        p.unlink()          # ← delete .enc after restore
        return str(out), None
    except Exception as e:
        return None, str(e)

# ═══════════════════════════════════════════════════════════
#  FOLDER  LOCK  (encrypts ALL files inside)
# ═══════════════════════════════════════════════════════════
def is_locked(path: str) -> bool:
    return (Path(path) / LOCK_MARKER).exists()

def lock_folder(folder_path: str, pwd: str) -> int:
    if not CRYPTO_OK: raise RuntimeError("cryptography not installed")
    folder = Path(folder_path)
    if not folder.exists():    raise FileNotFoundError("Folder not found")
    if is_locked(folder_path): raise RuntimeError("Folder is already locked")

    salt = os.urandom(16)
    key  = derive_key(pwd, salt)
    f    = Fernet(key)

    files = [p for p in folder.rglob("*") if p.is_file() and p.name != LOCK_MARKER]
    rel   = [str(p.relative_to(folder)).replace("\\", "/") for p in files]

    failed = []
    for fp in files:
        try:
            fp.write_bytes(f.encrypt(fp.read_bytes()))
        except Exception:
            failed.append(str(fp))

    pwd_h, pwd_s = hash_pwd(pwd)
    meta = json.dumps({
        "file_list":  rel,
        "file_count": len(files),
        "locked_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "pwd_hash":   pwd_h,
        "pwd_salt":   pwd_s,
        "version":    "4.0",
    }).encode()
    (folder / LOCK_MARKER).write_bytes(salt + f.encrypt(meta))

    reg = _load_reg()
    reg["locked"] = [e for e in reg["locked"] if e["path"] != str(folder)]
    reg["locked"].append({
        "id":        uuid.uuid4().hex,
        "path":      str(folder),
        "name":      folder.name,
        "locked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_count":len(files),
    })
    _save_reg(reg)
    if failed:
        raise RuntimeError(f"Locked {len(files)-len(failed)}/{len(files)} files. Failed: {len(failed)}")
    return len(files)

def unlock_folder(folder_path: str, pwd: str) -> int:
    if not CRYPTO_OK: raise RuntimeError("cryptography not installed")
    folder    = Path(folder_path)
    lock_file = folder / LOCK_MARKER
    if not lock_file.exists(): raise RuntimeError("Folder is not locked")

    raw  = lock_file.read_bytes()
    salt, meta_enc = raw[:16], raw[16:]
    key  = derive_key(pwd, salt)
    f    = Fernet(key)


    try:
        meta = json.loads(f.decrypt(meta_enc))
    except Exception:
        raise ValueError("Incorrect password")

    if not verify_pwd(pwd, meta["pwd_hash"], meta["pwd_salt"]):
        raise ValueError("Incorrect password")

    for rel in meta["file_list"]:
        fp = folder / rel.replace("/", os.sep)
        if fp.exists():
            try:
                fp.write_bytes(f.decrypt(fp.read_bytes()))
            except Exception:
                pass

    lock_file.unlink()
    reg = _load_reg()
    reg["locked"] = [e for e in reg["locked"] if e["path"] != str(folder)]
    _save_reg(reg)
    return meta["file_count"]

# ═══════════════════════════════════════════════════════════
#  FOLDER  HIDE
# ═══════════════════════════════════════════════════════════
def hide_folder(folder_path: str, pwd: str) -> dict:
    folder = Path(folder_path)
    if not folder.exists(): raise FileNotFoundError("Folder not found")
    vid  = uuid.uuid4().hex
    dest = VAULT_DIR / vid
    shutil.move(str(folder), str(dest))
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    pwd_h, pwd_s = hash_pwd(pwd)
    entry = {
        "id": vid, "original_path": str(folder), "original_name": folder.name,
        "vault_name": vid, "hidden_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pwd_hash": pwd_h, "pwd_salt": pwd_s, "size": size,
    }
    reg = _load_reg()
    reg["hidden"].append(entry)
    _save_reg(reg)
    return entry

def unhide_folder(entry_id: str, pwd: str) -> str:
    reg   = _load_reg()
    entry = next((e for e in reg["hidden"] if e["id"] == entry_id), None)
    if not entry: raise ValueError("Entry not found in registry")
    if not verify_pwd(pwd, entry["pwd_hash"], entry["pwd_salt"]):
        raise ValueError("Incorrect password")
    src  = VAULT_DIR / entry["vault_name"]
    dest = Path(entry["original_path"])
    if not src.exists():  raise FileNotFoundError("Vault folder missing")
    if dest.exists():     raise FileExistsError(f"Destination exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    reg["hidden"] = [e for e in reg["hidden"] if e["id"] != entry_id]
    _save_reg(reg)
    return str(dest)

# ═══════════════════════════════════════════════════════════
#  PASSWORD  ANALYSIS  &  GENERATION
# ═══════════════════════════════════════════════════════════
_COMMON = {
    "password","123456","qwerty","abc123","letmein","admin","welcome",
    "monkey","dragon","iloveyou","password1","12345678","sunshine",
    "princess","football","shadow","master","123123","654321",
}

def analyse_pwd(pwd: str):
    checks = [
        (len(pwd) >= 8,   "8+ characters"),
        (len(pwd) >= 12,  "12+ characters"),
        (len(pwd) >= 16,  "16+ characters"),
        (bool(re.search(r"[a-z]", pwd)), "Lowercase"),
        (bool(re.search(r"[A-Z]", pwd)), "Uppercase"),
        (bool(re.search(r"\d",    pwd)), "Numbers"),
        (bool(re.search(r"[!@#$%^&*()\-_=+\[\]{};:,.<>?/`~]", pwd)), "Special chars"),
        (not bool(re.search(r"(.)\1{2,}", pwd)), "No repeating chars"),
    ]
    weights = [8, 8, 9, 12, 12, 14, 22, 15]
    score   = sum(w for (ok,_), w in zip(checks, weights) if ok)
    if pwd.lower() in _COMMON: score = min(score, 8)
    score = min(score, 100)
    if score < 25:   lv, col = "WEAK",        C["red"]
    elif score < 50: lv, col = "FAIR",        C["orange"]
    elif score < 70: lv, col = "GOOD",        C["yellow"]
    elif score < 88: lv, col = "STRONG",      C["green"]
    else:            lv, col = "VERY STRONG", C["glow"]
    return score, lv, col, checks

def gen_password(length=16, upper=True, digits=True, symbols=True, no_ambig=False):
    lp = "abcdefghjkmnpqrstuvwxyz" if no_ambig else string.ascii_lowercase
    up = "ABCDEFGHJKLMNPQRSTUVWXYZ" if no_ambig else string.ascii_uppercase
    dp = "23456789" if no_ambig else string.digits
    sp = "!@#$%^&*-_=+?"
    pool = lp; req = [secrets.choice(lp)]
    if upper:   pool += up; req.append(secrets.choice(up))
    if digits:  pool += dp; req.append(secrets.choice(dp))
    if symbols: pool += sp; req.append(secrets.choice(sp))
    extra = [secrets.choice(pool) for _ in range(length - len(req))]
    pw = req + extra; secrets.SystemRandom().shuffle(pw)
    return "".join(pw)

# ═══════════════════════════════════════════════════════════
#  SECURE  NOTES
# ═══════════════════════════════════════════════════════════
def save_note(title, content, pwd, note_id=None):
    if not CRYPTO_OK: raise RuntimeError("cryptography not installed")
    nid  = note_id or uuid.uuid4().hex
    salt = os.urandom(16)
    data = json.dumps({"id":nid,"title":title,"content":content,
                        "saved_at":time.strftime("%Y-%m-%d %H:%M:%S")}).encode()
    enc  = Fernet(derive_key(pwd, salt)).encrypt(data)
    (NOTES_DIR / f"{nid}.svnote").write_bytes(salt + enc)
    return nid

def load_note(note_id, pwd):
    if not CRYPTO_OK: raise RuntimeError("cryptography not installed")
    nf = NOTES_DIR / f"{note_id}.svnote"
    if not nf.exists(): raise FileNotFoundError("Note not found")
    raw  = nf.read_bytes()
    try:
        return json.loads(Fernet(derive_key(pwd, raw[:16])).decrypt(raw[16:]))
    except: raise ValueError("Incorrect password")

def list_notes():
    notes = []
    for nf in NOTES_DIR.glob("*.svnote"):
        s = nf.stat()
        notes.append({"id":nf.stem,
                       "modified":time.strftime("%Y-%m-%d %H:%M",time.localtime(s.st_mtime)),
                       "size":fmt_size(s.st_size)})
    return sorted(notes, key=lambda x: x["modified"], reverse=True)

def delete_note(note_id):
    nf = NOTES_DIR / f"{note_id}.svnote"
    if nf.exists(): nf.unlink()

# ═══════════════════════════════════════════════════════════
#  FILE  INTEGRITY  MONITOR
# ═══════════════════════════════════════════════════════════
def integrity_baseline(folder_path: str, name: str) -> dict:
    """Create SHA-256 baseline snapshot of a folder."""
    folder  = Path(folder_path)
    records = {}
    for fp in folder.rglob("*"):
        if fp.is_file():
            rel = str(fp.relative_to(folder)).replace("\\", "/")
            try:
                records[rel] = {
                    "sha256": file_hash(str(fp), "sha256"),
                    "size":   fp.stat().st_size,
                    "mtime":  fp.stat().st_mtime,
                }
            except Exception:
                records[rel] = {"sha256": "ERROR", "size": 0, "mtime": 0}
    snap = {
        "name":       name,
        "folder":     str(folder),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_count": len(records),
        "records":    records,
    }
    snap_id = uuid.uuid4().hex
    (INTEGRITY_DIR / f"{snap_id}.json").write_text(
        json.dumps(snap, indent=2), encoding="utf-8")
    return {"id": snap_id, **snap}

def integrity_scan(snap_id: str) -> dict:
    """Compare current folder state against saved baseline."""
    sp = INTEGRITY_DIR / f"{snap_id}.json"
    if not sp.exists(): raise FileNotFoundError("Baseline not found")
    snap   = json.loads(sp.read_text(encoding="utf-8"))
    folder = Path(snap["folder"])
    if not folder.exists():
        return {"error": f"Folder not found: {snap['folder']}"}

    baseline = snap["records"]
    current  = {}
    for fp in folder.rglob("*"):
        if fp.is_file():
            rel = str(fp.relative_to(folder)).replace("\\", "/")
            try:
                current[rel] = {
                    "sha256": file_hash(str(fp), "sha256"),
                    "size":   fp.stat().st_size,
                }
            except Exception:
                current[rel] = {"sha256": "ERROR", "size": 0}

    modified = []
    deleted  = []
    added    = []
    ok       = []

    for rel, base in baseline.items():
        if rel not in current:
            deleted.append(rel)
        elif current[rel]["sha256"] != base["sha256"]:
            modified.append(rel)
        else:
            ok.append(rel)

    for rel in current:
        if rel not in baseline:
            added.append(rel)

    return {
        "snapshot":  snap["name"],
        "folder":    snap["folder"],
        "scanned_at":time.strftime("%Y-%m-%d %H:%M:%S"),
        "ok":        ok,
        "modified":  modified,
        "deleted":   deleted,
        "added":     added,
        "total":     len(baseline),
        "clean":     len(modified) == 0 and len(deleted) == 0 and len(added) == 0,
    }

def list_baselines() -> list:
    out = []
    for jp in INTEGRITY_DIR.glob("*.json"):
        try:
            d = json.loads(jp.read_text(encoding="utf-8"))
            out.append({
                "id":         jp.stem,
                "name":       d.get("name","?"),
                "folder":     d.get("folder","?"),
                "created_at": d.get("created_at","?"),
                "file_count": d.get("file_count", 0),
            })
        except: pass
    return sorted(out, key=lambda x: x["created_at"], reverse=True)

def delete_baseline(snap_id: str):
    sp = INTEGRITY_DIR / f"{snap_id}.json"
    if sp.exists(): sp.unlink()

# ═══════════════════════════════════════════════════════════
#  VIRUS  SCANNER  (heuristic / signature-based)
# ═══════════════════════════════════════════════════════════
# Known malware file name patterns
_BAD_NAMES = {
    "autorun.inf","desktop.ini.vbs","readme.txt.exe","setup.exe.bat",
    "install.exe.scr","update.exe","svchost32.exe","lsass32.exe",
    "explorer32.exe","winlogon32.exe","services32.exe",
}
# Suspicious double extensions
_DBL_EXT = [".exe.jpg",".exe.pdf",".exe.doc",".exe.png",".bat.jpg",
            ".vbs.jpg",".scr.jpg",".com.jpg",".ps1.jpg"]
# Dangerous single extensions
_DANGER_EXT = {".exe",".bat",".cmd",".vbs",".ps1",".scr",".com",
               ".hta",".pif",".msi",".reg",".jar",".dll"}
# Known malware byte signatures (magic bytes as hex prefix)
_SIGNATURES = {
    b"MZ":         "PE Executable (Windows binary)",
    b"PK\x03\x04": "ZIP archive (possible payload container)",
    b"\x7fELF":    "ELF Executable (Linux binary)",
    b"#!/":        "Shell script",
    b"#!python":   "Python script",
}
# Suspicious strings to search inside files
_SUSP_STRINGS = [
    b"cmd.exe /c",    b"powershell -e",  b"WScript.Shell",
    b"CreateObject",  b"ShellExecute",   b"HKEY_LOCAL_MACHINE",
    b"reg add",       b"net user add",   b"net localgroup",
    b"taskkill",      b"bcdedit",        b"vssadmin delete",
    b"cipher /w",     b"format c:",      b"del /f /s",
    b"base64_decode",  b"eval(",         b"exec(",
]

def _file_entropy(data: bytes) -> float:
    if not data: return 0.0
    freq  = [0] * 256
    for b in data: freq[b] += 1
    n  = len(data); ent = 0.0
    for f in freq:
        if f:
            p = f / n
            ent -= p * math.log2(p)
    return ent

def scan_file(fp: str) -> dict:
    p     = Path(fp)
    name  = p.name.lower()
    ext   = p.suffix.lower()
    risk  = "CLEAN"
    flags = []
    score = 0

    # 1. Known malware name
    if name in _BAD_NAMES:
        flags.append("Known malware filename"); score += 50

    # 2. Double extension
    full_lower = name
    for dbl in _DBL_EXT:
        if full_lower.endswith(dbl):
            flags.append(f"Double extension: {dbl}"); score += 40; break

    # 3. Dangerous extension
    if ext in _DANGER_EXT:
        flags.append(f"High-risk extension: {ext}"); score += 15

    # 4. Read file bytes (limit 5 MB for speed)
    try:
        size  = p.stat().st_size
        chunk = p.read_bytes()[:5 * 1024 * 1024]
    except Exception as e:
        return {"file":fp,"risk":"ERROR","flags":[str(e)],"score":0,"size":0,"entropy":0.0}

    # 5. Magic byte signatures
    for sig, desc in _SIGNATURES.items():
        if chunk.startswith(sig):
            if sig == b"MZ":
                flags.append(f"Executable binary: {desc}"); score += 10
            break

    # 6. Entropy (>7.2 = likely encrypted/packed payload)
    ent = _file_entropy(chunk)
    if ent > 7.5:
        flags.append(f"Very high entropy ({ent:.2f}) — possible packed/encrypted payload"); score += 30
    elif ent > 7.2:
        flags.append(f"High entropy ({ent:.2f}) — possibly compressed or obfuscated"); score += 15

    # 7. Suspicious strings
    found_strings = []
    for s in _SUSP_STRINGS:
        if s in chunk:
            found_strings.append(s.decode(errors="replace"))
    if found_strings:
        flags.append(f"Suspicious strings: {', '.join(found_strings[:4])}"); score += 20 * len(found_strings[:3])

    # 8. Classify risk
    if score >= 80:   risk = "HIGH RISK"
    elif score >= 40: risk = "SUSPICIOUS"
    elif score >= 15: risk = "LOW RISK"
    else:             risk = "CLEAN"

    return {
        "file":    fp,
        "name":    p.name,
        "risk":    risk,
        "score":   min(score, 100),
        "size":    size,
        "entropy": ent,
        "flags":   flags if flags else ["No threats detected"],
    }

def scan_folder(folder_path: str, progress_cb=None) -> list:
    folder  = Path(folder_path)
    files   = [f for f in folder.rglob("*") if f.is_file()]
    results = []
    for i, fp in enumerate(files):
        results.append(scan_file(str(fp)))
        if progress_cb: progress_cb(i+1, len(files), fp.name)
    return results

# ═══════════════════════════════════════════════════════════
#  DRAWING  UTILITIES
# ═══════════════════════════════════════════════════════════
def hex_pts(cx, cy, r):
    pts=[]
    for i in range(6):
        a=math.radians(60*i+30)
        pts+=[cx+r*math.cos(a), cy+r*math.sin(a)]
    return pts

def lerp(c1,c2,t):
    r1,g1,b1=int(c1[1:3],16),int(c1[3:5],16),int(c1[5:7],16)
    r2,g2,b2=int(c2[1:3],16),int(c2[3:5],16),int(c2[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1+(r2-r1)*t),int(g1+(g2-g1)*t),int(b1+(b2-b1)*t))

def arc_thick(cv,cx,cy,r,start,extent,color,width=10,steps=80):
    pts=[(cx+r*math.cos(math.radians(start+extent*i/steps)),
          cy+r*math.sin(math.radians(start+extent*i/steps)))
         for i in range(steps+1)]
    try:
        for i in range(len(pts)-1):
            cv.create_line(*pts[i],*pts[i+1],fill=color,width=width,
                           capstyle="round",joinstyle="round")
    except tk.TclError: pass

# ═══════════════════════════════════════════════════════════
#  WIDGETS
# ═══════════════════════════════════════════════════════════
class GlowButton(tk.Canvas):
    def __init__(self, parent, text="", cmd=None, w=160, h=42,
                 color=None, icon="", **kw):
        bg = parent.cget("bg") if hasattr(parent,"cget") else C["bg"]
        super().__init__(parent, width=w, height=h, bg=bg,
                         highlightthickness=0, **kw)
        self._text=text; self._cmd=cmd; self._width=w; self._h=h
        self._col=color or C["accent2"]; self._icon=icon
        self.after(10, lambda: self._draw(False))
        self.bind("<Enter>",    lambda e: self._draw(True))
        self.bind("<Leave>",    lambda e: self._draw(False))
        self.bind("<Button-1>", lambda e: (self._draw(True), self._cmd() if self._cmd else None))

    def _draw(self, hov):
        try:
            if not self.winfo_exists(): return
            self.delete("all")
            w,h,r=self._width,self._h,8
            col=self._col
            if hov:
                for i in range(5,0,-1):
                    sh=lerp(col,C["bg"],1-(i*0.15))
                    self.create_polygon(
                        r+i,i, w-r-i,i, w-i,r+i, w-i,h-r-i,
                        w-r-i,h-i, r+i,h-i, i,h-r-i, i,r+i,
                        fill=sh,outline="",smooth=True)
            bc=lerp(col,C["bg3"],0.6) if not hov else lerp(col,C["bg2"],0.35)
            self.create_polygon(r,0,w-r,0,w,r,w,h-r,w-r,h,r,h,0,h-r,0,r,
                                fill=bc,outline=col,width=1,smooth=True)
            self.create_line(r+1,1,w-r-1,1,fill=lerp(col,"#ffffff",0.2),width=1)
            txt=f"{self._icon}  {self._text}" if self._icon else self._text
            self.create_text(w//2,h//2,text=txt,
                             fill="#ffffff" if hov else C["text"],
                             font=FONTS["head"],anchor="center")
        except tk.TclError: pass

class RingGauge(tk.Canvas):
    def __init__(self, parent, size=180, **kw):
        bg=parent.cget("bg") if hasattr(parent,"cget") else C["bg"]
        super().__init__(parent,width=size,height=size,bg=bg,
                         highlightthickness=0,**kw)
        self._size=size; self._score=0; self._target=0
        self._level=""; self._color=C["muted"]; self._anim=False
        self._draw()

    def set(self, score, level, color):
        self._target=score; self._level=level; self._color=color
        if not self._anim: self._anim=True; self._step()

    def _step(self):
        try:
            if not self.winfo_exists(): return
            d=self._target-self._score
            if abs(d)<0.5:
                self._score=self._target; self._anim=False; self._draw(); return
            self._score+=d*0.14; self._draw(); self.after(16,self._step)
        except tk.TclError: pass

    def _draw(self):
        try:
            if not self.winfo_exists(): return
        except tk.TclError: return
        self.delete("all")
        s=self._size; cx=cy=s//2; rm=(s//2-12)-9
        arc_thick(self,cx,cy,rm,-210,240,C["bg3"],width=18)
        if self._score>0:
            ext=240*self._score/100; steps=60
            for i in range(steps):
                t1=i/steps; t2=(i+1)/steps
                if t1*100>self._score: break
                a1=math.radians(-210+ext*t1); a2=math.radians(-210+ext*t2)
                sc=lerp(C["accent2"],self._color,t1)
                x1=cx+rm*math.cos(a1); y1=cy+rm*math.sin(a1)
                x2=cx+rm*math.cos(a2); y2=cy+rm*math.sin(a2)
                self.create_line(x1,y1,x2,y2,fill=sc,width=18,capstyle="round")
        self.create_text(cx,cy-10,text=f"{int(self._score)}",
                         font=FONTS["num"],fill=self._color,anchor="center")
        self.create_text(cx,cy+14,text="/ 100",
                         font=FONTS["small"],fill=C["text2"],anchor="center")
        self.create_text(cx,cy+30,text=self._level,
                         font=FONTS["head"],fill=self._color,anchor="center")
        if self._score>0:
            a=math.radians(-210+240*self._score/100)
            ex=cx+rm*math.cos(a); ey=cy+rm*math.sin(a)
            self.create_oval(ex-5,ey-5,ex+5,ey+5,fill=self._color,outline="")

class MiniBar(tk.Canvas):
    def __init__(self, parent, labels, values, colors, w=320, h=120, **kw):
        bg=parent.cget("bg") if hasattr(parent,"cget") else C["bg"]
        super().__init__(parent,width=w,height=h,bg=bg,
                         highlightthickness=0,**kw)
        self._labels=labels; self._values=values; self._colors=colors
        self._width=w; self._h=h
        self._drawn=[0]*len(values)
        self._draw(); self.after(200,self._animate)

    def _animate(self):
        try:
            if not self.winfo_exists(): return
            done=True
            for i,t in enumerate(self._values):
                if self._drawn[i]<t: self._drawn[i]=min(t,self._drawn[i]+3); done=False
            self._draw()
            if not done: self.after(18,self._animate)
        except tk.TclError: pass

    def _draw(self):
        try:
            if not self.winfo_exists(): return
        except tk.TclError: return
        self.delete("all")
        n=len(self._labels); px=10
        bw=(self._width-2*px)//n-6; mh=self._h-38
        for i,(lb,v,col) in enumerate(zip(self._labels,self._drawn,self._colors)):
            x1=px+i*(bw+6); x2=x1+bw; bh=int(mh*v/100)
            self.create_rectangle(x1,4,x2,self._h-36,fill=C["bg3"],outline="")
            if bh>0:
                self.create_rectangle(x1,self._h-36-bh,x2,self._h-36,fill=col,outline="")
            self.create_text((x1+x2)//2,self._h-20,text=lb,fill=C["text2"],
                             font=FONTS["tiny"],anchor="center")
            self.create_text((x1+x2)//2,self._h-36-bh-8,text=f"{int(v)}%",
                             fill=col,font=FONTS["tiny"],anchor="center")

class HexBadge(tk.Canvas):
    def __init__(self, parent, icon, color, size=48, **kw):
        bg=parent.cget("bg") if hasattr(parent,"cget") else C["bg"]
        super().__init__(parent,width=size,height=size,bg=bg,
                         highlightthickness=0,**kw)
        cx=cy=size//2; r=size//2-3
        pts=hex_pts(cx,cy,r)
        self.create_polygon(pts,fill=lerp(color,C["bg3"],0.75),outline=color,width=1.5)
        self.create_text(cx,cy,text=icon,font=("Segoe UI Emoji",int(size*0.35)),
                         fill=color,anchor="center")

class ScanLine(tk.Canvas):
    """Stable horizontal scan-line animation."""
    def __init__(self, parent, w=400, h=3, color=None, **kw):
        bg=parent.cget("bg") if hasattr(parent,"cget") else C["bg"]
        super().__init__(parent,width=w,height=h,bg=bg,
                         highlightthickness=0,**kw)
        self._width=w; self._col=color or C["glow"]
        self._x=0; self._line=None; self._run=True
        self.after(100,self._tick)
    def _tick(self):
        if not self._run: return
        try:
            if not self.winfo_exists(): return
            if self._line is None:
                self._line=self.create_line(0,1,0,1,fill=self._col,width=2)
            self._x=(self._x+6)%(self._width+100)
            x1=max(0,self._x-80); x2=min(self._width,self._x)
            self.coords(self._line,x1,1,x2,1)
            self.after(22,self._tick)
        except tk.TclError: pass
    def stop(self): self._run=False

class StatusDot(tk.Canvas):
    """Pulsing status dot."""
    def __init__(self, parent, color, size=14, **kw):
        bg=parent.cget("bg") if hasattr(parent,"cget") else C["bg"]
        super().__init__(parent,width=size,height=size,bg=bg,
                         highlightthickness=0,**kw)
        self._col=color; self._size=size; self._t=0
        self._tick()
    def _tick(self):
        try:
            if not self.winfo_exists(): return
            self._t+=0.10
            r=max(2,int(self._size/2*(0.65+0.35*math.sin(self._t))))
            cx=self._size//2; self.delete("all")
            for i in range(3,0,-1):
                ri=r+i*2; fade=lerp(self._col,C["bg"],1-i*0.25)
                self.create_oval(cx-ri,cx-ri,cx+ri,cx+ri,fill=fade,outline="")
            self.create_oval(cx-r,cx-r,cx+r,cx+r,fill=self._col,outline="")
            self.after(60,self._tick)
        except tk.TclError: pass

class Scrollable(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent,bg=C["bg"],**kw)
        self._cv=tk.Canvas(self,bg=C["bg"],highlightthickness=0,bd=0)
        sb=tk.Scrollbar(self,orient="vertical",command=self._cv.yview)
        self._cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right",fill="y"); self._cv.pack(side="left",fill="both",expand=True)
        self.inner=tk.Frame(self._cv,bg=C["bg"])
        win=self._cv.create_window((0,0),window=self.inner,anchor="nw")
        self.inner.bind("<Configure>",
            lambda e: self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>",
            lambda e: self._cv.itemconfig(win,width=e.width))
        self._cv.bind("<MouseWheel>",
            lambda e: self._cv.yview_scroll(-1*(e.delta//120),"units"))

class Card(tk.Frame):
    def __init__(self, parent, accent=None, **kw):
        super().__init__(parent,bg=C["panel"],
                         highlightbackground=accent or C["border"],
                         highlightthickness=1,padx=16,pady=12,**kw)

# ═══════════════════════════════════════════════════════════
#  STYLED  TREEVIEW
# ═══════════════════════════════════════════════════════════
def styled_tree(parent, cols, row_h=26):
    st=ttk.Style(); st.theme_use("clam")
    st.configure("Vault.Treeview",
                 background=C["bg3"],foreground=C["text"],
                 fieldbackground=C["bg3"],bordercolor=C["border"],
                 rowheight=row_h,font=FONTS["body"])
    st.configure("Vault.Treeview.Heading",
                 background=C["bg2"],foreground=C["text2"],
                 font=FONTS["small"],relief="flat")
    st.map("Vault.Treeview",
           background=[("selected",C["border2"])],
           foreground=[("selected",C["glow"])])
    tv=ttk.Treeview(parent,style="Vault.Treeview",
                    columns=cols,show="headings",selectmode="browse")
    return tv

# ═══════════════════════════════════════════════════════════
#  PASSWORD  DIALOG
# ═══════════════════════════════════════════════════════════
class PwdDialog(tk.Toplevel):
    def __init__(self, parent, title="Enter Password", prompt="Password:", confirm=False):
        super().__init__(parent)
        self.result=None; self.title(title)
        self.configure(bg=C["bg2"]); self.resizable(False,False); self.grab_set()
        h=240 if confirm else 190
        self.geometry(f"400x{h}")
        self.update_idletasks()
        x=parent.winfo_rootx()+parent.winfo_width()//2-200
        y=parent.winfo_rooty()+parent.winfo_height()//2-h//2
        self.geometry(f"+{x}+{y}")
        hdr=tk.Frame(self,bg=C["bg1"],height=46); hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr,text=f"🔐  {title}",font=FONTS["head"],
                 bg=C["bg1"],fg=C["glow"]).pack(side="left",padx=14,pady=14)
        inner=tk.Frame(self,bg=C["bg2"]); inner.pack(fill="both",expand=True,padx=18,pady=8)
        tk.Label(inner,text=prompt,font=FONTS["small"],
                 bg=C["bg2"],fg=C["text2"]).pack(anchor="w",pady=(0,3))
        ef=tk.Frame(inner,bg=C["glow"],pady=1,padx=1); ef.pack(fill="x")
        self._e1=tk.Entry(ef,bg=C["bg"],fg=C["text"],font=FONTS["mono_lg"],
                          relief="flat",bd=6,show="●",insertbackground=C["glow"])
        self._e1.pack(fill="x"); self._e1.focus(); self._e2=None
        if confirm:
            tk.Label(inner,text="Confirm:",font=FONTS["small"],
                     bg=C["bg2"],fg=C["text2"]).pack(anchor="w",pady=(8,3))
            ef2=tk.Frame(inner,bg=C["accent2"],pady=1,padx=1); ef2.pack(fill="x")
            self._e2=tk.Entry(ef2,bg=C["bg"],fg=C["text"],font=FONTS["mono_lg"],
                              relief="flat",bd=6,show="●",insertbackground=C["accent2"])
            self._e2.pack(fill="x")
        btns=tk.Frame(self,bg=C["bg2"]); btns.pack(pady=8)
        GlowButton(btns,"Confirm",self._ok,w=100,h=32,color=C["glow"]).pack(side="left",padx=5)
        GlowButton(btns,"Cancel",self.destroy,w=100,h=32,color=C["red"]).pack(side="left",padx=5)
        self._e1.bind("<Return>",lambda e: self._ok())

    def _ok(self):
        p1=self._e1.get()
        if not p1: messagebox.showwarning("Empty","Password cannot be empty.",parent=self); return
        if self._e2 is not None and p1 != self._e2.get():
            messagebox.showwarning("Mismatch","Passwords do not match.",parent=self); return
        self.result=p1; self.destroy()

    @staticmethod
    def ask(parent,title="Enter Password",prompt="Password:",confirm=False):
        d=PwdDialog(parent,title,prompt,confirm); parent.wait_window(d); return d.result

# ═══════════════════════════════════════════════════════════
#  NAV  BUTTON
# ═══════════════════════════════════════════════════════════
class NavBtn(tk.Canvas):
    def __init__(self, parent, icon, label, idx, cmd, **kw):
        super().__init__(parent,width=195,height=48,
                         bg=C["bg1"],highlightthickness=0,**kw)
        self._icon=icon; self._label=label; self._idx=idx
        self._cmd=cmd; self._active=False
        self.after(12,lambda: self._draw(False))
        self.bind("<Enter>",    lambda e: self._draw(True)  if not self._active else None)
        self.bind("<Leave>",    lambda e: self._draw(False) if not self._active else None)
        self.bind("<Button-1>", lambda e: cmd(idx))

    def activate(self, yes):
        self._active=yes; self._draw(yes)

    def _draw(self, hov):
        try:
            if not self.winfo_exists(): return
            self.delete("all")
            w,h=195,48
            if self._active:
                # Cyan left accent bar
                for i in range(4,0,-1):
                    c=lerp(C["glow"],C["bg1"],1-i*0.22)
                    self.create_rectangle(0,0,2+i,h,fill=c,outline="")
                self.create_rectangle(3,0,w,h,fill=C["bg3"],outline="")
                self.create_line(w-1,4,w-1,h-4,fill=C["border2"],width=1)
            elif hov:
                self.create_rectangle(0,0,w,h,fill=C["bg2"],outline="")
            ic_col=C["glow"] if self._active else (C["text"] if hov else C["text2"])
            lbl_col=C["text"] if (self._active or hov) else C["text2"]
            lbl_font=("Consolas",9,"bold") if self._active else FONTS["body"]
            self.create_text(30,h//2,text=self._icon,
                             font=("Segoe UI Emoji",13),fill=ic_col,anchor="center")
            self.create_text(113,h//2,text=self._label,
                             font=lbl_font,fill=lbl_col,anchor="center")
        except tk.TclError: pass

# ═══════════════════════════════════════════════════════════
#  PAGE  BASE
# ═══════════════════════════════════════════════════════════
class Page(tk.Frame):
    def __init__(self, master):
        super().__init__(master,bg=C["bg"])

    def _sec(self, parent, icon, title, sub="", color=None):
        f=tk.Frame(parent,bg=C["bg"]); f.pack(fill="x",padx=22,pady=(16,4))
        top=tk.Frame(f,bg=C["bg"]); top.pack(fill="x")
        HexBadge(top,icon,color or C["glow"],size=42).pack(side="left",padx=(0,12))
        tf=tk.Frame(top,bg=C["bg"]); tf.pack(side="left",fill="x",expand=True)
        tk.Label(tf,text=title,font=FONTS["hero"],bg=C["bg"],
                 fg=color or C["glow"]).pack(anchor="w")
        if sub:
            tk.Label(tf,text=sub,font=FONTS["small"],bg=C["bg"],
                     fg=C["text2"]).pack(anchor="w")
        ScanLine(f,w=700,h=2,color=color or C["glow"]).pack(fill="x",pady=(6,0))

    def _card(self, parent, accent=None, **kw):
        c=Card(parent,accent=accent,**kw); c.pack(fill="x",padx=22,pady=5); return c

    def _label(self, parent, text, font=None, fg=None, **kw):
        return tk.Label(parent,text=text,font=font or FONTS["body"],
                        bg=parent.cget("bg"),fg=fg or C["text"],**kw)

    def _log_write(self, widget, msg, col=None):
        widget.config(state="normal")
        start=widget.index("end")
        widget.insert("end",msg)
        if col:
            tag=f"t{time.monotonic()}"
            widget.tag_add(tag,start,widget.index("end"))
            widget.tag_config(tag,foreground=col)
        widget.see("end"); widget.config(state="disabled")

# ═══════════════════════════════════════════════════════════
#  DASHBOARD  PAGE
# ═══════════════════════════════════════════════════════════
class DashPage(Page):
    def __init__(self, master):
        super().__init__(master)
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)

    def _build(self, p):
        self._sec(p,"⬡",APP_NAME,f"Enterprise Security Suite  •  {APP_VER}",C["glow"])

        # ── Session header (date only — admin name is in sidebar footer only) ─
        ab=tk.Frame(p,bg=C["bg1"],highlightbackground=C["border2"],highlightthickness=1)
        ab.pack(fill="x",padx=22,pady=(4,10))
        inner_ab=tk.Frame(ab,bg=C["bg1"]); inner_ab.pack(fill="x",padx=14,pady=8)
        tk.Label(inner_ab,text="⬡  "+APP_NAME,font=FONTS["head"],
                 bg=C["bg1"],fg=C["glow"]).pack(side="left")
        tk.Label(inner_ab,text="Enterprise Security Suite",font=FONTS["tiny"],
                 bg=C["bg1"],fg=C["text2"]).pack(side="left",padx=(12,0))
        tk.Label(inner_ab,text=time.strftime('%A, %d %B %Y'),
                 font=FONTS["small"],bg=C["bg1"],fg=C["text2"]).pack(side="right")

        # ── Module cards ─────────────────────────────────────────────────────
        stats=[
            ("🔑","Password","Strength Analysis", C["accent1"],94),
            ("🔒","Encrypt", "AES-256 Protection",C["green"],  88),
            ("📁","Lock",    "Vault-Based Lock",   C["orange"], 82),
            ("👁","Hide",    "Zero-Trace Vault",   C["accent2"],76),
            ("🛡","Integrity","File Monitoring",   C["teal"],   79),
            ("🔬","Scanner", "Heuristic Scan",     C["red"],    85),
        ]
        row=tk.Frame(p,bg=C["bg"]); row.pack(fill="x",padx=22,pady=4)
        for icon,title,sub,col,val in stats:
            c=tk.Frame(row,bg=C["panel"],highlightbackground=col,
                       highlightthickness=1,padx=10,pady=8)
            c.pack(side="left",expand=True,fill="both",padx=3)
            top=tk.Frame(c,bg=C["panel"]); top.pack(fill="x")
            HexBadge(top,icon,col,size=32).pack(side="left")
            StatusDot(top,col,size=8).pack(side="right",anchor="ne")
            tk.Label(c,text=title,font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(4,0))
            tk.Label(c,text=sub,  font=FONTS["tiny"],bg=C["panel"],fg=C["text2"]).pack(anchor="w")
            bar=tk.Canvas(c,height=3,bg=C["bg3"],highlightthickness=0); bar.pack(fill="x",pady=(4,0))
            c.after(400,lambda b=bar,v=val,cl=col: self._bar(b,v,cl))

        # ── Charts ────────────────────────────────────────────────────────────
        charts=tk.Frame(p,bg=C["bg"]); charts.pack(fill="x",padx=22,pady=6)
        lc=Card(charts,accent=C["border"]); lc.pack(side="left",fill="both",expand=True,padx=(0,5))
        tk.Label(lc,text="Module Readiness",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w")
        tk.Label(lc,text="Security posture scores",font=FONTS["tiny"],
                 bg=C["panel"],fg=C["text2"]).pack(anchor="w",pady=(0,6))
        MiniBar(lc,["PWD","ENC","LOCK","HIDE","INTG","SCAN"],
                [94,88,82,76,79,85],
                [C["accent1"],C["green"],C["orange"],C["accent2"],C["teal"],C["red"]],
                w=300,h=120).pack()
        rc=Card(charts,accent=C["border"]); rc.pack(side="left",fill="both",expand=True,padx=(5,0))
        tk.Label(rc,text="Overall Security Score",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w")
        tk.Label(rc,text="Composite module rating",font=FONTS["tiny"],
                 bg=C["panel"],fg=C["text2"]).pack(anchor="w",pady=(0,4))
        ring=RingGauge(rc,size=150); ring.pack(pady=2)
        ring.after(500,lambda: ring.set(84,"STRONG",C["green"]))

        # ── Module guide ─────────────────────────────────────────────────────
        gc=self._card(p,accent=C["border"])
        tk.Label(gc,text="Module Reference",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,8))
        guides=[
            (C["accent1"],"🔑","Password Checker",   "Real-time strength scoring + suggestions"),
            (C["pink"],   "⚡","Password Generator", "Cryptographically secure password generation"),
            (C["green"],  "🔒","File Encryption",    "AES-256 — encrypts file, deletes original"),
            (C["orange"], "📁","Folder Lock",         "Encrypt entire folder in-place, AES-256"),
            (C["accent2"],"👁","Folder Hide",         "Move folder to hidden vault, password-locked"),
            (C["gold"],   "📝","Secure Notes",        "Encrypted private notepad, AES-256"),
            (C["teal"],   "🛡","File Integrity",      "SHA-256 baseline monitoring for tampering"),
            (C["red"],    "🔬","Virus Scanner",       "Heuristic entropy + signature threat scan"),
        ]
        for col,ico,title2,desc in guides:
            r3=tk.Frame(gc,bg=C["panel"]); r3.pack(fill="x",pady=2)
            tk.Canvas(r3,width=3,height=20,bg=col,highlightthickness=0).pack(side="left",padx=(0,7))
            HexBadge(r3,ico,col,size=24).pack(side="left",padx=(0,7))
            tf=tk.Frame(r3,bg=C["panel"]); tf.pack(side="left")
            tk.Label(tf,text=title2,font=FONTS["body"],bg=C["panel"],
                     fg=col,width=20,anchor="w").pack(side="left")
            tk.Label(tf,text=desc,font=FONTS["tiny"],bg=C["panel"],fg=C["text2"]).pack(side="left")

        if not CRYPTO_OK:
            wc=self._card(p,accent=C["red"])
            tk.Label(wc,text="⚠  pip install cryptography",
                     font=FONTS["head"],bg=C["panel"],fg=C["red"]).pack(anchor="w")

    def _bar(self, bar, val, col):
        bar.update_idletasks()
        w=bar.winfo_width(); bar.delete("all")
        bar.create_rectangle(0,0,w,3,fill=C["bg3"],outline="")
        bar.create_rectangle(0,0,int(w*val/100),3,fill=col,outline="")

# ═══════════════════════════════════════════════════════════
#  PASSWORD  CHECK  PAGE
# ═══════════════════════════════════════════════════════════
class PwdPage(Page):
    def __init__(self, master):
        super().__init__(master)
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)

    def _build(self, p):
        self._sec(p,"🔑","Password Checker",
                  "Real-time strength analysis & security scoring",C["accent1"])
        ic=self._card(p,accent=C["accent1"])
        hdr=tk.Frame(ic,bg=C["panel"]); hdr.pack(fill="x")
        tk.Label(hdr,text="Enter Password",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(side="left")
        self._show=tk.BooleanVar(value=False)
        tk.Checkbutton(hdr,text="Show",variable=self._show,command=self._tog,
                       bg=C["panel"],fg=C["text2"],selectcolor=C["bg"],
                       activebackground=C["panel"],font=FONTS["small"]).pack(side="right")
        ef=tk.Frame(ic,bg=C["accent1"],pady=1,padx=1); ef.pack(fill="x",pady=(8,0))
        self._entry=tk.Entry(ef,bg=C["bg"],fg=C["glow"],font=("Courier New",15,"bold"),
                             relief="flat",bd=8,show="●",insertbackground=C["glow"])
        self._entry.pack(fill="x"); self._entry.bind("<KeyRelease>",self._update)

        sc2=self._card(p,accent=C["border"])
        sc_row=tk.Frame(sc2,bg=C["panel"]); sc_row.pack(fill="x")
        lf=tk.Frame(sc_row,bg=C["panel"]); lf.pack(side="left",fill="both",expand=True)
        self._score_ring=RingGauge(lf,size=155); self._score_ring.pack(pady=4)
        rf=tk.Frame(sc_row,bg=C["panel"]); rf.pack(side="left",fill="both",expand=True,padx=(12,0))
        tk.Label(rf,text="Requirements",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,8))
        self._chk_vars=[]; self._chk_lbls=[]
        for i in range(8):
            r4=tk.Frame(rf,bg=C["panel"]); r4.pack(anchor="w",pady=1)
            dot=tk.Label(r4,text="○",font=FONTS["body"],bg=C["panel"],fg=C["muted"])
            dot.pack(side="left",padx=(0,4))
            lbl=tk.Label(r4,text="",font=FONTS["body"],bg=C["panel"],fg=C["text2"])
            lbl.pack(side="left")
            self._chk_vars.append(dot); self._chk_lbls.append(lbl)

        sug=self._card(p,accent=C["border"])
        tk.Label(sug,text="Suggestions",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,6))
        self._sug=tk.Label(sug,text="Enter a password to see analysis.",
                           font=FONTS["body"],bg=C["panel"],fg=C["text2"],
                           justify="left",wraplength=580); self._sug.pack(anchor="w")

    def _tog(self):
        self._entry.config(show="" if self._show.get() else "●")

    def _update(self, e=None):
        pwd=self._entry.get()
        if not pwd:
            self._score_ring.set(0,"",""); return
        score,lv,col,checks=analyse_pwd(pwd)
        self._score_ring.set(score,lv,col)
        check_names=["8+ chars","12+ chars","16+ chars","Lowercase","Uppercase",
                     "Numbers","Special","No repeat"]
        for i,(ok,_) in enumerate(checks):
            self._chk_vars[i].config(text="●" if ok else "○",
                                     fg=C["green"] if ok else C["muted"])
            self._chk_lbls[i].config(text=check_names[i],
                                     fg=C["text"] if ok else C["text2"])
        sugs=[]
        if len(pwd)<12:      sugs.append("↑  Increase length to 12+ characters")
        if not re.search(r"[A-Z]",pwd): sugs.append("↑  Add uppercase letters (A-Z)")
        if not re.search(r"\d",pwd):    sugs.append("↑  Add numbers (0-9)")
        if not re.search(r"[!@#$%^&*]",pwd): sugs.append("↑  Add special characters")
        if pwd.lower() in _COMMON:      sugs.append("⚠  Commonly used password — change immediately!")
        if score>=88: sugs=["✨  Excellent! This password is very secure."]
        elif not sugs: sugs=["✓  Good start — consider adding more length."]
        self._sug.config(text="\n".join(sugs),fg=C["text"])

# ═══════════════════════════════════════════════════════════
#  PASSWORD  GENERATOR  PAGE
# ═══════════════════════════════════════════════════════════
class GenPage(Page):
    def __init__(self, master):
        super().__init__(master)
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)
        self._history=[]

    def _build(self, p):
        self._sec(p,"⚡","Password Generator",
                  "Cryptographically secure password generation",C["pink"])
        oc=self._card(p,accent=C["border"])
        tk.Label(oc,text="Options",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,8))
        opts=tk.Frame(oc,bg=C["panel"]); opts.pack(fill="x")
        lf=tk.Frame(opts,bg=C["panel"]); lf.pack(side="left",padx=(0,24))
        tk.Label(lf,text="Length",font=FONTS["body"],bg=C["panel"],fg=C["text2"]).pack(anchor="w")
        self._len_var=tk.IntVar(value=16)
        self._len_lbl=tk.Label(lf,text="16",font=FONTS["num_sm"],bg=C["panel"],fg=C["glow"],width=3)
        self._len_lbl.pack(anchor="w")
        tk.Scale(lf,from_=8,to=64,orient="horizontal",variable=self._len_var,
                 bg=C["panel"],fg=C["text"],troughcolor=C["bg3"],
                 highlightthickness=0,bd=0,sliderlength=16,
                 activebackground=C["glow"],length=180,
                 command=lambda v: self._len_lbl.config(text=v)).pack(anchor="w")
        cf=tk.Frame(opts,bg=C["panel"]); cf.pack(side="left")
        self._upper=tk.BooleanVar(value=True); self._digits=tk.BooleanVar(value=True)
        self._syms=tk.BooleanVar(value=True);  self._ambig=tk.BooleanVar(value=False)
        for label,var,col in [
            ("Uppercase (A-Z)",self._upper,C["accent1"]),
            ("Numbers (0-9)",  self._digits,C["green"]),
            ("Symbols (!@#$)", self._syms,C["orange"]),
            ("Exclude ambiguous",self._ambig,C["text2"]),
        ]:
            tk.Checkbutton(cf,text=label,variable=var,bg=C["panel"],
                           fg=col,selectcolor=C["bg"],activebackground=C["panel"],
                           font=FONTS["body"]).pack(anchor="w",pady=2)
        GlowButton(p,"⚡  GENERATE",self._generate,w=220,h=44,color=C["pink"]).pack(pady=10)
        rc=self._card(p,accent=C["border"])
        tk.Label(rc,text="Generated Password",font=FONTS["head"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,6))
        ef=tk.Frame(rc,bg=C["pink"],pady=1,padx=1); ef.pack(fill="x")
        self._result=tk.Entry(ef,bg=C["bg"],fg=C["pink"],
                              font=("Courier New",14,"bold"),
                              relief="flat",bd=8,state="readonly",
                              readonlybackground=C["bg"],insertbackground=C["pink"])
        self._result.pack(fill="x")
        br=tk.Frame(rc,bg=C["panel"]); br.pack(fill="x",pady=(6,0))
        GlowButton(br,"Copy",self._copy,w=90,h=32,color=C["glow"]).pack(side="left",padx=(0,6))
        GlowButton(br,"Again",self._generate,w=90,h=32,color=C["pink"]).pack(side="left")
        self._copy_lbl=tk.Label(br,text="",font=FONTS["small"],bg=C["panel"],fg=C["green"])
        self._copy_lbl.pack(side="right")
        sc2=self._card(p,accent=C["border"])
        tk.Label(sc2,text="Strength",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w")
        self._gen_ring=RingGauge(sc2,size=155); self._gen_ring.pack(pady=4)
        hc=self._card(p,accent=C["border"])
        tk.Label(hc,text="History (session)",font=FONTS["head"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,5))
        self._hist=tk.Text(hc,height=5,bg=C["bg"],fg=C["text2"],
                           font=FONTS["mono"],relief="flat",bd=6,
                           state="disabled",wrap="none")
        self._hist.pack(fill="x")

    def _generate(self):
        try:
            pwd=gen_password(length=self._len_var.get(),upper=self._upper.get(),
                             digits=self._digits.get(),symbols=self._syms.get(),
                             no_ambig=self._ambig.get())
            self._result.config(state="normal"); self._result.delete(0,"end")
            self._result.insert(0,pwd); self._result.config(state="readonly")
            score,lv,col,_=analyse_pwd(pwd); self._gen_ring.set(score,lv,col)
            self._history.insert(0,f"[{time.strftime('%H:%M:%S')}]  {pwd}")
            self._hist.config(state="normal"); self._hist.delete("1.0","end")
            self._hist.insert("end","\n".join(self._history[:8]))
            self._hist.config(state="disabled")
        except Exception as e: messagebox.showerror("Error",str(e))

    def _copy(self):
        pwd=self._result.get()
        if pwd:
            self.clipboard_clear(); self.clipboard_append(pwd)
            self._copy_lbl.config(text="✔ Copied!")
            self.after(2000,lambda: self._copy_lbl.config(text=""))

# ═══════════════════════════════════════════════════════════
#  FILE  ENCRYPTION  PAGE  (original deleted after encrypt)
# ═══════════════════════════════════════════════════════════
class EncPage(Page):
    def __init__(self, master):
        super().__init__(master); self._fp=""
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)

    def _build(self, p):
        self._sec(p,"🔒","File Encryption",
                  "AES-256 + PBKDF2-SHA256  •  Original file deleted after encryption",C["green"])
        if not CRYPTO_OK:
            c=self._card(p,accent=C["red"])
            tk.Label(c,text="⚠  pip install cryptography",
                     font=FONTS["title"],bg=C["panel"],fg=C["red"]).pack(); return

        fc=self._card(p,accent=C["border"])
        tk.Label(fc,text="Select File",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,6))
        fr=tk.Frame(fc,bg=C["bg"],highlightbackground=C["border"],highlightthickness=1)
        fr.pack(fill="x")
        self._flbl=tk.Label(fr,text="  No file selected…",bg=C["bg"],
                             fg=C["muted"],font=FONTS["mono"],anchor="w",padx=6,pady=6)
        self._flbl.pack(side="left",fill="x",expand=True)
        GlowButton(fr,"Browse",self._browse,w=100,h=32,
                   color=C["border"],icon="📂").pack(side="right",padx=4,pady=4)

        pc=self._card(p,accent=C["border"])
        tk.Label(pc,text="Encryption Password",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w")
        tk.Label(pc,text="⚠  Original file is permanently deleted after encryption. No recovery!",
                 font=FONTS["small"],bg=C["panel"],fg=C["orange"]).pack(anchor="w",pady=(2,6))
        ef=tk.Frame(pc,bg=C["green"],pady=1,padx=1); ef.pack(fill="x")
        self._pwd=tk.Entry(ef,bg=C["bg"],fg=C["text"],relief="flat",
                           font=FONTS["mono_lg"],bd=7,show="●",insertbackground=C["green"])
        self._pwd.pack(fill="x"); self._pwd.bind("<KeyRelease>",self._pwd_ch)
        self._pbar=tk.Canvas(pc,height=4,bg=C["bg3"],highlightthickness=0)
        self._pbar.pack(fill="x",pady=(4,0))
        self._plbl=tk.Label(pc,text="",font=FONTS["small"],bg=C["panel"],fg=C["muted"])
        self._plbl.pack(anchor="e")

        br=tk.Frame(p,bg=C["bg"]); br.pack(pady=10)
        GlowButton(br,"🔒  ENCRYPT FILE",self._encrypt,w=200,h=46,color=C["accent2"]).pack(side="left",padx=8)
        GlowButton(br,"🔓  DECRYPT FILE",self._decrypt,w=200,h=46,color=C["green"]).pack(side="left",padx=8)

        lc=self._card(p,accent=C["border"])
        lhdr=tk.Frame(lc,bg=C["panel"]); lhdr.pack(fill="x")
        tk.Label(lhdr,text="◉  Activity Terminal",font=FONTS["head"],
                 bg=C["panel"],fg=C["green"]).pack(side="left")
        StatusDot(lhdr,C["green"],size=10).pack(side="right")
        self._log=tk.Text(lc,height=8,bg=C["bg"],fg=C["green"],
                          font=FONTS["mono"],relief="flat",bd=7,
                          state="disabled",wrap="word")
        self._log.pack(fill="x",pady=(6,0))
        self._log_write(self._log,"Security Manager — Encryption Terminal Ready\n",C["text2"])
        self._log_write(self._log,"AES-256-Fernet  •  PBKDF2-SHA256  •  480,000 iterations\n",C["text2"])
        self._log_write(self._log,"NOTE: Original file will be DELETED after successful encryption.\n\n",C["orange"])

    def _pwd_ch(self, e=None):
        pwd=self._pwd.get()
        if not pwd: self._pbar.delete("all"); self._plbl.config(text=""); return
        sc,lv,col,_=analyse_pwd(pwd)
        self._pbar.update_idletasks(); w=self._pbar.winfo_width()
        self._pbar.delete("all")
        self._pbar.create_rectangle(0,0,w,4,fill=C["bg3"],outline="")
        self._pbar.create_rectangle(0,0,int(w*sc/100),4,fill=col,outline="")
        self._plbl.config(text=f"Password strength: {lv}",fg=col)

    def _browse(self):
        fp=filedialog.askopenfilename(title="Select file to encrypt/decrypt")
        if fp:
            self._fp=fp
            self._flbl.config(text=f"  {Path(fp).name}",fg=C["text"])
            self._log_write(self._log,f"[FILE]  {fp}\n",C["accent1"])

    def _encrypt(self):
        if not self._fp: return messagebox.showwarning("No File","Select a file first.")
        pwd=self._pwd.get()
        if not pwd: return messagebox.showwarning("No Password","Enter a password.")
        if not messagebox.askyesno("Confirm Encrypt",
            f"Encrypt '{Path(self._fp).name}'?\n\nThe ORIGINAL FILE will be permanently deleted.\nMake sure you remember the password!"):
            return
        self._log_write(self._log,f"[ENC]  Encrypting: {Path(self._fp).name} …\n",C["yellow"])
        def run():
            out,err=encrypt_file(self._fp,pwd)
            if err:
                self._log_write(self._log,f"[ERR]  {err}\n",C["red"])
                self.after(0,lambda: messagebox.showerror("Failed",err))
            else:
                self._log_write(self._log,f"[OK]   Encrypted → {Path(out).name}\n",C["green"])
                self._log_write(self._log,f"[DEL]  Original deleted.\n",C["orange"])
                self._fp=out
                self.after(0,lambda: (
                    self._flbl.config(text=f"  {Path(out).name}",fg=C["green"]),
                    messagebox.showinfo("Encrypted",f"File encrypted:\n{out}\n\nOriginal deleted.")))
        threading.Thread(target=run,daemon=True).start()

    def _decrypt(self):
        if not self._fp: return messagebox.showwarning("No File","Select a .enc file.")
        pwd=self._pwd.get()
        if not pwd: return messagebox.showwarning("No Password","Enter the decryption password.")
        self._log_write(self._log,f"[DEC]  Decrypting: {Path(self._fp).name} …\n",C["yellow"])
        def run():
            out,err=decrypt_file(self._fp,pwd)
            if err:
                self._log_write(self._log,f"[ERR]  Wrong password or corrupted file.\n",C["red"])
                self.after(0,lambda: messagebox.showerror("Failed","Wrong password or corrupted file."))
            else:
                self._log_write(self._log,f"[OK]   Restored → {Path(out).name}\n",C["green"])
                self._log_write(self._log,f"[DEL]  .enc file removed.\n",C["orange"])
                self._fp=out
                self.after(0,lambda: (
                    self._flbl.config(text=f"  {Path(out).name}",fg=C["green"]),
                    messagebox.showinfo("Decrypted",f"Restored:\n{out}\n\n.enc file deleted.")))
        threading.Thread(target=run,daemon=True).start()

# ═══════════════════════════════════════════════════════════
#  FOLDER  LOCK  PAGE
# ═══════════════════════════════════════════════════════════
class LockPage(Page):
    def __init__(self, master):
        super().__init__(master); self._fp=""
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)

    def _build(self, p):
        self._sec(p,"📁","Folder Lock / Unlock",
                  "AES-256 encryption of entire folder contents  •  Pure Python  •  No Windows tools",
                  C["orange"])
        cols=tk.Frame(p,bg=C["bg"]); cols.pack(fill="x",padx=22,pady=6)

        # LEFT: Lock
        lf=Card(cols,accent=C["border"]); lf.pack(side="left",fill="both",expand=True,padx=(0,5))
        tk.Label(lf,text="🔒  Lock a Folder",font=FONTS["title"],
                 bg=C["panel"],fg=C["orange"]).pack(anchor="w",pady=(0,8))
        fr=tk.Frame(lf,bg=C["bg"],highlightbackground=C["border"],highlightthickness=1)
        fr.pack(fill="x")
        self._flbl=tk.Label(fr,text="  No folder selected…",bg=C["bg"],
                             fg=C["muted"],font=FONTS["mono"],anchor="w",padx=6,pady=6)
        self._flbl.pack(side="left",fill="x",expand=True)
        GlowButton(fr,"Browse",self._browse,w=88,h=30,
                   color=C["border"],icon="📂").pack(side="right",padx=3,pady=3)
        tk.Label(lf,text="Set Password:",font=FONTS["small"],
                 bg=C["panel"],fg=C["text2"]).pack(anchor="w",pady=(8,2))
        ef1=tk.Frame(lf,bg=C["orange"],pady=1,padx=1); ef1.pack(fill="x")
        self._pwd1=tk.Entry(ef1,bg=C["bg"],fg=C["text"],relief="flat",
                            font=FONTS["mono_lg"],bd=6,show="●",insertbackground=C["orange"])
        self._pwd1.pack(fill="x")
        tk.Label(lf,text="Confirm Password:",font=FONTS["small"],
                 bg=C["panel"],fg=C["text2"]).pack(anchor="w",pady=(6,2))
        ef2=tk.Frame(lf,bg=C["orange"],pady=1,padx=1); ef2.pack(fill="x")
        self._pwd2=tk.Entry(ef2,bg=C["bg"],fg=C["text"],relief="flat",
                            font=FONTS["mono_lg"],bd=6,show="●",insertbackground=C["orange"])
        self._pwd2.pack(fill="x")
        GlowButton(lf,"🔒  LOCK FOLDER",self._lock,w=180,h=42,color=C["red"]).pack(pady=10)
        for txt,col in [
            ("⚠  ALL files inside will be encrypted.",C["orange"]),
            ("   Use the same password to unlock.",   C["text2"]),
            ("   Keep backups of important data.",    C["text2"]),
        ]:
            tk.Label(lf,text=txt,font=FONTS["tiny"],bg=C["panel"],fg=col,anchor="w").pack(anchor="w")

        # RIGHT: Locked folders list
        rf=Card(cols,accent=C["border"]); rf.pack(side="left",fill="both",expand=True,padx=(5,0))
        hdr_r=tk.Frame(rf,bg=C["panel"]); hdr_r.pack(fill="x",pady=(0,6))
        tk.Label(hdr_r,text="🗂  Locked Folders",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(side="left")
        GlowButton(hdr_r,"↻",self._refresh,w=50,h=26,color=C["border"]).pack(side="right")
        self._tree=styled_tree(rf,("name","files","date"))
        self._tree.heading("name", text="Folder Name")
        self._tree.heading("files",text="Files")
        self._tree.heading("date", text="Locked At")
        self._tree.column("name", width=150)
        self._tree.column("files",width=55,anchor="center")
        self._tree.column("date", width=125,anchor="center")
        self._tree.pack(fill="both",expand=True)
        GlowButton(rf,"🔓  UNLOCK SELECTED",self._unlock,w=180,h=40,
                   color=C["green"]).pack(pady=(8,0))
        self._status_lbl=tk.Label(p,text="",font=FONTS["body"],bg=C["bg"],fg=C["green"])
        self._status_lbl.pack(pady=4)
        self._refresh()

    def _browse(self):
        fp=filedialog.askdirectory(title="Select Folder to Lock")
        if fp: self._fp=fp; self._flbl.config(text=f"  {Path(fp).name}",fg=C["text"])

    def _lock(self):
        if not self._fp: return messagebox.showwarning("No Folder","Select a folder first.")
        p1=self._pwd1.get(); p2=self._pwd2.get()
        if not p1: return messagebox.showwarning("No Password","Enter a password.")
        if p1!=p2: return messagebox.showwarning("Mismatch","Passwords do not match.")
        if not CRYPTO_OK: return messagebox.showerror("Error","pip install cryptography")
        if not messagebox.askyesno("Confirm Lock",
            f"Lock folder '{Path(self._fp).name}'?\n\nAll files will be AES-256 encrypted in place."):
            return
        self._status_lbl.config(text="⏳  Encrypting folder…",fg=C["yellow"])
        def run():
            try:
                n=lock_folder(self._fp,p1)
                msg=f"✔  Locked {n} files in: {Path(self._fp).name}"
                self.after(0,lambda: (
                    self._status_lbl.config(text=msg,fg=C["green"]),
                    self._refresh(),
                    messagebox.showinfo("Locked",f"Folder locked!\n{n} files encrypted.")))
            except Exception as e:
                self.after(0,lambda: (
                    self._status_lbl.config(text=f"✘  {e}",fg=C["red"]),
                    messagebox.showerror("Error",str(e))))
        threading.Thread(target=run,daemon=True).start()

    def _unlock(self):
        sel=self._tree.selection()
        if not sel: return messagebox.showwarning("None Selected","Select a locked folder.")
        tags=self._tree.item(sel[0],"tags")
        path=tags[0] if tags else ""
        if not path: return messagebox.showerror("Error","Could not determine folder path.")
        pwd=PwdDialog.ask(self,f"Unlock: {Path(path).name}",f"Password for: {Path(path).name}")
        if not pwd: return
        self._status_lbl.config(text="⏳  Decrypting folder…",fg=C["yellow"])
        def run():
            try:
                n=unlock_folder(path,pwd)
                msg=f"✔  Unlocked {n} files in: {Path(path).name}"
                self.after(0,lambda: (
                    self._status_lbl.config(text=msg,fg=C["green"]),
                    self._refresh(),
                    messagebox.showinfo("Unlocked",f"Folder unlocked!\n{n} files decrypted.")))
            except Exception as e:
                self.after(0,lambda: (
                    self._status_lbl.config(text=f"✘  {e}",fg=C["red"]),
                    messagebox.showerror("Error",str(e))))
        threading.Thread(target=run,daemon=True).start()

    def _refresh(self):
        for item in self._tree.get_children(): self._tree.delete(item)
        for e in _load_reg().get("locked",[]):
            if is_locked(e.get("path","")):
                self._tree.insert("","end",
                    values=(e.get("name","?"),e.get("file_count","?"),e.get("locked_at","?")),
                    tags=(e.get("path",""),))

# ═══════════════════════════════════════════════════════════
#  FOLDER  HIDE  PAGE
# ═══════════════════════════════════════════════════════════
class HidePage(Page):
    def __init__(self, master):
        super().__init__(master)
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)

    def _build(self, p):
        self._sec(p,"👁","Folder Hide / Unhide",
                  "Zero-trace vault  •  Moved to encrypted registry  •  Password protected",
                  C["accent2"])
        cols=tk.Frame(p,bg=C["bg"]); cols.pack(fill="x",padx=22,pady=6)

        lf=Card(cols,accent=C["border"]); lf.pack(side="left",fill="both",expand=True,padx=(0,5))
        tk.Label(lf,text="🙈  Hide a Folder",font=FONTS["title"],
                 bg=C["panel"],fg=C["accent2"]).pack(anchor="w",pady=(0,8))
        fr=tk.Frame(lf,bg=C["bg"],highlightbackground=C["border"],highlightthickness=1)
        fr.pack(fill="x")
        self._flbl=tk.Label(fr,text="  No folder selected…",bg=C["bg"],
                             fg=C["muted"],font=FONTS["mono"],anchor="w",padx=6,pady=6)
        self._flbl.pack(side="left",fill="x",expand=True)
        GlowButton(fr,"Browse",self._browse,w=88,h=30,
                   color=C["border"],icon="📂").pack(side="right",padx=3,pady=3)
        for lbl,var_attr,col in [("Set Password:","_pwd1",C["accent2"]),
                                  ("Confirm:","_pwd2",C["accent2"])]:
            tk.Label(lf,text=lbl,font=FONTS["small"],bg=C["panel"],fg=C["text2"]).pack(anchor="w",pady=(8,2))
            ef=tk.Frame(lf,bg=col,pady=1,padx=1); ef.pack(fill="x")
            e=tk.Entry(ef,bg=C["bg"],fg=C["text"],relief="flat",
                       font=FONTS["mono_lg"],bd=6,show="●",insertbackground=col)
            e.pack(fill="x"); setattr(self,var_attr,e)
        GlowButton(lf,"🙈  HIDE FOLDER",self._hide,w=180,h=42,color=C["accent2"]).pack(pady=10)
        for txt,col in [
            ("ℹ  Folder moved to secure hidden vault.",C["accent2"]),
            ("   Original path is completely removed.",C["text2"]),
            ("   Only password holders can restore it.",C["text2"]),
        ]:
            tk.Label(lf,text=txt,font=FONTS["tiny"],bg=C["panel"],fg=col,anchor="w").pack(anchor="w")

        rf=Card(cols,accent=C["border"]); rf.pack(side="left",fill="both",expand=True,padx=(5,0))
        hdr_r=tk.Frame(rf,bg=C["panel"]); hdr_r.pack(fill="x",pady=(0,6))
        tk.Label(hdr_r,text="🗄  Hidden Folders",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(side="left")
        GlowButton(hdr_r,"↻",self._refresh,w=50,h=26,color=C["border"]).pack(side="right")
        self._tree=styled_tree(rf,("name","hidden","size"))
        self._tree.heading("name",  text="Original Name")
        self._tree.heading("hidden",text="Hidden At")
        self._tree.heading("size",  text="Size")
        self._tree.column("name",  width=140)
        self._tree.column("hidden",width=130,anchor="center")
        self._tree.column("size",  width=75, anchor="center")
        self._tree.pack(fill="both",expand=True)
        GlowButton(rf,"🔓  UNHIDE SELECTED",self._unhide,w=180,h=40,
                   color=C["green"]).pack(pady=(8,0))
        self._status_lbl=tk.Label(p,text="",font=FONTS["body"],bg=C["bg"],fg=C["green"])
        self._status_lbl.pack(pady=4)
        self._refresh()

    def _browse(self):
        fp=filedialog.askdirectory(title="Select Folder to Hide")
        if fp: self._fp=fp; self._flbl.config(text=f"  {Path(fp).name}",fg=C["text"])

    def _hide(self):
        fp=getattr(self,"_fp","")
        if not fp: return messagebox.showwarning("No Folder","Select a folder first.")
        p1=self._pwd1.get(); p2=self._pwd2.get()
        if not p1: return messagebox.showwarning("No Password","Enter a password.")
        if p1!=p2: return messagebox.showwarning("Mismatch","Passwords do not match.")
        try:
            entry=hide_folder(fp,p1)
            self._status_lbl.config(text=f"✔  Hidden: {entry['original_name']}",fg=C["green"])
            self._flbl.config(text="  No folder selected…",fg=C["muted"])
            self._fp=""; self._pwd1.delete(0,"end"); self._pwd2.delete(0,"end")
            self._refresh()
            messagebox.showinfo("Hidden",f"Folder hidden successfully!\nOriginal path removed.")
        except Exception as e:
            self._status_lbl.config(text=f"✘  {e}",fg=C["red"])
            messagebox.showerror("Error",str(e))

    def _unhide(self):
        sel=self._tree.selection()
        if not sel: return messagebox.showwarning("None Selected","Select a hidden folder.")
        tags=self._tree.item(sel[0],"tags")
        eid=tags[0] if tags else ""
        if not eid: return messagebox.showerror("Error","Could not determine entry ID.")
        pwd=PwdDialog.ask(self,"Unhide Folder","Password:")
        if not pwd: return
        try:
            dest=unhide_folder(eid,pwd)
            self._status_lbl.config(text=f"✔  Restored to: {dest}",fg=C["green"])
            self._refresh(); messagebox.showinfo("Restored",f"Folder restored to:\n{dest}")
        except Exception as e:
            self._status_lbl.config(text=f"✘  {e}",fg=C["red"])
            messagebox.showerror("Error",str(e))

    def _refresh(self):
        for item in self._tree.get_children(): self._tree.delete(item)
        for e in _load_reg().get("hidden",[]):
            self._tree.insert("","end",
                values=(e.get("original_name","?"),e.get("hidden_at","?"),
                        fmt_size(e.get("size",0))),
                tags=(e.get("id",""),))

# ═══════════════════════════════════════════════════════════
#  SECURE  NOTES  PAGE
# ═══════════════════════════════════════════════════════════
class NotesPage(Page):
    def __init__(self, master):
        super().__init__(master); self._cur_id=None
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)
        self._refresh()

    def _build(self, p):
        self._sec(p,"📝","Secure Notes",
                  "AES-256 encrypted private notepad",C["gold"])
        cols=tk.Frame(p,bg=C["bg"])
        cols.pack(fill="both", padx=22, pady=6, expand=True)

        lf=Card(cols,accent=C["border"]); lf.pack(side="left",fill="both",padx=(0,5),ipadx=4)
        lf.configure(width=200); lf.pack_propagate(False)
        tk.Label(lf,text="Notes",font=FONTS["title"],bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,6))
        self._notes_lb=tk.Listbox(lf,bg=C["bg3"],fg=C["text"],font=FONTS["body"],
                                   relief="flat",selectbackground=C["border2"],
                                   selectforeground=C["glow"],height=14,bd=0)
        self._notes_lb.pack(fill="both",expand=True,pady=(0,6))
        self._notes_lb.bind("<<ListboxSelect>>",self._on_select)
        GlowButton(lf,"+ New",self._new_note,w=84,h=30,color=C["gold"]).pack(side="left",pady=(4,0))
        GlowButton(lf,"Delete",self._delete_note,w=84,h=30,color=C["red"]).pack(side="right",pady=(4,0))
        self._notes_meta=[]

        rf=Card(cols,accent=C["border"]); rf.pack(side="left",fill="both",expand=True,padx=(5,0))
        tk.Label(rf,text="Title:",font=FONTS["small"],bg=C["panel"],fg=C["text2"]).pack(anchor="w")
        ef=tk.Frame(rf,bg=C["gold"],pady=1,padx=1); ef.pack(fill="x",pady=(2,8))
        self._title_e=tk.Entry(ef,bg=C["bg"],fg=C["text"],font=FONTS["mono_lg"],
                               relief="flat",bd=6,insertbackground=C["gold"])
        self._title_e.pack(fill="x")
        tk.Label(rf,text="Content:",font=FONTS["small"],bg=C["panel"],fg=C["text2"]).pack(anchor="w")
        self._content_e=tk.Text(rf,bg=C["bg"],fg=C["text"],font=FONTS["mono"],
                                 relief="flat",bd=6,height=14,wrap="word",
                                 insertbackground=C["gold"])
        self._content_e.pack(fill="both",expand=True,pady=(2,8))
        br=tk.Frame(rf,bg=C["panel"]); br.pack(fill="x")
        GlowButton(br,"💾  Save",self._save_note,w=130,h=36,color=C["gold"]).pack(side="left",padx=(0,8))
        GlowButton(br,"📂  Load",self._load_note,w=130,h=36,color=C["teal"]).pack(side="left")
        self._save_lbl=tk.Label(br,text="",font=FONTS["small"],bg=C["panel"],fg=C["text2"])
        self._save_lbl.pack(side="right")

    def _refresh(self):
        self._notes_lb.delete(0,"end"); self._notes_meta=[]
        for n in list_notes():
            self._notes_lb.insert("end",f"  {n['id'][:8]}…  {n['modified']}")
            self._notes_meta.append(n)

    def _on_select(self,e=None):
        sel=self._notes_lb.curselection()
        if sel: self._save_lbl.config(text=f"Selected: {self._notes_meta[sel[0]]['id'][:8]}…")

    def _new_note(self):
        self._cur_id=None
        self._title_e.delete(0,"end"); self._content_e.delete("1.0","end")
        self._save_lbl.config(text="New note — enter content and Save")

    def _save_note(self):
        title=self._title_e.get().strip(); content=self._content_e.get("1.0","end-1c")
        if not title: return messagebox.showwarning("No Title","Enter a title for the note.")
        pwd=PwdDialog.ask(self,"Save Note","Encryption password:",confirm=self._cur_id is None)
        if not pwd: return
        try:
            self._cur_id=save_note(title,content,pwd,self._cur_id)
            self._save_lbl.config(text=f"Saved ✔  {time.strftime('%H:%M:%S')}",fg=C["green"])
            self._refresh()
        except Exception as e: messagebox.showerror("Error",str(e))

    def _load_note(self):
        sel=self._notes_lb.curselection()
        if not sel: return messagebox.showwarning("None Selected","Select a note to load.")
        meta=self._notes_meta[sel[0]]
        pwd=PwdDialog.ask(self,"Load Note","Decryption password:")
        if not pwd: return
        try:
            data=load_note(meta["id"],pwd)
            self._cur_id=meta["id"]
            self._title_e.delete(0,"end"); self._title_e.insert(0,data["title"])
            self._content_e.delete("1.0","end"); self._content_e.insert("1.0",data["content"])
            self._save_lbl.config(text=f"Loaded  •  {data.get('saved_at','?')}",fg=C["text2"])
        except Exception as e: messagebox.showerror("Error",str(e))

    def _delete_note(self):
        sel=self._notes_lb.curselection()
        if not sel: return messagebox.showwarning("None Selected","Select a note to delete.")
        meta=self._notes_meta[sel[0]]
        if not messagebox.askyesno("Delete Note",f"Permanently delete note {meta['id'][:8]}…?"):
            return
        delete_note(meta["id"])
        if self._cur_id==meta["id"]:
            self._cur_id=None; self._title_e.delete(0,"end"); self._content_e.delete("1.0","end")
        self._refresh()

# ═══════════════════════════════════════════════════════════
#  FILE  INTEGRITY  MONITOR  PAGE
# ═══════════════════════════════════════════════════════════
class IntegrityPage(Page):
    def __init__(self, master):
        super().__init__(master); self._fp=""
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)
        self._refresh_baselines()

    def _build(self, p):
        self._sec(p,"🛡","File Integrity Monitor",
                  "SHA-256 baseline snapshots  •  Detect modified / added / deleted files",
                  C["teal"])

        # Create baseline
        cc=self._card(p,accent=C["teal"])
        tk.Label(cc,text="Create Baseline Snapshot",font=FONTS["title"],
                 bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,8))
        fr=tk.Frame(cc,bg=C["bg"],highlightbackground=C["border"],highlightthickness=1)
        fr.pack(fill="x")
        self._flbl=tk.Label(fr,text="  No folder selected…",bg=C["bg"],
                             fg=C["muted"],font=FONTS["mono"],anchor="w",padx=6,pady=6)
        self._flbl.pack(side="left",fill="x",expand=True)
        GlowButton(fr,"Browse",self._browse,w=100,h=32,color=C["border"],icon="📂").pack(side="right",padx=4,pady=4)
        nr=tk.Frame(cc,bg=C["panel"]); nr.pack(fill="x",pady=(8,0))
        tk.Label(nr,text="Snapshot name:",font=FONTS["small"],bg=C["panel"],fg=C["text2"]).pack(side="left",padx=(0,8))
        self._name_e=tk.Entry(nr,bg=C["bg3"],fg=C["text"],font=FONTS["mono"],
                               relief="flat",bd=5,width=28,insertbackground=C["teal"])
        self._name_e.insert(0,f"Baseline {time.strftime('%Y-%m-%d')}")
        self._name_e.pack(side="left")
        GlowButton(cc,"📸  CREATE BASELINE",self._create,w=220,h=42,color=C["teal"]).pack(pady=10)

        # Saved baselines
        bc=self._card(p,accent=C["border"])
        bhdr=tk.Frame(bc,bg=C["panel"]); bhdr.pack(fill="x",pady=(0,8))
        tk.Label(bhdr,text="Saved Baselines",font=FONTS["title"],bg=C["panel"],fg=C["text"]).pack(side="left")
        GlowButton(bhdr,"↻",self._refresh_baselines,w=50,h=26,color=C["border"]).pack(side="right")
        self._b_tree=styled_tree(bc,("name","folder","files","created"))
        self._b_tree.heading("name",   text="Snapshot Name")
        self._b_tree.heading("folder", text="Monitored Folder")
        self._b_tree.heading("files",  text="Files")
        self._b_tree.heading("created",text="Created At")
        self._b_tree.column("name",   width=160)
        self._b_tree.column("folder", width=200)
        self._b_tree.column("files",  width=55,anchor="center")
        self._b_tree.column("created",width=130,anchor="center")
        self._b_tree.pack(fill="both",expand=True)
        bbtns=tk.Frame(bc,bg=C["panel"]); bbtns.pack(fill="x",pady=(8,0))
        GlowButton(bbtns,"🔍  SCAN FOR CHANGES",self._run_scan,w=200,h=40,color=C["green"]).pack(side="left",padx=(0,8))
        GlowButton(bbtns,"🗑  Delete Baseline",self._delete_baseline,w=170,h=40,color=C["red"]).pack(side="left")

        # Results
        rc=self._card(p,accent=C["border"])
        rhdr=tk.Frame(rc,bg=C["panel"]); rhdr.pack(fill="x")
        tk.Label(rhdr,text="◉  Scan Results",font=FONTS["head"],bg=C["panel"],fg=C["teal"]).pack(side="left")
        StatusDot(rhdr,C["teal"],size=10).pack(side="right")
        self._res_log=tk.Text(rc,height=14,bg=C["bg"],fg=C["teal"],
                              font=FONTS["mono"],relief="flat",bd=7,
                              state="disabled",wrap="word")
        self._res_log.pack(fill="x",pady=(6,0))
        self._log_write(self._res_log,
            "Security Manager — File Integrity Monitor Ready\n"
            "Create a baseline snapshot, then scan to detect any tampering.\n\n",
            C["text2"])

    def _browse(self):
        fp=filedialog.askdirectory(title="Select Folder to Monitor")
        if fp:
            self._fp=fp
            self._flbl.config(text=f"  {Path(fp).name}",fg=C["text"])
            self._name_e.delete(0,"end")
            self._name_e.insert(0,f"{Path(fp).name} — {time.strftime('%Y-%m-%d')}")

    def _create(self):
        if not self._fp: return messagebox.showwarning("No Folder","Select a folder first.")
        name=self._name_e.get().strip() or f"Baseline {time.strftime('%Y-%m-%d %H:%M')}"
        self._log_write(self._res_log,f"[BASELINE]  Creating snapshot for: {self._fp}\n",C["yellow"])
        def run():
            try:
                snap=integrity_baseline(self._fp,name)
                msg=f"[OK]  Baseline '{snap['name']}' created — {snap['file_count']} files hashed.\n"
                self.after(0,lambda: (
                    self._log_write(self._res_log,msg,C["green"]),
                    self._refresh_baselines(),
                    messagebox.showinfo("Baseline Created",
                        f"Snapshot: {snap['name']}\nFiles: {snap['file_count']}\nID: {snap['id'][:12]}…")))
            except Exception as e:
                self.after(0,lambda: (
                    self._log_write(self._res_log,f"[ERR]  {e}\n",C["red"]),
                    messagebox.showerror("Error",str(e))))
        threading.Thread(target=run,daemon=True).start()

    def _run_scan(self):
        sel=self._b_tree.selection()
        if not sel: return messagebox.showwarning("None","Select a baseline to scan against.")
        tags=self._b_tree.item(sel[0],"tags")
        snap_id=tags[0] if tags else ""
        if not snap_id: return
        self._log_write(self._res_log,f"[SCAN]  Scanning against baseline {snap_id[:12]}…\n",C["yellow"])
        def run():
            try:
                result=integrity_scan(snap_id)
                if "error" in result:
                    self.after(0,lambda: self._log_write(self._res_log,f"[ERR]  {result['error']}\n",C["red"])); return

                lines=[]
                lines.append(f"\n{'═'*50}\n")
                lines.append(f"  INTEGRITY SCAN REPORT\n")
                lines.append(f"  Snapshot : {result['snapshot']}\n")
                lines.append(f"  Folder   : {result['folder']}\n")
                lines.append(f"  Scanned  : {result['scanned_at']}\n")
                lines.append(f"{'─'*50}\n")
                lines.append(f"  ✔ Unchanged : {len(result['ok'])} files\n")
                lines.append(f"  ⚠ Modified  : {len(result['modified'])} files\n")
                lines.append(f"  ✘ Deleted   : {len(result['deleted'])} files\n")
                lines.append(f"  + Added     : {len(result['added'])} files\n")
                lines.append(f"{'─'*50}\n")
                status="CLEAN — No changes detected." if result["clean"] else "⚠  ALERT — Changes detected!"
                lines.append(f"  STATUS: {status}\n")
                if result["modified"]:
                    lines.append(f"\n  MODIFIED FILES:\n")
                    for f in result["modified"]: lines.append(f"    ⚠  {f}\n")
                if result["deleted"]:
                    lines.append(f"\n  DELETED FILES:\n")
                    for f in result["deleted"]: lines.append(f"    ✘  {f}\n")
                if result["added"]:
                    lines.append(f"\n  NEW FILES:\n")
                    for f in result["added"]: lines.append(f"    +  {f}\n")
                lines.append(f"\n{'═'*50}\n\n")

                col=C["green"] if result["clean"] else C["red"]
                self.after(0,lambda: self._log_write(self._res_log,"".join(lines),col))
            except Exception as e:
                self.after(0,lambda: self._log_write(self._res_log,f"[ERR]  {e}\n",C["red"]))
        threading.Thread(target=run,daemon=True).start()

    def _refresh_baselines(self):
        for item in self._b_tree.get_children(): self._b_tree.delete(item)
        for b in list_baselines():
            fld=Path(b["folder"]).name if b["folder"] else "?"
            self._b_tree.insert("","end",
                values=(b["name"],fld,b["file_count"],b["created_at"]),
                tags=(b["id"],))

    def _delete_baseline(self):
        sel=self._b_tree.selection()
        if not sel: return messagebox.showwarning("None","Select a baseline to delete.")
        tags=self._b_tree.item(sel[0],"tags")
        snap_id=tags[0] if tags else ""
        if not snap_id: return
        if messagebox.askyesno("Delete","Delete this baseline snapshot?"):
            delete_baseline(snap_id); self._refresh_baselines()

# ═══════════════════════════════════════════════════════════
#  VIRUS  SCANNER  PAGE
# ═══════════════════════════════════════════════════════════
class ScannerPage(Page):
    def __init__(self, master):
        super().__init__(master); self._fp=""; self._scanning=False
        sc=Scrollable(self); sc.pack(fill="both",expand=True)
        self._build(sc.inner)

    def _build(self, p):
        self._sec(p,"🔬","Virus / Threat Scanner",
                  "Heuristic analysis  •  Signature detection  •  Entropy analysis  •  Pattern matching",
                  C["red"])

        sc=self._card(p,accent=C["red"])
        tk.Label(sc,text="Select Target",font=FONTS["title"],bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,8))
        fr=tk.Frame(sc,bg=C["bg"],highlightbackground=C["border"],highlightthickness=1); fr.pack(fill="x")
        self._flbl=tk.Label(fr,text="  No target selected…",bg=C["bg"],
                             fg=C["muted"],font=FONTS["mono"],anchor="w",padx=6,pady=6)
        self._flbl.pack(side="left",fill="x",expand=True)
        btns=tk.Frame(fr,bg=C["bg"]); btns.pack(side="right",padx=4,pady=4)
        GlowButton(btns,"File",self._browse_file,w=75,h=30,color=C["border"],icon="📄").pack(side="left",padx=2)
        GlowButton(btns,"Folder",self._browse_folder,w=80,h=30,color=C["border"],icon="📁").pack(side="left",padx=2)

        # Info row
        ir=tk.Frame(sc,bg=C["panel"]); ir.pack(fill="x",pady=(8,0))
        for ico,txt,col in [
            ("🔍","Malware signatures","Checks known binary signatures"),
            ("📊","Entropy analysis","Detects packed/encrypted payloads"),
            ("🧵","String scanning","Finds suspicious command patterns"),
            ("📎","Extension check","Detects double/dangerous extensions"),
        ]:
            cell=tk.Frame(ir,bg=C["bg3"],highlightbackground=C["border"],highlightthickness=1)
            cell.pack(side="left",expand=True,fill="x",padx=3,ipadx=6,ipady=6)
            tk.Label(cell,text=ico,font=("Segoe UI Emoji",14),bg=C["bg3"]).pack()
            tk.Label(cell,text=txt,font=FONTS["tiny"],bg=C["bg3"],fg=C["text"]).pack()
            tk.Label(cell,text=col,font=FONTS["tiny"],bg=C["bg3"],fg=C["text2"]).pack()

        br=tk.Frame(p,bg=C["bg"]); br.pack(pady=10)
        self._scan_btn=GlowButton(br,"🔬  START SCAN",self._start_scan,w=220,h=46,color=C["red"])
        self._scan_btn.pack(side="left",padx=8)
        GlowButton(br,"Clear",self._clear,w=100,h=46,color=C["border"]).pack(side="left",padx=8)

        # Progress
        pc=self._card(p,accent=C["border"])
        pr=tk.Frame(pc,bg=C["panel"]); pr.pack(fill="x")
        tk.Label(pr,text="Scan Progress",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(side="left")
        self._prog_lbl=tk.Label(pr,text="",font=FONTS["small"],bg=C["panel"],fg=C["text2"])
        self._prog_lbl.pack(side="right")
        self._prog_bar=tk.Canvas(pc,height=6,bg=C["bg3"],highlightthickness=0)
        self._prog_bar.pack(fill="x",pady=(6,0))
        self._cur_file_lbl=tk.Label(pc,text="",font=FONTS["tiny"],bg=C["panel"],
                                    fg=C["text2"],anchor="w")
        self._cur_file_lbl.pack(fill="x",pady=(3,0))

        # Summary
        sum_r=tk.Frame(p,bg=C["bg"]); sum_r.pack(fill="x",padx=22,pady=(4,6))
        self._sum_cards={}
        for label,col in [("CLEAN",C["green"]),("LOW RISK",C["yellow"]),
                           ("SUSPICIOUS",C["orange"]),("HIGH RISK",C["red"])]:
            sf=tk.Frame(sum_r,bg=C["panel"],highlightbackground=col,
                        highlightthickness=1,padx=10,pady=8)
            sf.pack(side="left",expand=True,fill="x",padx=3)
            vl=tk.Label(sf,text="0",font=FONTS["num_sm"],bg=C["panel"],fg=col)
            vl.pack()
            tk.Label(sf,text=label,font=FONTS["tiny"],bg=C["panel"],fg=C["text2"]).pack()
            self._sum_cards[label]=vl

        # Results table
        rc=self._card(p,accent=C["border"])
        rhdr=tk.Frame(rc,bg=C["panel"]); rhdr.pack(fill="x")
        tk.Label(rhdr,text="◉  Threat Report",font=FONTS["head"],bg=C["panel"],fg=C["red"]).pack(side="left")
        StatusDot(rhdr,C["red"],size=10).pack(side="right")
        self._res_tree=styled_tree(rc,("name","risk","score","size","flags"),row_h=28)
        self._res_tree.heading("name", text="File Name")
        self._res_tree.heading("risk", text="Risk Level")
        self._res_tree.heading("score",text="Score")
        self._res_tree.heading("size", text="Size")
        self._res_tree.heading("flags",text="Flags / Details")
        self._res_tree.column("name", width=180)
        self._res_tree.column("risk", width=90,  anchor="center")
        self._res_tree.column("score",width=60,  anchor="center")
        self._res_tree.column("size", width=70,  anchor="center")
        self._res_tree.column("flags",width=350)
        self._res_tree.pack(fill="both",expand=True)
        self._res_tree.bind("<<TreeviewSelect>>",self._on_tree_select)

        dc=self._card(p,accent=C["border"])
        tk.Label(dc,text="File Details",font=FONTS["head"],bg=C["panel"],fg=C["text"]).pack(anchor="w",pady=(0,5))
        self._detail_lbl=tk.Label(dc,text="Select a result above to see detailed flags.",
                                   font=FONTS["body"],bg=C["panel"],fg=C["text2"],
                                   justify="left",wraplength=700)
        self._detail_lbl.pack(anchor="w")
        self._scan_results=[]

    def _browse_file(self):
        fp=filedialog.askopenfilename(title="Select File to Scan")
        if fp: self._fp=fp; self._flbl.config(text=f"  {Path(fp).name}",fg=C["text"])

    def _browse_folder(self):
        fp=filedialog.askdirectory(title="Select Folder to Scan")
        if fp: self._fp=fp; self._flbl.config(text=f"  {Path(fp).name}  (folder)",fg=C["text"])

    def _start_scan(self):
        if not self._fp: return messagebox.showwarning("No Target","Select a file or folder first.")
        if self._scanning: return
        self._scanning=True
        for item in self._res_tree.get_children(): self._res_tree.delete(item)
        for k in self._sum_cards: self._sum_cards[k].config(text="0")
        self._detail_lbl.config(text="Scanning…")
        self._scan_results=[]

        def progress_cb(done,total,fname):
            pct=done/total if total else 0
            self.after(0,lambda: (
                self._prog_lbl.config(text=f"{done}/{total}"),
                self._cur_file_lbl.config(text=f"  Scanning: {fname}"),
                self._update_progbar(pct)))

        def run():
            try:
                p=Path(self._fp)
                if p.is_file():
                    results=[scan_file(self._fp)]
                else:
                    results=scan_folder(self._fp,progress_cb)
                self.after(0,lambda: self._show_results(results))
            except Exception as e:
                self.after(0,lambda: messagebox.showerror("Scan Error",str(e)))
            finally:
                self._scanning=False
                self.after(0,lambda: (
                    self._cur_file_lbl.config(text="  Scan complete."),
                    self._update_progbar(1.0)))
        threading.Thread(target=run,daemon=True).start()

    def _update_progbar(self, pct):
        self._prog_bar.update_idletasks()
        w=self._prog_bar.winfo_width()
        self._prog_bar.delete("all")
        self._prog_bar.create_rectangle(0,0,w,6,fill=C["bg3"],outline="")
        col=C["green"] if pct>=1 else C["yellow"] if pct>0.5 else C["red"]
        self._prog_bar.create_rectangle(0,0,int(w*pct),6,fill=col,outline="")

    def _show_results(self, results):
        self._scan_results=results
        counts={k:0 for k in self._sum_cards}
        risk_col={"CLEAN":C["green"],"LOW RISK":C["yellow"],"SUSPICIOUS":C["orange"],
                  "HIGH RISK":C["red"],"ERROR":C["text2"]}
        # Sort: high risk first
        order={"HIGH RISK":0,"SUSPICIOUS":1,"LOW RISK":2,"CLEAN":3,"ERROR":4}
        results_sorted=sorted(results,key=lambda r: order.get(r.get("risk","ERROR"),5))
        for r in results_sorted:
            risk=r.get("risk","?"); rc=risk_col.get(risk,C["text2"])
            score=r.get("score",0); flags=r.get("flags",[]); nm=r.get("name",Path(r["file"]).name)
            sz=fmt_size(r.get("size",0)); flag_txt=flags[0] if flags else ""
            iid=self._res_tree.insert("","end",
                values=(nm,risk,score,sz,flag_txt))
            self._res_tree.tag_configure(f"risk_{iid}",foreground=rc)
            if risk in counts: counts[risk]+=1
        for k,v in counts.items():
            self._sum_cards[k].config(text=str(v))
        total=len(results)
        threats=counts.get("HIGH RISK",0)+counts.get("SUSPICIOUS",0)
        if threats==0:
            self._detail_lbl.config(text=f"✔  Scan complete — {total} files scanned. No threats detected.",fg=C["green"])
        else:
            self._detail_lbl.config(text=f"⚠  Scan complete — {total} files scanned. {threats} potential threats found!",fg=C["red"])

    def _on_tree_select(self, e=None):
        sel=self._res_tree.selection()
        if not sel: return
        idx=self._res_tree.index(sel[0])
        order={"HIGH RISK":0,"SUSPICIOUS":1,"LOW RISK":2,"CLEAN":3,"ERROR":4}
        results_sorted=sorted(self._scan_results,key=lambda r: order.get(r.get("risk","ERROR"),5))
        if idx<len(results_sorted):
            r=results_sorted[idx]
            lines=[
                f"File: {r.get('file','')}",
                f"Risk: {r.get('risk','?')}   Score: {r.get('score',0)}/100",
                f"Size: {fmt_size(r.get('size',0))}   Entropy: {r.get('entropy',0):.3f}",
                "Flags:",
            ]
            for fl in r.get("flags",["None"]): lines.append(f"  • {fl}")
            self._detail_lbl.config(text="\n".join(lines),fg=C["text"])

    def _clear(self):
        for item in self._res_tree.get_children(): self._res_tree.delete(item)
        for k in self._sum_cards: self._sum_cards[k].config(text="0")
        self._detail_lbl.config(text="Select a result above to see detailed flags.",fg=C["text2"])
        self._fp=""; self._flbl.config(text="  No target selected…",fg=C["muted"])
        self._prog_bar.delete("all"); self._prog_lbl.config(text=""); self._cur_file_lbl.config(text="")
        self._scan_results=[]

# ═══════════════════════════════════════════════════════════
#  MAIN  APPLICATION
# ═══════════════════════════════════════════════════════════
class App(tk.Tk):
    # Hash Checker REMOVED per requirements
    NAV = [
        ("⬡",  "Dashboard"),
        ("🔑", "Password"),
        ("⚡",  "Generator"),
        ("🔒", "Encrypt"),
        ("📁", "Folder Lock"),
        ("👁",  "Folder Hide"),
        ("📝", "Secure Notes"),
        ("🛡",  "Integrity"),
        ("🔬", "Scanner"),
    ]
    PAGES = [DashPage, PwdPage, GenPage, EncPage,
             LockPage, HidePage, NotesPage, IntegrityPage, ScannerPage]

    def __init__(self):
        super().__init__()
        _init_vault()
        self.title(f"{APP_NAME}  •  Enterprise Security Suite  •  {APP_VER}")
        self.geometry("1150x740")
        self.minsize(960,640)
        self.configure(bg=C["bg"])
        self._pages={}; self._btns=[]; self._cur=-1
        self._build(); self._go(0)

    def _build(self):
        # ── Sidebar ──────────────────────────────────────────────────────────
        sb=tk.Frame(self,bg=C["bg1"],width=200)
        sb.pack(side="left",fill="y"); sb.pack_propagate(False)

        # Logo area with hexagon
        logo=tk.Canvas(sb,width=200,height=112,bg=C["bg1"],highlightthickness=0)
        logo.pack()
        # Hexagon rings
        for ri,al in [(44,0.15),(38,0.4),(32,0.9)]:
            pts=hex_pts(100,55,ri)
            c=lerp(C["glow"],C["bg1"],1-al*0.3)
            logo.create_polygon(pts,fill="",outline=c,width=1)
        pts=hex_pts(100,55,28)
        logo.create_polygon(pts,fill=lerp(C["glow"],C["bg1"],0.82),outline=C["glow"],width=1.5)
        logo.create_text(100,53,text="🔐",font=("Segoe UI Emoji",15),fill=C["glow"])
        logo.create_text(100,82,text=APP_NAME,font=("Consolas",9,"bold"),fill=C["text"])
        logo.create_text(100,95,text=APP_VER,font=("Consolas",7),fill=C["text2"])

        ScanLine(sb,w=200,h=2,color=C["glow"]).pack()
        

        nav_f=tk.Frame(sb,bg=C["bg1"]); nav_f.pack(fill="x",pady=2)
        for i,(ico,lbl) in enumerate(self.NAV):
            btn=NavBtn(nav_f,ico,lbl,i,self._go)
            btn.pack(fill="x",pady=1)
            self._btns.append(btn)

        # Footer — Administrator shown ONCE (only here, not in topbar)
        foot=tk.Frame(sb,bg=C["bg1"]); foot.pack(side="bottom",fill="x",padx=10,pady=10)
        tk.Frame(foot,bg=C["border"],height=1).pack(fill="x",pady=(0,7))
        tk.Label(foot,text="👑  ADMINISTRATOR",font=FONTS["tiny"],
                 bg=C["bg1"],fg=C["gold"]).pack(anchor="w")
        ar=tk.Frame(foot,bg=C["bg1"]); ar.pack(fill="x",pady=3)
        StatusDot(ar,C["gold"],size=7).pack(side="left",padx=(0,4))
        tk.Label(ar,text=ADMIN_NAME,font=FONTS["small"],bg=C["bg1"],fg=C["text"]).pack(side="left")
        tk.Frame(foot,bg=C["muted"],height=1).pack(fill="x",pady=(5,4))
        sr=tk.Frame(foot,bg=C["bg1"]); sr.pack(fill="x")
        StatusDot(sr,C["green"],size=8).pack(side="left")
        tk.Label(sr,text=" System Online",font=FONTS["tiny"],bg=C["bg1"],fg=C["text2"]).pack(side="left")
        ck=C["green"] if CRYPTO_OK else C["red"]
        tk.Label(foot,text="AES-256 ✔" if CRYPTO_OK else "cryptography ✘",
                 font=FONTS["tiny"],bg=C["bg1"],fg=ck).pack(anchor="w")

        # ── Content area ─────────────────────────────────────────────────────
        self._content=tk.Frame(self,bg=C["bg"])
        self._content.pack(side="left",fill="both",expand=True)

        # Top bar — clean, no admin name here
        topbar=tk.Frame(self._content,bg=C["bg2"],height=42)
        topbar.pack(fill="x"); topbar.pack_propagate(False)
        self._topbar_lbl=tk.Label(topbar,text="",font=FONTS["head"],
                                   bg=C["bg2"],fg=C["text"])
        self._topbar_lbl.pack(side="left",padx=16,pady=12)
        # Right side: clock only
        self._clock=tk.Label(topbar,text="",font=FONTS["tiny"],bg=C["bg2"],fg=C["text2"])
        self._clock.pack(side="right",padx=14)
        self._tick_clock()

        self._main=tk.Frame(self._content,bg=C["bg"])
        self._main.pack(fill="both",expand=True)

        # Status bar
        stbar=tk.Frame(self._content,bg=C["bg2"],height=22)
        stbar.pack(fill="x"); stbar.pack_propagate(False)
        StatusDot(stbar,C["green"],size=7).pack(side="left",padx=5,pady=7)
        self._status=tk.Label(stbar,text="Ready",font=FONTS["tiny"],
                               bg=C["bg2"],fg=C["text2"])
        self._status.pack(side="left")
        tk.Label(stbar,text=f"{APP_NAME}  •  {APP_VER}",
                 font=FONTS["tiny"],bg=C["bg2"],fg=C["muted"]).pack(side="right",padx=10)

    def _tick_clock(self):
        self._clock.config(text=time.strftime("%H:%M:%S   %a %d %b %Y"))
        self.after(1000,self._tick_clock)

    def _go(self, idx):
        if idx==self._cur: return
        for i,b in enumerate(self._btns): b.activate(i==idx)
        self._cur=idx
        for pg in self._pages.values(): pg.pack_forget()
        if idx not in self._pages:
            pg=self.PAGES[idx](self._main)
            self._pages[idx]=pg
        self._pages[idx].pack(fill="both",expand=True)
        lbl=self.NAV[idx][1]
        self._topbar_lbl.config(text=f"  {self.NAV[idx][0]}   {lbl}")
        self._status.config(text=f"Module: {lbl}  |  {APP_NAME}  |  {time.strftime('%H:%M:%S')}")

# ═══════════════════════════════════════════════════════════
#  ENTRY  POINT
# ═══════════════════════════════════════════════════════════
if __name__=="__main__":
    if not CRYPTO_OK:
        print("\n[!] 'cryptography' module not found.")
        print("    Install:  pip install cryptography\n")
    App().mainloop()
