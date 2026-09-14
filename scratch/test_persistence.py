import json
import urllib.request

scan_id = '15197732e3b94aa295317fc964004fc7'

print('=== GET /api/v1/scans/{id} ===')
with urllib.request.urlopen(f'http://localhost:8080/api/v1/scans/{scan_id}') as resp:
    data = json.loads(resp.read().decode())
    print('Scan ID:', data['id'])
    print('Officer:', data['officer_name'])
    print('OCR Provider:', data['ocr_provider'])
    print('OCR Mode:', data.get('ocr_mode'))
    print('Verdict:', data['verdict'])
    print('Declarations:')
    for d in data.get('declarations', []):
        print(f"  Field: {d['field']}, Value: {d['value']}, Present: {d['present']}")
    print('Ledger Entry Sequence:', data.get('ledger_entry', {}).get('sequence'))
    print('Payload Hash:', data.get('ledger_entry', {}).get('payload_hash'))

print('\n=== GET /api/v1/ledger/verify ===')
with urllib.request.urlopen('http://localhost:8080/api/v1/ledger/verify') as resp:
    vdata = json.loads(resp.read().decode())
    print('Chain Valid:', vdata['valid'])
    print('Checked Entries:', vdata['checked_entries'])
    print('Detail:', vdata['detail'])
