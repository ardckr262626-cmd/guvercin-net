from flask import Flask, render_template, request, redirect, url_for, session
import os
from datetime import datetime
import time

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

susturulan_kuslar = set()  
slowmode_suresi = 0        
son_mesaj_zamanlari = {}   

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
                           logs=log_kayitlari,
                           susturulanlar=susturulan_kuslar,
                           slowmode=slowmode_suresi)

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
            
    return render_template('login.html', hata=hata)

@app.route('/logout')
def logout():
    session.pop('kus_adi', None)
    return redirect(url_for('login'))

@app.route('/mesaj-gonder', methods=['POST'])
def mesaj_gonder():
    global slowmode_suresi, mesajlar, log_kayitlari
    
    metin = request.form.get('mesaj', '').strip()
    user = session.get('kus_adi', 'Yabancı Kuş')
    
    if not metin:
        return redirect(url_for('index'))

    # ⚙️ MÜHENDİSLİK NOTU: Yetkili Rol Tanımlamaları
    user_rol = guvercin_veritabi.get(user, {}).get('rol', 'Yavru Kuş')
    komut_yetkili_roller = ["Kurucu Güvercin", "Yan Admin"]

    # 🛠️ GELİŞMİŞ KOMUT KONTROL SİSTEMİ
    if metin.startswith('/') and user_rol in komut_yetkili_roller:
        parcalar = metin.split(' ')
        komut = parcalar[0].lower()
        zaman = datetime.now().strftime('%H:%M:%S')

        # 1. /clear (Kurucu ve Yan Admin Yapabilir)
        if komut == '/clear':
            mesajlar = []
            mesajlar.append({"gonderen": "SİSTEM", "rol": "🛡️ Otomasyon", "metin": f"🧹 Kafes {user} tarafından tamamen süpürüldü!", "ozel_alici": None})
            log_kayitlari.append(f"[{zaman}] 🧹 {user} chat geçmişini temizledi.")
            return redirect(url_for('index'))

        # 2. /mute [KuşAdı] (Kurucu ve Yan Admin Yapabilir)
        elif komut == '/mute':
            if len(parcalar) > 1:
                hedef = parcalar[1]
                if guvercin_veritabi.get(hedef, {}).get('rol') == "Kurucu Güvercin":
                    return redirect(url_for('index')) # Kurucu susturulamaz aga! .d
                susturulan_kuslar.add(hedef)
                mesajlar.append({"gonderen": "SİSTEM", "rol": "🛡️ Otomasyon", "metin": f"🔇 {hedef} kuşu {user} tarafından susturuldu!", "ozel_alici": None})
                log_kayitlari.append(f"[{zaman}] 🔇 {hedef}, {user} tarafından susturuldu.")
            return redirect(url_for('index'))

        # 3. /unmute [KuşAdı] (Kurucu ve Yan Admin Yapabilir)
        elif komut == '/unmute':
            if len(parcalar) > 1:
                hedef = parcalar[1]
                susturulan_kuslar.discard(hedef)
                mesajlar.append({"gonderen": "SİSTEM", "rol": "🛡️ Otomasyon", "metin": f"🔊 {hedef} kuşunun cezası {user} tarafından kaldırıldı!", "ozel_alici": None})
                log_kayitlari.append(f"[{zaman}] 🔊 {hedef} cezası {user} tarafından kaldırıldı.")
            return redirect(url_for('index'))

        # 4. /slowmode [Saniye] (Sadece SÜPER YETKİ - Kurucu Güvercin)
        elif komut == '/slowmode' and user_rol == "Kurucu Güvercin":
            try:
                saniye = int(parcalar[1]) if len(parcalar) > 1 else 0
                slowmode_suresi = saniye
                if saniye > 0:
                    mesajlar.append({"gonderen": "SİSTEM", "rol": "🛡️ Otomasyon", "metin": f"⏳ Yavaş mod aktif! Kuşlar {saniye} saniyede bir yazabilir.", "ozel_alici": None})
                else:
                    mesajlar.append({"gonderen": "SİSTEM", "rol": "🛡️ Otomasyon", "metin": "⚡ Yavaş mod kaldırıldı.", "ozel_alici": None})
            except ValueError:
                pass
            return redirect(url_for('index'))

        # 5. /system [Mesaj] (Sadece SÜPER YETKİ - Kurucu Güvercin)
        elif komut == '/system' and user_rol == "Kurucu Güvercin":
            duyuru_metni = " ".join(parcalar[1:])
            if duyuru_metni:
                mesajlar.append({"gonderen": "📢 DUYURU", "rol": "👑 Kurucu Özel", "metin": f"🚨 {duyuru_metni} 🚨", "ozel_alici": None})
            return redirect(url_for('index'))

    # 🔒 /msg [KuşAdı] [Mesaj] - GİZLİ MESAJ SİSTEMİ (Herkes Kullanabilir)
    if metin.startswith('/msg'):
        parcalar = metin.split(' ')
        if len(parcalar) > 2:
            hedef_alici = parcalar[1]
            ozel_mesaj = " ".join(parcalar[2:])
            mesajlar.append({
                "gonderen": user,
                "rol": user_rol,
                "metin": f"🤫 (Fısıldama): {ozel_mesaj}",
                "ozel_alici": hedef_alici
            })
        return redirect(url_for('index'))

    # 🛑 SUSTURULMA KONTROLÜ
    if user in susturulan_kuslar:
        return redirect(url_for('index'))
        
    # SLOWMODE KONTROLÜ
    if user_rol != 'Kurucu Güvercin' and slowmode_suresi > 0:
        simdi = time.time()
        son_atilan = son_mesaj_zamanlari.get(user, 0)
        if simdi - son_atilan < slowmode_suresi:
            return redirect(url_for('index'))
        son_mesaj_zamanlari[user] = simdi

    mesajlar.append({
        "gonderen": user,
        "rol": user_rol,
        "metin": metin,
        "ozel_alici": None
    })
    return redirect(url_for('index'))

@app.route('/sifre-ve-rol-ver', methods=['POST'])
def sifre_ve_rol_ver():
    # Güvenlik Duvarı: Sadece Kurucu Güvercin şifre/rol atayabilir!
    aktif_user = session.get('kus_adi','')
    if guvercin_veritabi.get(aktif_user, {}).get('rol') != 'Kurucu Güvercin':
        return "Aga şifre yönetimi sadece Kurucu Güvercin'e aittir!", 403
        
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
    return redirect(url_for('index'))

@app.route('/kus-sil/<string:kus_adi>', methods=['POST'])
def kus_sil(kus_adi):
    # Güvenlik Duvarı: Sadece Kurucu Güvercin kuş silebilir!
    aktif_user = session.get('kus_adi','')
    if guvercin_veritabi.get(aktif_user, {}).get('rol') != 'Kurucu Güvercin':
        return "Aga kuşu yuvadan sadece Kurucu Güvercin atabilir!", 403
        
    if kus_adi in guvercin_veritabi and kus_adi != 'Kurucu':
        del guvercin_veritabi[kus_adi]
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)