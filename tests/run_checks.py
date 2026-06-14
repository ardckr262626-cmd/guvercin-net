import time
import sys
import os
from unittest.mock import patch

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

import app

flask_app = app.app

with flask_app.test_client() as client:
    # Mock DB lookups so no external Supabase call is needed
    with patch('app.load_roles', return_value={'Arda': {'rol': 'Yavru Kuş'}, 'Kurucu': {'rol': 'Kurucu Güvercin'}}), \
         patch('app.get_user_data', return_value={'id': 1, 'isim': 'Arda', 'sifre': 'hash', 'rol': 'Yavru Kuş'}), \
         patch('app.verify_password', return_value=True):

        # Login (sets session)
        r = client.post('/login', data={'kus_adi': 'Arda', 'sifre': 'x'}, follow_redirects=True)
        print('login status', r.status_code)

        # First send should be accepted
        r1 = client.post('/mesaj-gonder', data={'mesaj': 'Merhaba'}, follow_redirects=True)
        print('first send status', r1.status_code)

        # Rapidly send same message 5 times
        results = []
        for i in range(5):
            r = client.post('/mesaj-gonder', data={'mesaj': 'Merhaba'}, follow_redirects=True)
            results.append(r.status_code)
            time.sleep(0.2)  # short delay between attempts
        print('repeat statuses:', results)

        print('messages stored count:', len(app.messages))
        print('recent_messages entry for Arda:', app.recent_messages.get('Arda'))

        # Now simulate Kurucu kicking Arda by making load_roles not include Arda
        with patch('app.load_roles', return_value={'Kurucu': {'rol': 'Kurucu Güvercin'}}):
            r = client.get('/mesajlar')
            print('/mesajlar after kick response json:', r.get_json())

print('Test script finished')
