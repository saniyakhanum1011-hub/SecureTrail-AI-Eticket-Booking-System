import requests
API_KEY = "AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA"
email = "admin_new@securetrail.in"
password = "Admin@123"

def debug_login():
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    r = requests.post(url, json=payload)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))

if __name__ == "__main__":
    import json
    debug_login()
