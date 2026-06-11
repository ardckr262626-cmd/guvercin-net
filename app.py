from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Mühendislik Notu: Gerçek bir DB yerine şimdilik verileri bu Python listelerinde tutuyoruz.
# Sayfa yenilense de mesajlar uçup gitmez, ama sunucu kapanırsa sıfırlanır. .d
kullanici_rolleri = {
    "Arda": "Taklacı Güvercin",
    "Sen": "Kurucu Güvercin"
}

mesajlar = [
    {"gonderen": "Arda", "rol": "Taklacı Güvercin", "metin": "Aga selam, sistem tam fonksiyonel oldu mu? .d", "tip": "incoming"},
    {"gonderen": "Sen", "rol": "Kurucu Güvercin", "metin": "Oldu aga, Python motoru arkada cayır cayır çalışıyor! :D", "tip": "outgoing"}
]

@app.route('/')
def index():
    # Sayfa her yüklendiğinde güncel mesajları ve rolleri HTML'e gönderiyoruz
    return render_template('index.html', mesajlar=mesajlar, roller=kullanici_rolleri)

@app.route('/rol-ver', methods=['POST'])
def rol_ver():
    kullanici = request.form.get('kullanici_adi')
    yeni_rol = request.form.get('rol_adi')
    
    if kullanici and yeni_rol:
        kullanici_rolleri[kullanici] = yeni_rol # Rolü sözlüğe kaydet/güncelle
        
    return redirect(url_for('index'))

@app.route('/mesaj-gonder', methods=['POST'])
def mesaj_gonder():
    metin = request.form.get('mesaj')
    # Simülasyon gereği mesajı hep "Sen (Admin)" olarak gönderiyoruz
    if metin:
        mesajlar.append({
            "gonderen": "Sen",
            "rol": kullanici_rolleri.get("Sen", "Kurucu Güvercin"),
            "metin": metin,
            "tip": "outgoing"
        })
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)