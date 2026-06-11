from flask import Flask, render_template, request, redirect, url_for, session
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "guvercin_gizemli_kod_aga"

guvercin_veritabi = {
    "Kurucu": {"sifre": "mor_guvercinkanadi", "rol": "Kurucu Güvercin"},
    "Taklacı": {"sifre": "777", "rol": "Yavru Kuş"},
    "Postacı": {"sifre": "pigeon", "rol": "Haberci Kuş"},
    "Şebap": {"sifre": "sebo", "rol": "Süs Güvercini"}
}

mesajlar = []
log_kayitlari = []

@app.route('/')
def index():
    if 'kus_adi' not in session:
        return redirect(url_for('login'))
        
    aktif = session['kus_adi']
    if aktif not in guvercin_veritabi:
        session.pop('kus_adi', None)
        return redirect(url_for('login'))

    return render_template('index.html', 
                           mesajlar=mesajlar, 
                           kuslar=guvercin_veritabi, 
                           aktif_user=aktif,
                           mevcut_rol=guvercin_veritabi[aktif]['rol'],
                           logs=log_kayitlari)

# 📱 MÜHENDİSLİK NOTU: Giriş ekranı CSS'ine mobilde kutuyu büyütecek @media sorgusu eklendi!
@app.route('/login', methods=['GET', 'POST'])
def login():
    hata = None
    if request.method == 'POST':
        isim = request.form.get('kus_adi')
        sifre = request.form.get('sifre')
        
        if isim in guvercin_veritabi and guvercin_veritabi[isim]['sifre'] == sifre:
            session['kus_adi'] = isim
            zaman = datetime.now().strftime('%H:%M:%S')
            log_kayitlari.append(f"[{zaman}] 🕊️ {isim} kuşu doğru şifreyle kafese süzüldü.")
            return redirect(url_for('index'))
        else:
            hata = "Böyle bir kuş yok veya şifre hatalı aga! .d"
            
    return f'''
        <style>
            body{{ background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin:0;}}
            .box{{ background: white; padding: 40px 30px; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 380px; transition: all 0.3s ease;}}
            input{{ width: 100%; padding: 14px; margin: 12px 0; border: 2px solid #e2e8f0; border-radius: 8px; box-sizing: border-box; font-size: 15px; outline: none;}}
            input:focus{{ border-color: #4b7bec; }}
            button{{ background: #4b7bec; color: white; border: none; padding: 14px; width: 100%; border-radius: 8px; font-weight: bold; font-size: 15px; cursor: pointer; margin-top: 10px;}}
            .error{{ color: #ff4757; font-size: 14px; margin-bottom: 10px; font-weight: bold;}}
            
            /* Mobilde Giriş Kutusunu Orantılı Büyütme Alanı */
            @media (max-width: 480px) {{
                .box {{
                    width: 95%;
                    max-width: 95%;
                    padding: 40px 20px; /* İç boşlukları telefona göre optimize ettik */
                }}
                input, button {{
                    padding: 16px; /* Mobilde parmakla rahat basılsın diye input ve butonu büyüttük */
                    font-size: 16px;
                }}
            }}
        </style>
        <div class="box">
            <h2 style="margin-bottom: 15px; color: #2c3e50;">🕊️ Güvercin Kafesi</h2>
            {f'<div class="error">{{hata}}</div>' if hata else ''}
            <form method="POST">
                <input type="text" name="kus_adi" placeholder="Güvercin Adı (Örn: Kurucu)" required autocomplete="off">
                <input type="password" name="sifre" placeholder="Şifre" required>
                <button type="submit">Kanat Çırp</button>
            </form>
        </div>
    '''

@app.route('/logout')
def logout():
    session.pop('kus_adi', None)
    return redirect(url_for('login'))

@app.route('/sifre-ve-rol-ver', methods=['POST'])
def sifre_ve_rol_ver():
    if session.get('kus_adi') != 'Kurucu':
        return "Aga bu yetki sadece Kurucu Güvercin'e ait! .d", 403
        
    isim = request.form.get('kus_adi')
    yeni_sifre = request.form.get('sifre')
    yeni_rol = request.form.get('rol_adi')
    
    if isim:
        if isim not in guvercin_veritabi:
            guvercin_veritabi[isim] = {}
        if yeni_sifre:
            guvercin_veritabi[isim]['sifre'] = yeni_sifre
        if yeni_rol:
            guvercin_veritabi[isim]['rol'] = yeni_rol
            
        zaman = datetime.now().strftime('%H:%M:%S')
        log_kayitlari.append(f"[{zaman}] 👑 Kurucu, {isim} kuşunun bilgilerini güncelledi.")
        
    return redirect(url_for('index'))

@app.route('/kus-sil/<string:kus_adi>', methods=['POST'])
def kus_sil(kus_adi):
    if session.get('kus_adi') != 'Kurucu':
        return "Aga kuşu yuvadan sadece Kurucu atabilir! .d", 403
    
    if kus_adi == 'Kurucu':
        return "Aga kendi kendini yuvadan atamazsın! :D", 400

    if kus_adi in guvercin_veritabi:
        del guvercin_veritabi[kus_adi]
        zaman = datetime.now().strftime('%H:%M:%S')
        log_kayitlari.append(f"❌ {kus_adi} kuşu Kurucu tarafından sepetlendi.")
        
    return redirect(url_for('index'))

@app.route('/mesaj-gonder', methods=['POST'])
def mesaj_gonder():
    metin = request.form.get('mesaj')
    user = session.get('kus_adi', 'Yabancı Kuş')
    if metin:
        mesajlar.append({
            "gonderen": user,
            "rol": guvercin_veritabi.get(user, {}).get('rol', 'Yavru Kuş'),
            "metin": metin
        })
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)