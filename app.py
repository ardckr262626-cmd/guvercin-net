import os
import re
import time
import threading
from datetime import datetime

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from supabase import create_client
from werkzeug.security import check_password_hash, generate_password_hash

# .env dosyasını oku
load_dotenv()

# Supabase bağlantısını kur
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'change-this-in-production'),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', '0') == '1',
    PREFERRED_URL_SCHEME='https',
    DEBUG=False,
    ENV='production',
)

state_lock = threading.Lock()
messages = []
logs = []
muted_users = {}
slowmode_seconds = 0
last_message_times = {}
recent_messages = {}
MIN_MESSAGE_INTERVAL = 1  # seconds, minimal interval for non-Kurucu users to avoid rapid double-posting


def clean_input(value):
    return re.sub(r"[^A-Za-z0-9ğüşöçıİĞÜŞÖÇ\s_-]", "", (value or "").strip())


def hash_password(password):
    if not password:
        return ""
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password, stored_hash):
    if not password or not stored_hash:
        return False

    if stored_hash.startswith(("pbkdf2:", "sha256:", "bcrypt:", "scrypt:")):
        try:
            return check_password_hash(stored_hash, password)
        except ValueError:
            return False

    return password == stored_hash


def load_roles():
    try:
        response = supabase.table("kuslar").select("id, isim, rol").execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase yükleme hatası: {response.error}")
            return {}
        return {item['isim']: {'rol': item['rol']} for item in response.data or []}
    except Exception as e:
        print(f"Supabase kuş verisi çekilirken hata oluştu: {e}")
        return {}


def load_kuslar():
    try:
        response = supabase.table("kuslar").select("id, isim, rol").execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase kuş listesi hatası: {response.error}")
            return []
        return response.data or []
    except Exception as e:
        print(f"Supabase kuş listisi çekilirken hata oluştu: {e}")
        return []


def get_all_kuslar():
    try:
        response = supabase.table("kuslar").select("id, isim, rol").execute()
        if hasattr(response, "error") and response.error:
            raise RuntimeError(response.error)
        return response.data or []
    except Exception as e:
        print(f"Supabase kuş listesini çekerken hata oluştu: {e}")
        return []


@app.route('/api/kuslar')
def api_kuslar():
    kuslar = get_all_kuslar()
    return jsonify({"kuslar": kuslar})


def delete_kus_by_id(kus_id):
    try:
        response = supabase.table("kuslar").delete().eq("id", kus_id).execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase kuş silme hatası: {response.error}")
            return False
        return True
    except Exception as e:
        print(f"Supabase kuş silme hatası: {e}")
        return False


def get_user_data(username):
    try:
        response = supabase.table("kuslar").select("id, isim, sifre, rol").eq("isim", username).single().execute()
        if hasattr(response, "error") and response.error:
            return None
        return response.data
    except Exception as e:
        return None


def upsert_user(name, password, role):
    name = clean_input(name)
    role = clean_input(role) or 'Yavru Kuş'
    
    existing_user = get_user_data(name)
    
    # Aga BUG FIX: Yeni kullanıcı eklerken şifre yoksa direkt reddet
    if not existing_user and not password:
        return False
        
    data = {
        "isim": name,
        "rol": role,
    }

    if password:
        data["sifre"] = hash_password(password)

    try:
        if existing_user:
            response = supabase.table("kuslar").update(data).eq("isim", name).execute()
        else:
            response = supabase.table("kuslar").insert(data).execute()
            
        if hasattr(response, "error") and response.error:
            print(f"Supabase kullanıcı kaydetme hatası ({name}): {response.error}")
            return False
        return True
    except Exception as e:
        print("Hata var aga:", str(e))
        return False


def delete_user(name):
    try:
        response = supabase.table("kuslar").delete().eq("isim", name).execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase kullanıcı silme hatası ({name}): {response.error}")
            return False
        return True
    except Exception as e:
        print(f"Supabase kullanıcı silme hatası: {e}")
        return False


def update_user_by_id(kus_id, data):
    try:
        response = supabase.table("kuslar").update(data).eq("id", kus_id).execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase kullanıcı güncelleme hatası (id={kus_id}): {response.error}")
            return False
        return True
    except Exception as e:
        print(f"Supabase kullanıcı güncelleme hatası: {e}")
        return False


def normalize_role(role):
    if not role or not isinstance(role, str):
        return ''
    return role.strip().lower()


def get_user_role(username):
    user = get_user_data(username)
    if user and isinstance(user.get('rol'), str):
        return user['rol'].strip()
    return 'Yavru Kuş'


def is_kurucu(username):
    return normalize_role(get_user_role(username)) == 'kurucu güvercin'


def is_admin(username):
    return normalize_role(get_user_role(username)) in {'kurucu güvercin', 'yan admin'}


def add_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    with state_lock:
        logs.append(f'[{timestamp}] {message}')
        if len(logs) > 100:
            del logs[:-100]


def add_message(sender, role, text, recipient=None):
    with state_lock:
        messages.append({
            'gonderen': sender,
            'rol': role,
            'metin': text,
            'ozel_alici': recipient,
        })
        if len(messages) > 200:
            del messages[:-200]


