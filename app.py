import os
import time
import threading
from datetime import datetime

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from supabase import create_client

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
muted_users = set()
slowmode_seconds = 0
last_message_times = {}

def load_roles():
    try:
        response = supabase.table("kuslar").select("id, isim, sifre, rol").execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase yükleme hatası: {response.error}")
            return {}
        return {item['isim']: {'sifre': item['sifre'], 'rol': item['rol']} for item in response.data or []}
    except Exception as e:
        print(f"Supabase kuş verisi çekilirken hata oluştu: {e}")
        return {}


def get_user_data(username):
    try:
        response = supabase.table("kuslar").select("id, isim, sifre, rol").eq("isim", username).single().execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase kullanıcı verisi hatası: {response.error}")
            return None
        return response.data
    except Exception as e:
        print(f"Supabase kullanıcı çekilirken hata oluştu: {e}")
        return None


def upsert_user(name, password, role):
    try:
        response = supabase.table("kuslar").upsert({
            "isim": name,
            "sifre": password,
            "rol": role,
        }).execute()
        if hasattr(response, "error") and response.error:
            print(f"Supabase kullanıcı kaydetme hatası ({name}): {response.error}")
            return False
        return True
    except Exception as e:
        print(f"Supabase kullanıcı kaydetme hatası: {e}")
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


def get_user_role(username):
    user = get_user_data(username)
    return user['rol'] if user else 'Yavru Kuş'


def is_kurucu(username):
    return get_user_role(username) == 'Kurucu Güvercin'


def is_admin(username):
    return get_user_role(username) in {'Kurucu Güvercin', 'Yan Admin'}


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

    if not active_user or active_user not in roles:
        session.pop('kus_adi', None)
        return redirect(url_for('login'))

    return render_template(
        'index.html',
        mesajlar=messages,
        kuslar=roles,
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
        print(f"DEBUG: Veritabanından gelen veri -> {user}")

        if user and user.get('sifre') == password:
            session['kus_adi'] = name
            add_log(f'🕊️ {name} kuşu doğru şifreyle kafese süzüldü.')
            return redirect(url_for('index'))
        
        error = 'Giriş başarısız. Kullanıcı adı veya şifre hatalı.'
        
    return render_template('login.html', hata=error)


@app.route('/logout')
def logout():
    session.pop('kus_adi', None)
    return redirect(url_for('login'))


@app.route('/mesaj-gonder', methods=['POST'])
def mesaj_gonder():
    global slowmode_seconds
    text = request.form.get('mesaj', '').strip()
    user = session.get('kus_adi')

    if not user or not text:
        return redirect(url_for('index'))

    roles = load_roles()
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
                muted_users.add(target)
                add_message('SİSTEM', '🛡️ Otomasyon', f'🔇 {target} kuşu {user} tarafından susturuldu!')
                add_log(f'🔇 {target}, {user} tarafından susturuldu.')
            return redirect(url_for('index'))

        if command == '/unmute' and len(parts) > 1:
            target = parts[1]
            muted_users.discard(target)
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

    if user in muted_users:
        return redirect(url_for('index'))

    if role != 'Kurucu Güvercin' and slowmode_seconds > 0:
        now = time.time()
        last = last_message_times.get(user, 0)
        if now - last < slowmode_seconds:
            return redirect(url_for('index'))
        last_message_times[user] = now

    add_message(user, role, text)
    return redirect(url_for('index'))


@app.route('/sifre-ve-rol-ver', methods=['POST'])
def sifre_ve_rol_ver():
    user = session.get('kus_adi')
    if not is_kurucu(user):
        return abort(403, 'Şifre yönetimi sadece Kurucu Güvercin içindir.')

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

    if password:
        password_value = password
    else:
        password_value = ''

    if upsert_user(name, password_value, role):
        add_log(f'🔐 {user} kullanıcısı için şifre ve rol güncellendi: {name}')
    else:
        print(f"Kullanıcı güncelleme başarısız oldu: {name}")

    return redirect(url_for('index'))


@app.route('/kus-sil/<string:kus_adi>', methods=['POST'])
def kus_sil(kus_adi):
    user = session.get('kus_adi')
    if not is_kurucu(user):
        return abort(403, 'Sadece Kurucu Güvercin kuş silebilir.')

    if kus_adi != 'Kurucu':
        if delete_user(kus_adi):
            add_log(f'❌ {kus_adi} yuvadan atıldı.')
        else:
            print(f"Kuş silme işlemi başarısız oldu: {kus_adi}")
    return redirect(url_for('index'))


@app.route('/mesajlar')
def mesajlar_json():
    active_user = session.get('kus_adi')
    return jsonify(
        mesajlar=[message for message in messages if message['ozel_alici'] is None or message['ozel_alici'] == active_user or message['gonderen'] == active_user],
        susturulanlar=list(muted_users),
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
