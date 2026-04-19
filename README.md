# TarFixer

An Integrated System for Real-Time Road Damage Detection and Classification using YOLOv11 with Automated Authority Reporting.

**Live Application:** https://tar-fixer.vercel.app/

**Backend API:** https://huggingface.co/spaces/Jeeva5655/tarfixer-backend

## Overview

TarFixer is a deep learning-based system designed to detect and categorize road surface defects such as potholes, cracks, and erosion from uploaded images. Citizens capture road damage using a smartphone camera and submit images through a web interface. The system processes each image through a YOLOv11 model fine-tuned on the RDD2022 dataset, detecting damaged regions and calculating a severity percentage for each area.

When damage severity exceeds a 60% threshold, the system classifies it as a severe road condition and automatically generates a GeoJSON report containing the GPS coordinates extracted from the image metadata. This report is transmitted to road authorities through an integrated Officer Dashboard, enabling proactive maintenance and safer infrastructure.

## Key Features

- **Real-Time Detection** -- YOLOv11-based object detection achieving 32 FPS inference speed for instant damage classification.
- **Severity Estimation** -- Calculates damage severity as a percentage based on model confidence scores and the ratio of damaged pixel area to total image area.
- **Automated Authority Reporting** -- Triggers automatic report generation when severity exceeds the 60% threshold, reducing manual intervention.
- **Geospatial Mapping** -- Extracts GPS metadata directly from uploaded image EXIF data and formats locations into standardized GeoJSON reports.
- **Officer Dashboard** -- A centralized web portal for road authorities to view, track, manage, and prioritize reported road conditions.
- **Worker Dashboard** -- Interface for field workers to view assigned repair tasks and update completion status.
- **User Portal** -- Public-facing portal for citizens to upload road images and track their submitted reports.
- **Authentication System** -- Firebase-based authentication with email verification, role-based access control (citizen, officer, worker), and Google Sign-In.
- **Cross-Platform Support** -- Flutter mobile application in addition to the responsive web interface.

## System Architecture

TarFixer is composed of four main modules:

```
                      +-------------------+
                      |   User (Mobile/   |
                      |   Web Browser)    |
                      +--------+----------+
                               |
                   Upload Image + GPS Data
                               |
                      +--------v----------+
                      |  Frontend (Vercel)|
                      |  - User Portal    |
                      |  - Officer Dash   |
                      |  - Worker Dash    |
                      +--------+----------+
                               |
                         REST API Calls
                               |
              +----------------v-----------------+
              |  Backend (Hugging Face Spaces)   |
              |  - Flask API Server              |
              |  - YOLOv11 Inference Engine       |
              |  - Severity Calculator            |
              |  - GeoJSON Report Generator       |
              +----------------+-----------------+
                               |
                    Firebase (Auth + Firestore)
                               |
              +----------------v-----------------+
              |  Database and Reporting          |
              |  - Report Storage                |
              |  - User Management               |
              |  - Role-Based Access              |
              +----------------------------------+
```

### Module Breakdown

1. **Frontend Interface** -- A responsive, mobile-friendly web portal deployed on Vercel. Three role-based dashboards (User, Officer, Worker) provide tailored views for each stakeholder.

2. **Backend Processing** -- A Python Flask API server hosted on Hugging Face Spaces. Handles image upload, preprocessing, YOLOv11 inference, severity calculation, and annotated image generation.

3. **AI Service** -- Standalone Dockerized service for model inference, designed for independent scaling and deployment on Hugging Face Spaces or Render.

4. **Database and Reporting** -- Firebase Firestore for storing reports, user data, and authentication state. Reports include severity scores, GPS coordinates, timestamps, and annotated images.

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| Deep Learning | PyTorch, Ultralytics YOLOv11 |
| Backend API | Python 3.8+, Flask, Flask-CORS, Gunicorn |
| Frontend | HTML, CSS, JavaScript |
| Mobile | Flutter, Dart |
| Authentication | Firebase Auth (Email + Google Sign-In) |
| Database | Firebase Firestore |
| Image Processing | OpenCV, Pillow, NumPy |
| Geospatial | GeoJSON, EXIF metadata extraction |
| Deployment | Vercel (frontend), Hugging Face Spaces (backend), Render (alternative), Docker |
| SEO | robots.txt, sitemap.xml, Google Search Console verification |

## Model Performance

| Metric | Value |
| :--- | :--- |
| Dataset | RDD2022 (47,420+ globally-sourced road images) |
| Architecture | YOLOv11 (fine-tuned) |
| F1-Score | ~81% |
| Mean Average Precision (mAP) | Competitive against multi-national benchmarks |
| Inference Speed | 32 FPS |
| Severity Threshold | 60% (auto-reporting trigger) |

## Project Structure