def cleanup_expired_mutes():
    now = time.time()
    expired = [name for name, until in muted_users.items() if until <= now]
    for name in expired:
        muted_users.pop(name, None)


def mute_user(username, duration_minutes=20, reason='spam'):
    if not username:
        return False
    username = clean_input(username)
    expires_at = time.time() + duration_minutes * 60
    muted_users[username] = expires_at
    if reason == 'spam':
        add_message('SİSTEM', '🛡️ Otomasyon', f'Sistem {username} kuşunu spamdan dolayı {duration_minutes} dakika susturdu.')
        add_log(f'🔇 Sistem {username} kuşunu spamdan dolayı {duration_minutes} dakika susturdu.')
    else:
        add_message('SİSTEM', '🛡️ Otomasyon', f'Sistem {username} kuşunu {duration_minutes} dakika susturdu.')
        add_log(f'🔇 Sistem {username} kuşunu {duration_minutes} dakika susturdu.')
    return True


def is_user_muted(username):
    cleanup_expired_mutes()
    return username in muted_users


@app.after_request
def secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@app.route('/')
def index():
    active_user = session.get('kus_adi')
    roles = load_roles()
    kuslar_list = load_kuslar()

    if not active_user or active_user not in roles:
        session.pop('kus_adi', None)
        return redirect(url_for('login'))

    return render_template(
        'index.html',
        mesajlar=messages,
        kuslar=roles,
        kuslar_list=kuslar_list,
        aktif_user=active_user,
        mevcut_rol=roles[active_user]['rol'],
        logs=logs,
        susturulanlar=muted_users,
        slowmode=slowmode_seconds,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        name = request.form.get('kus_adi', '').strip()
        password = request.form.get('sifre', '').strip()
        user = get_user_data(name)

        if user and verify_password(password, user.get('sifre', '')):
            session['kus_adi'] = name
            add_log(f'🕊️ {name} kuşu doğru şifreyle kafese süzüldü.')
            return redirect(url_for('index'))
        
        error = 'Giriş başarısız. Kullanıcı adı veya şifre hatalı.'
        
    return render_template('login.html', hata=error)


@app.route('/logout')
def logout():
    session.pop('kus_adi', None)
    return redirect(url_for('login'))


@app.route('/kus-sil/<int:kus_id>', methods=['POST'])
def kus_sil(kus_id):
    active_user = session.get('kus_adi')
    if not active_user or not is_kurucu(active_user):
        abort(403)

    current_user = get_user_data(active_user)
    if current_user and current_user.get('id') == kus_id:
        abort(400)

    if delete_kus_by_id(kus_id):
        add_log(f'🗑️ {active_user} yuvadan bir kuş attı: id={kus_id}')

    return redirect(url_for('index'))


@app.route('/kus-guncelle/<int:kus_id>', methods=['POST'])
def kus_guncelle(kus_id):
    active_user = session.get('kus_adi')
    if not active_user or not is_kurucu(active_user):
        abort(403)

    yeni_isim = request.form.get('yeni_isim', '').strip()
    yeni_sifre = request.form.get('yeni_sifre', '').strip()
    yeni_rol = request.form.get('yeni_rol', '').strip() or 'Yavru Kuş'

    data = {}
    if yeni_isim:
        data['isim'] = clean_input(yeni_isim)
        # isim çakışması kontrolü
        existing = get_user_data(data['isim'])
        if existing and existing.get('id') != kus_id:
            add_log(f'⚠️ {active_user} isim değişikliği denedi, fakat {data["isim"]} zaten var.')
            return redirect(url_for('index'))
    if yeni_rol:
        data['rol'] = clean_input(yeni_rol)
    if yeni_sifre:
        data['sifre'] = hash_password(yeni_sifre)

    if not data:
        return redirect(url_for('index'))

    if update_user_by_id(kus_id, data):
        add_log(f'✏️ {active_user} bir kuşun bilgilerini güncelledi: id={kus_id} ({data.get("isim","-")})')
    else:
        add_log(f'⚠️ {active_user} kullanıcı güncelleme hatası: id={kus_id}')

    # Eğer aktif kullanıcının kendisini güncellediyse session ismini güncelle
    current = get_user_data(active_user)
    try:
        # try to find updated record to adjust session if needed
        updated_roles = load_roles()
        if active_user not in updated_roles:
            # session user name might have been changed — kill session to force re-login
            session.pop('kus_adi', None)
    except Exception:
        pass

    return redirect(url_for('index'))


@app.route('/mesaj-gonder', methods=['POST'])
def mesaj_gonder():
    global slowmode_seconds
    text = request.form.get('mesaj', '').strip()
    user = session.get('kus_adi')

    if not user or not text:
        return redirect(url_for('index'))

    roles = load_roles()
    
    # Aga BUG FIX: Mesaj atarken de yuvada var mı diye son kez kontrol et
    if user not in roles:
        session.pop('kus_adi', None)
        return redirect(url_for('login'))

    role = roles.get(user, {}).get('rol', 'Yavru Kuş')

    if text.startswith('/') and is_admin(user):
        parts = text.split()
        command = parts[0].lower()

        if command == '/clear':
            messages.clear()
            add_message('SİSTEM', '🛡️ Otomasyon', f'🧹 Kafes {user} tarafından tamamen süpürüldü!')
            add_log(f'🧹 {user} chat geçmişini temizledi.')
            return redirect(url_for('index'))

        if command == '/mute' and len(parts) > 1:
            target = parts[1]
            if load_roles().get(target, {}).get('rol') != 'Kurucu Güvercin':
                duration = 20
                if len(parts) > 2:
                    try:
                        duration = int(parts[2])
                    except ValueError:
                        duration = 20
                mute_user(target, duration, reason='manual')
                add_log(f'🔇 {target}, {user} tarafından {duration} dakika susturuldu.')
            return redirect(url_for('index'))

        if command == '/unmute' and len(parts) > 1:
            target = parts[1]
            muted_users.pop(target, None)
            add_message('SİSTEM', '🛡️ Otomasyon', f'🔊 {target} kuşunun cezası {user} tarafından kaldırıldı!')
            add_log(f'🔊 {target} cezası {user} tarafından kaldırıldı.')
            return redirect(url_for('index'))

        if command == '/slowmode' and is_kurucu(user):
            try:
                slowmode_seconds = int(parts[1]) if len(parts) > 1 else 0
            except ValueError:
                slowmode_seconds = 0
            notice = (
                f'⏳ Yavaş mod aktif! Kuşlar {slowmode_seconds} saniyede bir yazabilir.'
                if slowmode_seconds > 0
                else '⚡ Yavaş mod kaldırıldı.'
            )
            add_message('SİSTEM', '🛡️ Otomasyon', notice)
            return redirect(url_for('index'))

        if command == '/system' and is_kurucu(user):
            announcement = ' '.join(parts[1:]).strip()
            if announcement:
                add_message('📢 DUYURU', '👑 Kurucu Özel', f'🚨 {announcement} 🚨')
            return redirect(url_for('index'))

    if text.startswith('/msg'):
        parts = text.split()
        if len(parts) > 2:
            target = parts[1]
            private_text = ' '.join(parts[2:]).strip()
            if private_text:
                add_message(user, role, f'🤫 (Fısıldama): {private_text}', recipient=target)
        return redirect(url_for('index'))

    if is_user_muted(user):
        return redirect(url_for('index'))

    # RATE LIMIT: enforce a minimal interval for non-Kurucu users
    now = time.time()
    if not is_kurucu(user):
        required_interval = max(MIN_MESSAGE_INTERVAL, slowmode_seconds or 0)
        last = last_message_times.get(user, 0)
        if now - last < required_interval:
            return redirect(url_for('index'))
        last_message_times[user] = now

    # DUPLICATE MESSAGE PREVENTION: block repeated identical messages
    user_recent = recent_messages.get(user, {'text': None, 'count': 0, 'time': 0})
    if text == user_recent['text'] and now - user_recent['time'] < 10:
        user_recent['count'] += 1
    else:
        user_recent['text'] = text
        user_recent['count'] = 1
        user_recent['time'] = now

    recent_messages[user] = user_recent

    if user_recent['count'] > 3:
        mute_user(user, duration_minutes=20, reason='spam')
        return redirect(url_for('index'))

    add_message(user, role, text)
    return redirect(url_for('index'))


@app.route('/sifre-ve-rol-ver', methods=['POST'])
def sifre_ve_rol_ver():
    user = session.get('kus_adi')
    if not is_admin(user):
        return abort(403, 'Şifre yönetimi sadece kurucu veya yan admin içindir.')

    name = request.form.get('kus_adi', '').strip()
    password = request.form.get('sifre', '').strip()
    role = request.form.get('rol_adi', '').strip() or 'Yavru Kuş'

    if not name:
        return redirect(url_for('index'))

    if name.lower() == 'anonim':
        index = 1
        roles = load_roles()
        while f'Anonim_{index}' in roles:
            index += 1
        name = f'Anonim_{index}'

    if upsert_user(name, password, role):
        add_log(f'🔐 {user} kullanıcısı için şifre ve rol güncellendi: {name}')
    else:
        # BUG FIX: Yeni kayıt şifresiz denendiyse hata mesajı bas
        add_log(f'⚠️ Başarısız işlem: Yeni hesaba ({name}) şifre girmedin aga!')

    return redirect(url_for('index'))


@app.route('/mesajlar')
def mesajlar_json():
    active_user = session.get('kus_adi')
    roles = load_roles()
    
    # Aga BUG FIX: Kullanıcı silindiyse AJAX'a kovulduğunu bildir
    if active_user and active_user not in roles:
        return jsonify({"kicked": True})
        
    cleanup_expired_mutes()
    return jsonify(
        mesajlar=[message for message in messages if message['ozel_alici'] is None or message['ozel_alici'] == active_user or message['gonderen'] == active_user],
        susturulanlar=list(muted_users),
        logs=logs,
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)