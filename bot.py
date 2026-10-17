# =========================================================
#  HOSTING BOTU - ÇOKLU BOT (MAX 10) - BUTONLU
#  Token ve ID'yi aşağıdaki 2 satıra yaz.
# =========================================================
BOT_TOKEN = "7882714192:AAEjW4q0bMekWR1gzox-SxUeiEH_tSuRJgM"
ALLOWED_USER_ID = 8984033559
# =========================================================

import os
import sys
import signal
import subprocess
import threading
import time
import json
import shutil
from pathlib import Path
from datetime import datetime

try:
    import telebot
    from telebot import types
except ImportError:
    print("Kur: pip install pyTelegramBotAPI"); sys.exit(1)

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    print("HATA: BOT_TOKEN geçersiz."); sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ---------------- DİZİN ----------------
BASE_DIR = Path(__file__).parent.resolve()
BOTS_DIR = BASE_DIR / "bots"
BOTS_DIR.mkdir(exist_ok=True)
STATE_FILE = BASE_DIR / "state.json"
MAX_BOTS = 10

# ---------------- DURUM ----------------
# state = { "bots": { "bot1": {"name": "...", "folder": "...", "created": "..."} } }
# process'ler ayrı tutulur: processes = { "bot1": Popen }
processes = {}
log_handles = {}
monitor_threads = {}
lock = threading.Lock()

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"bots": {}}
    return {"bots": {}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

state = load_state()

# ---------------- YARDIMCI ----------------
def is_allowed(message) -> bool:
    return message.from_user and message.from_user.id == ALLOWED_USER_ID

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def bot_dir(name: str) -> Path:
    return BOTS_DIR / name

def log_path(name: str) -> Path:
    return bot_dir(name) / "log.txt"

def is_running(name: str) -> bool:
    p = processes.get(name)
    return p is not None and p.poll() is None

def safe_send(chat_id, text, kb=None):
    try: bot.send_message(chat_id, text, reply_markup=kb)
    except Exception: pass

def kill_pid(pid: int) -> bool:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                time.sleep(0.25)
                try: os.kill(pid, 0)
                except OSError: return True
            os.kill(pid, signal.SIGKILL)
        return True
    except Exception:
        return False

# ---------------- KLAVYELER ----------------
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🤖 Botlarım", callback_data="list"),
        types.InlineKeyboardButton("➕ Bot Ekle", callback_data="add"),
    )
    kb.add(
        types.InlineKeyboardButton("📊 Durum", callback_data="all_status"),
        types.InlineKeyboardButton("ℹ️ Yardım", callback_data="help"),
    )
    return kb

def bots_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    bots_list = state.get("bots", {})
    if not bots_list:
        kb.add(types.InlineKeyboardButton("➕ İlk botunu ekle", callback_data="add"))
    else:
        for name in sorted(bots_list.keys()):
            running = is_running(name)
            icon = "🟢" if running else "🔴"
            kb.add(types.InlineKeyboardButton(
                f"{icon} {name}", callback_data=f"open:{name}"
            ))
    kb.add(types.InlineKeyboardButton("➕ Bot Ekle", callback_data="add"))
    kb.add(types.InlineKeyboardButton("⬅️ Geri", callback_data="menu"))
    return kb

def bot_menu(name: str):
    kb = types.InlineKeyboardMarkup(row_width=2)
    running = is_running(name)
    if running:
        kb.add(
            types.InlineKeyboardButton("🛑 Durdur", callback_data=f"stop:{name}"),
            types.InlineKeyboardButton("♻️ Yeniden Başlat", callback_data=f"restart:{name}"),
        )
    else:
        kb.add(types.InlineKeyboardButton("🚀 Başlat", callback_data=f"start:{name}"))
    kb.add(
        types.InlineKeyboardButton("📄 Log", callback_data=f"log:{name}"),
        types.InlineKeyboardButton("👀 Son 30 Satır", callback_data=f"tail:{name}"),
    )
    kb.add(
        types.InlineKeyboardButton("📤 bot.py Yükle", callback_data=f"upbot:{name}"),
        types.InlineKeyboardButton("📤 req.txt Yükle", callback_data=f"upreq:{name}"),
    )
    kb.add(
        types.InlineKeyboardButton("🗑️ Botu Sil", callback_data=f"delask:{name}"),
        types.InlineKeyboardButton("⬅️ Botlar", callback_data="list"),
    )
    return kb

