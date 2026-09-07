import io
from PIL import Image

def test_client_logo_upload_is_validated_and_saved(client):
    active=client.get('/api/clients').json()['active']
    image=Image.new('RGB',(32,32),(10,20,30)); raw=io.BytesIO(); image.save(raw,'PNG')
    response=client.post(f"/api/clients/{active['client_id']}/logo",files={'logo':('brand.png',raw.getvalue(),'image/png')})
    assert response.status_code==200, response.text
    assert response.json()['logo_path'].endswith('.png')
    bad=client.post(f"/api/clients/{active['client_id']}/logo",files={'logo':('bad.txt',b'not image','text/plain')})
    assert bad.status_code==400
