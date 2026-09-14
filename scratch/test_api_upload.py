import json
import os
import urllib.request
import urllib.error
import uuid

def upload_test():
    filepath = 'backend/tests/fixtures/synthetic_label.jpg'
    boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
    body = []

    def add_field(name, val):
        body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode())

    def add_file(name, path):
        filename = os.path.basename(path)
        with open(path, 'rb') as f:
            content = f.read()
        header = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
        body.append(header + content + b'\r\n')

    add_field('officer_name', 'Inspector Sharma')
    add_field('lang', 'en')
    add_field('is_food_item', 'false')
    add_field('is_imported', 'false')
    add_field('skip_quality_gate', 'true')
    add_file('image', filepath)

    payload = b''.join(body) + f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request(
        'http://localhost:8080/api/v1/scans',
        data=payload,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print('Scan upload status:', resp.status)
            scan = data.get('scan', {})
            print('Scan ID:', scan.get('id'))
            print('OCR Provider Used:', scan.get('ocr_provider'))
            print('Verdict:', scan.get('verdict'))
            print('Declarations count:', len(scan.get('declarations', [])))
            print('Entity roles count:', len(scan.get('entity_roles', [])))
            print('Ledger sequence:', scan.get('ledger_entry', {}).get('sequence'))
            return scan.get('id')
    except urllib.error.HTTPError as exc:
        print('Upload failed HTTP', exc.code, exc.read().decode())
        return None

if __name__ == '__main__':
    upload_test()
