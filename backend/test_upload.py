import requests

with open('dummy.pdf', 'wb') as f:
    f.write(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n')

try:
    with open('dummy.pdf', 'rb') as f:
        print("Uploading...")
        response = requests.post(
            'http://127.0.0.1:8001/documents/upload',
            files={'file': ('dummy.pdf', f, 'application/pdf')}
        )
        print("Status code:", response.status_code)
        print("Response text:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
