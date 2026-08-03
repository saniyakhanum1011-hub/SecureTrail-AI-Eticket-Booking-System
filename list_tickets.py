import requests, json

FIREBASE_API_KEY    = "AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA"
FIREBASE_PROJECT_ID = "trail-45113"
FS_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

def list_tickets():
    r = requests.get(f"{FS_BASE}/tickets?key={FIREBASE_API_KEY}&pageSize=5")
    if r.status_code == 200:
        docs = r.json().get("documents", [])
        for doc in docs:
            fields = doc.get("fields", {})
            pnr = fields.get("pnr", {}).get("stringValue", "N/A")
            status = fields.get("status", {}).get("stringValue", "N/A")
            mode = fields.get("mode", {}).get("stringValue", "N/A")
            print(f"PNR: {pnr} | Status: {status} | Mode: {mode}")
    else:
        print(f"Error: {r.json()}")

if __name__ == "__main__":
    list_tickets()
