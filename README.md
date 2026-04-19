# TarFixer: Real-Time Road Damage Detection and Classification System

**An Integrated System for Real-Time Road Damage Detection and Classification using YOLOv11 with Automated Authority Reporting**

## Live Demos & Links
- **Live Web Application:** [TarFixer on Vercel](https://tar-fixer.vercel.app/)
- **Hugging Face Backend (API):** [TarFixer HF Space](https://huggingface.co/spaces/Jeeva5655/tarfixer-backend)

## Overview
TarFixer is a deep learning-based system designed to detect and categorize road surface defects, such as potholes, cracks, and erosion. It allows users to capture images of roads using a smartphone camera and upload these captured images through a web interface. These images are processed by a YOLOv11 model that detects the damaged regions and calculates the severity percentage in each detected area. 

If the detected damage severity exceeds a 60% threshold, the system classifies it as a "Severe Road Condition" and automatically generates a report containing the latitude and longitude of the damaged location in GeoJSON format. This report is securely transmitted to the respective road authorities through an integrated officer portal (Officer Dashboard), ensuring proactive maintenance and safe road infrastructure.

## Key Features
- **Real-Time Detection:** Utilizes YOLOv11 to execute fast and efficient object detection, achieving an inference speed of 32 FPS.
- **Severity Estimation:** Calculates damage severity percentage based on model confidence and bounding-box density.
- **Automated Authority Reporting:** Triggers automatic report generation for severity levels >60%.
- **Geospatial Mapping:** Extracts GPS metadata directly from uploaded images and formats locations into standardized GeoJSON reports.
- **Officer Dashboard:** A centralized visualization web portal for authorities to seamlessly track, manage, and prioritize severe road conditions.
- **Robust Precision:** Achieves an F1-score of ~81% on the RDD2022 dataset, verifying its strong generalization across varying environments.

## System Architecture
TarFixer comprises multiple cohesive modules:
1. **Frontend Interface:** A web-based mobile-friendly portal allowing citizens to snapshot & upload road damages seamlessly.
2. **Backend Processing:** Python-Flask server that runs image preprocessing, applies YOLOv11 inference logic, and compiles coordinates onto maps.
3. **Database & Reporting Unit:** Organizes image locations & severity scores, pushing alerts securely to the Officer Dashboard.

## Technology Stack
- **Deep Learning Framework:** PyTorch / TensorFlow (running the YOLOv11 Architecture)
- **Backend:** Python 3.8+, Flask API
- **Frontend:** HTML, CSS, JavaScript
- **Database:** Firebase / MySQL
- **Spatial Data:** GeoJSON, Shapely
- **Vision Processing:** OpenCV

## Performance & Results
- **Dataset:** Fine-tuned on the RDD2022 globally-sourced dataset (over 47,420 images).
- **Speed:** 32 FPS real-time processing ability.
- **Accuracy:** ~81% F1-score with impressive Mean Average Precision (mAP) against multi-national benchmarks.

## Documentation Links
For detailed setup instructions, deployment guides, and security overviews, please refer to the following documentation files included in this repository:
- [Quickstart Guide](QUICKSTART.md)
- [Complete System Summary](COMPLETE_SYSTEM_SUMMARY.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Deploy to Render](DEPLOY_TO_RENDER.md)
- [Deploy to Hugging Face](DEPLOY_TO_HF.md)
- [Firebase Setup](FIREBASE_SETUP.md)
- [Login System Guide](LOGIN_SYSTEM_GUIDE.md)
- [Email Verification Setup](EMAIL_VERIFICATION_README.md)
- [Security Tests & Overview](SECURITY_TESTS.md)
- [Advanced Security](ADVANCED_SECURITY.md)
- [Implementation Complete](IMPLEMENTATION_COMPLETE.md)

## Contributors
Developed by:
* **Jeeva N**
* **Siva S**

---
*This repository contains the full source code and documentation related to the building, deployment, and testing of the Road Damage Detection model.*
