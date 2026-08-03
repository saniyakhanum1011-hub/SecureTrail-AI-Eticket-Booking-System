import requests

FIREBASE_API_KEY = "AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA"

def create_user(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    r = requests.post(url, json=payload)
    print(f"Status: {r.status_code}")
    print(r.json())

if __name__ == "__main__":
    # Ensure admin user exists in Auth
    create_user("admin_new@securetrail.in", "Admin@123")
