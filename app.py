from flask import Flask, render_template, request, redirect, url_for, session
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "guvercin_gizemli_kod_aga"

# Şifre düz metin, takılma riski sıfırlandı aga!
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
            .box{{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 350px;}}
            input{{ width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #e2e8f0; border-radius: 8px; box-sizing: border-box;}}
            button{{ background: #4b7bec; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 10px;}}
            .error{{ color: #ff4757; font-size: 13px; margin-bottom: 10px; }}
        </style>
        <div class="box">
            <h2>🕊️ Güvercin Kafesi Giriş</h2>
            {f'<div class="error">{{hata}}</div>' if hata else ''}
            <form method="POST">
                <input type="text" name="kus_adi" placeholder="Güvercin Adı (Örn: Kurucu)" required>
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
    
    # Mühendislik Notu: Hatalı olan isset kaldırıldı, Python tarzı kontrol getirildi!
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