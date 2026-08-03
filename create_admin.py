import requests, json

FIREBASE_API_KEY    = "AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA"
FIREBASE_PROJECT_ID = "trail-45113"
FS_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

def create_auth_user(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    r = requests.post(url, json=payload)
    if r.status_code == 200:
        return r.json()["localId"]
    else:
        print(f"Auth Error: {r.json()}")
        return None

def create_fs_user(uid, email, name, role):
    url = f"{FS_BASE}/users/{uid}?key={FIREBASE_API_KEY}"
    payload = {
        "fields": {
            "email": {"stringValue": email},
            "name": {"stringValue": name},
            "role": {"stringValue": role},
            "created_at": {"stringValue": "2026-05-01T12:00:00Z"},
            "login_count": {"integerValue": "0"}
        }
    }
    r = requests.patch(url, json=payload)
    if r.status_code == 200:
        print(f"Successfully created Firestore user for {email}")
        return True
    else:
        print(f"Firestore Error: {r.json()}")
        return False

if __name__ == "__main__":
    email = "admin_new@securetrail.in"
    password = "Admin@123"
    uid = create_auth_user(email, password)
    if uid:
        print(f"Created Auth user with UID: {uid}")
        create_fs_user(uid, email, "System Admin", "admin")
    else:
        # Maybe it already exists? Try to find UID if possible? 
        # But we don't have admin SDK. 
        # Let's just try another email if this one fails.
        pass
