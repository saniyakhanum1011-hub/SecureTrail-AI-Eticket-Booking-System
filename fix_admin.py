import requests, json

FIREBASE_API_KEY    = "AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA"
FIREBASE_PROJECT_ID = "trail-45113"
FS_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

def fs_query_email(email):
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "users"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "email"},
                    "op": "EQUAL",
                    "value": {"stringValue": email}
                }
            }
        }
    }
    r = requests.post(f"{FS_BASE}:runQuery?key={FIREBASE_API_KEY}", json=query)
    if r.status_code == 200:
        results = r.json()
        if results and "document" in results[0]:
            doc = results[0]["document"]
            doc_id = doc["name"].split("/")[-1]
            return doc_id
    return None

def fs_set_admin(doc_id):
    # We only want to update the role field. 
    # REST API Patch with updateMask is cleaner but let's just get the doc first.
    r = requests.get(f"{FS_BASE}/users/{doc_id}?key={FIREBASE_API_KEY}")
    if r.status_code == 200:
        doc = r.json()
        fields = doc["fields"]
        fields["role"] = {"stringValue": "admin"}
        
        upd = requests.patch(f"{FS_BASE}/users/{doc_id}?key={FIREBASE_API_KEY}", json={"fields": fields})
        if upd.status_code == 200:
            print(f"Successfully promoted {doc_id} to admin.")
            return True
    return False

if __name__ == "__main__":
    email = "admin@securetrail.in"
    did = fs_query_email(email)
    if did:
        print(f"Found user {email} with ID: {did}")
        fs_set_admin(did)
    else:
        print(f"User {email} not found in Firestore.")