# ---------------- /start ----------------
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    if not is_allowed(message):
        bot.reply_to(message, "⛔ Yetkin yok."); return
    bot.send_message(
        message.chat.id,
        f"🤖 Hosting Bot — Çoklu (max {MAX_BOTS})\n\n"
        f"Aktif bot: {len(state.get('bots', {}))}/{MAX_BOTS}\n\n"
        "Aşağıdaki menüden yönet.",
        reply_markup=main_menu()
    )

# ---------------- Callback ----------------
@bot.callback_query_handler(func=lambda c: True)
def on_cb(call):
    if call.from_user.id != ALLOWED_USER_ID:
        bot.answer_callback_query(call.id, "⛔ Yetkin yok."); return

    data = call.data

    if data == "menu":
        bot.edit_message_text("🤖 Ana Menü", call.message.chat.id, call.message.message_id,
                              reply_markup=main_menu())
        bot.answer_callback_query(call.id)

    elif data == "help":
        bot.edit_message_text(
            "ℹ️ Yardım\n\n"
            "1️⃣ Bot Ekle → isim ver\n"
            "2️⃣ Bot kartından bot.py ve requirements.txt yükle\n"
            "3️⃣ Başlat butonuna bas\n\n"
            "Her botun kendi klasörü ve logu var.\n"
            f"Limit: {MAX_BOTS} bot",
            call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("⬅️ Geri", callback_data="menu"))
        )
        bot.answer_callback_query(call.id)

    elif data == "list":
        bots_list = state.get("bots", {})
        txt = f"🤖 Botlarım ({len(bots_list)}/{MAX_BOTS})"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                              reply_markup=bots_menu())
        bot.answer_callback_query(call.id)

    elif data == "add":
        if len(state.get("bots", {})) >= MAX_BOTS:
            bot.answer_callback_query(call.id, f"Limit {MAX_BOTS}!", show_alert=True); return
        msg = bot.send_message(call.message.chat.id,
            "➕ Yeni bot için isim yaz (örn: `kopya_bot`, sadece harf/rakam/_).\n"
            "İptal: /start")
        bot.register_next_step_handler(msg, step_add_name)
        bot.answer_callback_query(call.id)

    elif data.startswith("open:"):
        name = data.split(":", 1)[1]
        if name not in state["bots"]:
            bot.answer_callback_query(call.id, "Bot yok."); return
        running = is_running(name)
        icon = "🟢 Çalışıyor" if running else "🔴 Duruyor"
        info = state["bots"][name]
        txt = (f"🤖 {name}\n{icon}\n"
               f"Oluşturulma: {info.get('created', '-')}")
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id,
                              reply_markup=bot_menu(name))
        bot.answer_callback_query(call.id)

    elif data == "all_status":
        bots_list = state.get("bots", {})
        if not bots_list:
            bot.answer_callback_query(call.id, "Bot yok.", show_alert=True); return
        lines = []
        for n in sorted(bots_list.keys()):
            lines.append(f"{'🟢' if is_running(n) else '🔴'} {n}")
        bot.edit_message_text("📊 Durum\n\n" + "\n".join(lines),
                              call.message.chat.id, call.message.message_id,
                              reply_markup=types.InlineKeyboardMarkup().add(
                                  types.InlineKeyboardButton("⬅️ Geri", callback_data="menu")))
        bot.answer_callback_query(call.id)

    elif data.startswith("start:"):
        name = data.split(":", 1)[1]
        ok = start_bot(name, call.message.chat.id)
        bot.answer_callback_query(call.id, "Başlatıldı" if ok else "Hata")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=bot_menu(name))
        except Exception: pass

    elif data.startswith("stop:"):
        name = data.split(":", 1)[1]
        ok = stop_bot(name, call.message.chat.id)
        bot.answer_callback_query(call.id, "Durduruldu" if ok else "Hata")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=bot_menu(name))
        except Exception: pass

    elif data.startswith("restart:"):
        name = data.split(":", 1)[1]
        stop_bot(name, call.message.chat.id, silent=True)
        time.sleep(1)
        ok = start_bot(name, call.message.chat.id)
        bot.answer_callback_query(call.id, "Yeniden başlatıldı" if ok else "Hata")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=bot_menu(name))
        except Exception: pass

    elif data.startswith("log:"):
        name = data.split(":", 1)[1]
        lp = log_path(name)
        if not lp.exists() or lp.stat().st_size == 0:
            bot.answer_callback_query(call.id, "Log boş.", show_alert=True); return
        try:
            with open(lp, "rb") as f:
                bot.send_document(call.message.chat.id, f, caption=f"📄 {name} log")
            bot.answer_callback_query(call.id, "Gönderildi")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Hata: {e}", show_alert=True)

    elif data.startswith("tail:"):
        name = data.split(":", 1)[1]
        lp = log_path(name)
        if not lp.exists():
            bot.answer_callback_query(call.id, "Log yok.", show_alert=True); return
        try:
            lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
            txt = "\n".join(lines) or "(boş)"
            if len(txt) > 3800: txt = txt[-3800:]
            bot.send_message(call.message.chat.id, f"📄 {name} son 30 satır:\n{txt}")
            bot.answer_callback_query(call.id)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Hata: {e}", show_alert=True)

    elif data.startswith("upbot:"):
        name = data.split(":", 1)[1]
        msg = bot.send_message(call.message.chat.id,
            f"📤 `{name}` için `bot.py` dosyasını gönder.\nİptal: /start")
        bot.register_next_step_handler(msg, step_upload, name, "bot.py")
        bot.answer_callback_query(call.id)

    elif data.startswith("upreq:"):
        name = data.split(":", 1)[1]
        msg = bot.send_message(call.message.chat.id,
            f"📤 `{name}` için `requirements.txt` dosyasını gönder.\nİptal: /start")
        bot.register_next_step_handler(msg, step_upload, name, "requirements.txt")
        bot.answer_callback_query(call.id)

    elif data.startswith("delask:"):
        name = data.split(":", 1)[1]
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Evet, sil", callback_data=f"delok:{name}"),
            types.InlineKeyboardButton("❌ Vazgeç", callback_data=f"open:{name}"),
        )
        bot.edit_message_text(f"🗑️ `{name}` silinsin mi? Durdurulacak ve klasörü silinecek.",
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)

    elif data.startswith("delok:"):
        name = data.split(":", 1)[1]
        stop_bot(name, call.message.chat.id, silent=True)
        with lock:
            state.get("bots", {}).pop(name, None)
            save_state(state)
        try:
            shutil.rmtree(bot_dir(name), ignore_errors=True)
        except Exception: pass
        bot.answer_callback_query(call.id, "Silindi")
        bot.edit_message_text("🗑️ Silindi.", call.message.chat.id, call.message.message_id,
                              reply_markup=bots_menu())

    else:
        bot.answer_callback_query(call.id)