```
TarFixer/
|-- index.html                  # Landing page
|-- auth.js                     # Authentication logic
|-- firebase-config.js          # Firebase configuration
|-- api-client.js               # API client for backend communication
|-- api-client-v2.js            # Updated API client
|-- Dashboard/
|   |-- Officer.HTML            # Officer dashboard portal
|   |-- User.HTML               # Citizen reporting portal
|   |-- Worker.HTML             # Field worker task portal
|-- Login/                      # Login and registration pages
|-- backend/
|   |-- app.py                  # Flask API entry point
|   |-- server.py               # Full server with all routes
|   |-- predictor.py            # YOLOv11 inference and severity logic
|   |-- run.py                  # Server runner with configuration
|   |-- model/                  # Trained model weights
|   |-- predictions/            # Saved prediction outputs
|   |-- uploads/                # Uploaded image storage
|-- ai-service/
|   |-- app.py                  # Standalone AI inference service
|   |-- Dockerfile              # Docker configuration for deployment
|   |-- requirements.txt        # AI service dependencies
|-- Scripts/                    # Utility scripts
|-- flutter/                    # Flutter mobile application source
|-- runs/detect/                # YOLO training run outputs
|-- Dockerfile                  # Root Docker configuration
|-- Procfile                    # Process file for Render deployment
|-- render.yaml                 # Render deployment configuration
|-- render-build.sh             # Render build script
|-- requirements.txt            # Python dependencies
|-- robots.txt                  # SEO robots configuration
|-- sitemap.xml                 # SEO sitemap
```

## How It Works

1. A citizen opens the web application and captures or uploads a photo of road damage.
2. The image is sent to the Flask API backend via a REST endpoint.
3. The backend loads the image, runs YOLOv11 inference, and detects all damaged regions with bounding boxes.
4. For each detection, the system calculates damage severity as the ratio of damaged pixel area to total image area.
5. If severity exceeds 60%, the system extracts GPS coordinates from the image EXIF metadata and generates a GeoJSON report.
6. The annotated image (with bounding boxes drawn) and severity data are returned to the frontend.
7. Reports with severity above the threshold are automatically pushed to the Officer Dashboard.
8. Officers can review, prioritize, and assign repair tasks to field workers through the Worker Dashboard.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Node.js (for frontend development, optional)
- A Firebase project with Authentication and Firestore enabled
- YOLO model weights (trained on RDD2022 or custom dataset)

### Local Setup

1. Clone the repository:
   ```
   git clone https://github.com/jeeva5655/TarFixer.git
   cd TarFixer
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure Firebase:
   - Create a Firebase project at https://console.firebase.google.com
   - Enable Email/Google authentication
   - Create a Firestore database
   - Update `firebase-config.js` with your project credentials

4. Place your trained YOLO model weights in the `backend/model/` directory.

5. Start the backend server:
   ```
   cd backend
   python app.py
   ```

6. Open `index.html` in a browser or serve it with a local HTTP server.

For detailed setup instructions, see the [Quickstart Guide](QUICKSTART.md).

### Deployment

The system supports multiple deployment configurations:

- **Frontend:** Deploy to Vercel by connecting the repository and setting the root directory.
- **Backend:** Deploy to Hugging Face Spaces using the provided Dockerfile in `ai-service/`, or deploy to Render using `render.yaml`.
- **Docker:** Build and run using the root `Dockerfile` for containerized deployment.

For step-by-step deployment instructions, see:
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Deploy to Hugging Face](DEPLOY_TO_HF.md)
- [Deploy to Render](DEPLOY_TO_RENDER.md)

## Documentation

| Document | Description |
| :--- | :--- |
| [Quickstart Guide](QUICKSTART.md) | Step-by-step local setup |
| [Complete System Summary](COMPLETE_SYSTEM_SUMMARY.md) | Full architecture and design overview |
| [Deployment Guide](DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [Deploy to Hugging Face](DEPLOY_TO_HF.md) | Hugging Face Spaces deployment |
| [Deploy to Render](DEPLOY_TO_RENDER.md) | Render deployment |
| [Firebase Setup](FIREBASE_SETUP.md) | Firebase project configuration |
| [Login System Guide](LOGIN_SYSTEM_GUIDE.md) | Authentication system details |
| [Email Verification Setup](EMAIL_VERIFICATION_README.md) | Email verification configuration |
| [Security Tests](SECURITY_TESTS.md) | Security testing overview |
| [Advanced Security](ADVANCED_SECURITY.md) | Security hardening details |
| [Implementation Complete](IMPLEMENTATION_COMPLETE.md) | Implementation status and checklist |

## API Reference

### POST /detect

Accepts a road image and returns detection results.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `image` (file) -- JPEG or PNG image of road surface

**Response:**
```json
{
  "damage_percentage": "45.23",
  "detection_count": 3,
  "annotated_image": "data:image/jpeg;base64,..."
}
```

**Fields:**
- `damage_percentage` -- Percentage of the image area covered by detected damage.
- `detection_count` -- Number of damage regions detected.
- `annotated_image` -- Base64-encoded JPEG with bounding boxes drawn on detected regions.

## Contributors

- **Jeeva N** -- [GitHub](https://github.com/Jeeva5655) | [LinkedIn](https://linkedin.com/in/jeeva-n-37b255293) | [Portfolio](https://portfolio-green-theta-80.vercel.app/)
- **Siva S**

## License

This project is open source and available for educational and research purposes. The full source code and documentation related to the building, deployment, and testing of the Road Damage Detection model are included in this repository.
