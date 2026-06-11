from flask import Flask, render_template, request, redirect, url_for, session
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "guvercin_gizli_anahtar_aga" # Session (oturum) için gerekli

# Hafıza Veri Tabanımız
kullanici_rolleri = {
    "Arda": "Taklacı Güvercin",
    "Admin": "Kurucu Güvercin"
}

# Mühendislik Notu: Giriş mesajlarını kaldırdık, liste boş başlıyor. Sadece en son konuşulanlar kalacak!
mesajlar = []
log_kayitlari = [] # Sadece Admin'in görebileceği giriş logları

@app.route('/')
def index():
    # Kullanıcı giriş yapmadıysa direkt giriş sayfasına fırlat aga
    if 'kullanici' not in session:
        return redirect(url_for('login'))
        
    return render_template('index.html', 
                           mesajlar=mesajlar, 
                           roller=kullanici_rolleri, 
                           aktif_user=session['kullanici'],
                           mevcut_rol=kullanici_rolleri.get(session['kullanici'], 'Yavru Kuş'),
                           logs=log_kayitlari)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        kullanici = request.form.get('kullanici_adi')
        if kullanici:
            session['kullanici'] = kullanici
            if kullanici not in kullanici_rolleri:
                kullanici_rolleri[kullanici] = "Yavru Kuş" # Yeni gelene varsayılan rol
                
            # Mühendislik Notu: Log kaydını zaman damgası (Timestamp) ile tutuyoruz
            zaman = datetime.now().strftime('%H:%M:%S')
            log_kayitlari.append(f"[{zaman}] 🕊️ {kullanici} sisteme kanat çırptı (Giriş yaptı).")
            
            return redirect(url_for('index'))
    return '''
        <style>
            body{ background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin:0;}
            .box{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 350px;}
            input{ width: 100%; padding: 12px; margin: 15px 0; border: 2px solid #e2e8f0; border-radius: 8px; box-sizing: border-box;}
            button{ background: #4b7bec; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer;}
        </style>
        <div class="box">
            <h2>🕊️ Güvercin.Net'e Giriş</h2>
            <form method="POST"><input type="text" name="kullanici_adi" placeholder="Kullanıcı Adınız" required><button type="submit">Uçuşu Başlat</button></form>
        </div>
    '''

@app.route('/logout')
def logout():
    session.pop('kullanici', None)
    return redirect(url_for('login'))

@app.route('/rol-ver', methods=['POST'])
def rol_ver():
    if session.get('kullanici') != 'Admin':
        return "Aga burası sadece Admin'e özel! .d", 403
        
    kullanici = request.form.get('kullanici_adi')
    yeni_rol = request.form.get('rol_adi')
    if kullanici and yeni_rol:
        kullanici_rolleri[kullanici] = yeni_rol
    return redirect(url_for('index'))

@app.route('/mesaj-gonder', methods=['POST'])
def mesaj_gonder():
    metin = request.form.get('mesaj')
    user = session.get('kullanici', 'Anonim')
    if metin:
        mesajlar.append({
            "gonderen": user,
            "rol": kullanici_rolleri.get(user, "Yavru Kuş"),
            "metin": metin,
            "tip": "outgoing" if user == session.get('kullanici') else "incoming"
        })
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)