# ---------------- Adım: isim ----------------
def step_add_name(message):
    if not is_allowed(message):
        return
    if not message.text or message.text.startswith("/"):
        safe_send(message.chat.id, "İptal."); return
    name = message.text.strip().replace(" ", "_")
    if not name.replace("_", "").isalnum() or len(name) > 32:
        safe_send(message.chat.id, "❌ Geçersiz isim. Sadece harf/rakam/_ (max 32).")
        return
    if name in state["bots"]:
        safe_send(message.chat.id, "❌ Bu isimde bot var."); return
    if len(state["bots"]) >= MAX_BOTS:
        safe_send(message.chat.id, f"❌ Limit {MAX_BOTS}."); return

    d = bot_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    with lock:
        state["bots"][name] = {
            "created": ts(),
            "folder": str(d),
        }
        save_state(state)
    safe_send(message.chat.id, f"✅ `{name}` eklendi. Bot kartına gir, dosyaları yükle.",
              kb=bots_menu())

# ---------------- Adım: dosya yükleme ----------------
def step_upload(message, name: str, expected: str):
    if not is_allowed(message):
        return
    if not message.document:
        safe_send(message.chat.id, "❌ Dosya göndermedin. İptal."); return
    doc = message.document
    if doc.file_name != expected:
        safe_send(message.chat.id, f"❌ Dosya adı `{expected}` olmalı."); return
    if name not in state["bots"]:
        safe_send(message.chat.id, "❌ Bot yok."); return
    try:
        fi = bot.get_file(doc.file_id)
        data = bot.download_file(fi.file_path)
        target = bot_dir(name) / expected
        with open(target, "wb") as f: f.write(data)
        safe_send(message.chat.id, f"✅ `{name}/{expected}` kaydedildi ({len(data)} bayt).",
                  kb=bot_menu(name))
    except Exception as e:
        safe_send(message.chat.id, f"❌ İndirme hatası: {e}")

