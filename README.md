# SecureTrail — Smart Indian E-Ticket System

A complete full-stack React & Flask web application for AI-powered ticket booking and fraud detection, built entirely from scratch.

## Project Structure
```text
cont_project/
├── backend/
│   ├── app.py                   # Main Flask API, Firebase integration, ML inference
│   └── requirements.txt         # Python dependencies
├── frontend/
│   └── index.html               # React 18 SPA (Zero-build, served by Flask)
├── ml/
│   ├── generate_dataset.py      # Synthetic data generator (10,000 tickets, Faker)
│   ├── train_model.py           # Logistic Regression + Decision Tree training script
│   └── fraud_model.pkl          # Saved after training
├── database.db                  # (Not used - Switched to Firebase)
├── start.bat                    # Windows startup script
└── README.md
```

## Setup & Running
**Prerequisites**: Python 3.8+ installed on your system.

### One-Click Startup (Windows)
Double-click `start.bat`. This will:
1. Install dependencies from `backend\requirements.txt`
2. Generate the 10,000-row synthetic dataset (`ml\data\train_tickets.csv`)
3. Train the AI fraud models (`ml\train_model.py`)
4. Build the frontend components into `frontend\index.html`
5. Start the Flask server on `http://localhost:5000`

### Firebase Database Note
The app comes pre-configured with a Firebase project to meet the requirements of the prompt (`trail-45113`).
It is ready to use immediately without any extra setup. 

## Features
*   **Modern UI**: Dark glassmorphism React SPA built without Webpack/Node overhead.
*   **Realistic Indian Routes**: 30 cities and 50+ inter-city routes with distance-based pricing.
*   **Full Booking Flow**: Form details -> Price calculation -> Fake Payment -> Real OTP verification -> Ticket generation (with QR code).
*   **Dual Fraud Detection**:
    *   **Booking-Time ML Check**: Analyzes user behavior and returns a 0-100 score + risk level.
    *   **Image Scanning**: Upload tickets (Pro & Batch mode available) to scan via OpenCV (QR matching, edge density, OCR checks) and get a comprehensive analysis report.
*   **Admin Dashboard**: View platform stats, charts (Chart.js), and manually retrain the model based on user feedback (False Positives).

## Accounts
*   **Admin Access**: Sign in with an account that has `role: "admin"` in the Firestore `users` collection to see the Admin tab. A default admin user can be created manually in your firebase console or you can sign up normally and change your role in the DB.