# ---------------- Başlat / Durdur ----------------
def start_bot(name: str, chat_id: int) -> bool:
    if name not in state["bots"]:
        safe_send(chat_id, "❌ Bot yok."); return False
    with lock:
        if is_running(name):
            safe_send(chat_id, f"⚠️ `{name}` zaten çalışıyor."); return False
        d = bot_dir(name)
        bot_py = d / "bot.py"
        req_txt = d / "requirements.txt"
        if not bot_py.exists():
            safe_send(chat_id, f"❌ `{name}/bot.py` yok."); return False

        if req_txt.exists():
            safe_send(chat_id, f"📦 `{name}` bağımlılıkları kuruluyor...")
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_txt)],
                    cwd=str(d), capture_output=True, text=True, timeout=600
                )
                if r.returncode != 0:
                    safe_send(chat_id, f"❌ pip hatası:\n{r.stderr[-1200:]}")
                    return False
            except subprocess.TimeoutExpired:
                safe_send(chat_id, "❌ pip zaman aşımı."); return False
            except Exception as e:
                safe_send(chat_id, f"❌ pip: {e}"); return False

        try:
            lp = log_path(name)
            lp.write_text(f"=== [{ts()}] {name} başlatıldı ===\n", encoding="utf-8")
            lh = open(lp, "a", encoding="utf-8", buffering=1)
            log_handles[name] = lh
            p = subprocess.Popen(
                [sys.executable, "-u", "bot.py"],
                cwd=str(d), stdout=lh, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            processes[name] = p
        except Exception as e:
            safe_send(chat_id, f"❌ Başlatma: {e}"); return False

        safe_send(chat_id, f"🚀 `{name}` başladı. PID: {p.pid}")
        threading.Thread(target=monitor, args=(name, chat_id), daemon=True).start()
        return True

def stop_bot(name: str, chat_id: int, silent=False) -> bool:
    with lock:
        p = processes.get(name)
        if not p or p.poll() is not None:
            if not silent: safe_send(chat_id, f"ℹ️ `{name}` çalışmıyor.")
            processes.pop(name, None)
            return False
        try:
            kill_pid(p.pid)
            processes.pop(name, None)
            lh = log_handles.pop(name, None)
            if lh:
                try: lh.close()
                except Exception: pass
            if not silent: safe_send(chat_id, f"🛑 `{name}` durduruldu.")
            return True
        except Exception as e:
            if not silent: safe_send(chat_id, f"❌ Durdurma: {e}")
            return False

# ---------------- İzleme ----------------
def monitor(name: str, chat_id: int):
    while True:
        time.sleep(5)
        p = processes.get(name)
        if p is None: return
        if p.poll() is not None:
            code = p.returncode
            processes.pop(name, None)
            safe_send(chat_id, f"🚨 `{name}` durdu! Çıkış kodu: {code}")
            # Watchdog: 3 deneme
            for attempt in range(1, 4):
                if name not in state["bots"]:
                    return
                safe_send(chat_id, f"♻️ `{name}` watchdog {attempt}/3...")
                time.sleep(3)
                if start_bot(name, chat_id):
                    safe_send(chat_id, f"✅ `{name}` yeniden başladı.")
                    return
            safe_send(chat_id, f"❌ `{name}` watchdog başaramadı.")
            return

# ---------------- Başlat ----------------
if __name__ == "__main__":
    print(f"Hosting bot çalışıyor... Max {MAX_BOTS} bot.")
    bot.infinity_polling(timeout=30, long_polling_timeout=25)