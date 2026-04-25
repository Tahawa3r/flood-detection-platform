# Flood Detection & Risk Platform

A satellite-based flood detection system using Sentinel-1 radar imagery and U-Net deep learning models for real-time flood monitoring and risk assessment.

## 🌟 Features

- **Real-time Flood Detection**: Uses Sentinel-1 satellite imagery for accurate flood mapping
- **Deep Learning Models**: U-Net architecture for semantic segmentation of flood areas
- **Interactive Map Interface**: Leaflet-based map with drawing tools for region selection
- **Google Earth Engine Integration**: Automated data acquisition and processing
- **Google Drive Sync**: Seamless dataset synchronization from cloud storage
- **RESTful API**: FastAPI backend with comprehensive endpoints
- **Modern Frontend**: React-based UI with real-time job monitoring
- **Geocoding**: Automatic location identification for flood areas

## 🏗️ Architecture

```
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/            # API routes and endpoints
│   │   ├── core/           # Configuration and settings
│   │   ├── db/             # Database models and schemas
│   │   ├── ml/             # Machine learning models and utilities
│   │   └── services/       # Business logic services
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment variables template
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   └── index.css       # Styling
│   ├── package.json        # Node.js dependencies
│   └── .env.example        # Frontend environment variables
└── README.md              # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- Google Cloud Service Account (for Earth Engine and Drive access)

### Backend Setup

1. **Clone and navigate to backend**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Start the backend server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup

1. **Navigate to frontend**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your backend URL
   ```

4. **Start development server**
   ```bash
   npm run dev
   ```

5. **Build for production**
   ```bash
   npm run build
   ```

## ⚙️ Configuration

### Backend Environment Variables

Create a `.env` file in the backend directory:

```env
DATABASE_URL=sqlite:///./app.db
DATA_DIR=./data
MODELS_DIR=./models_registry
GOOGLE_APPLICATION_CREDENTIALS=./service_account.json
GDRIVE_FOLDER_ID=your_google_drive_folder_id
CORS_ORIGINS=http://localhost:5173
```

### Frontend Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://127.0.0.1:8000
```

## 📡 API Endpoints

### Health & Monitoring
- `GET /health` - Health check
- `GET /jobs` - List all background jobs
- `GET /jobs/{job_id}` - Get job status

### Regions & Datasets
- `GET /regions` - List available regions
- `POST /regions` - Create new region
- `GET /datasets` - List datasets
- `POST /datasets` - Create dataset

### Models & Predictions
- `GET /models` - List ML models
- `POST /models` - Register new model
- `POST /predictions` - Start flood prediction
- `GET /predictions` - List predictions
- `GET /predictions/{id}/overlay.png` - Get flood overlay image

### Training
- `POST /train` - Start model training

## 🧠 Machine Learning

### Model Architecture
- **U-Net**: Semantic segmentation network for flood detection
- **Input**: Sentinel-1 radar imagery (multiple bands)
- **Output**: Binary flood mask
- **Training**: Custom dataset with labeled flood events

### Data Pipeline
1. **Data Acquisition**: Google Earth Engine API for Sentinel-1 data
2. **Preprocessing**: Radiometric calibration and speckle filtering
3. **Training**: Patch-based training with data augmentation
4. **Inference**: Real-time prediction on selected regions

## 🔧 Development

### Code Style
- Python: PEP 8 compliance
- JavaScript/React: ESLint + Prettier
- Consistent naming conventions across codebase

### Testing
```bash
# Backend tests (when implemented)
cd backend
pytest

# Frontend tests (when implemented)
cd frontend
npm test
```

## 📦 Deployment

### Backend Deployment
1. Build Docker image:
   ```bash
   docker build -t flood-backend backend/
   ```

2. Run with environment variables:
   ```bash
   docker run -p 8000:8000 --env-file backend/.env flood-backend
   ```

### Frontend Deployment
1. Build production bundle:
   ```bash
   cd frontend
   npm run build
   ```

2. Deploy `dist/` folder to your web server

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Google Earth Engine** for satellite data access
- **Sentinel-1** mission for radar imagery
- **U-Net** architecture for semantic segmentation
- **Leaflet** for interactive mapping
- **FastAPI** for high-performance API

## 📞 Support

For questions and support:
- Create an issue in this repository
- Check the API documentation at `http://localhost:8000/docs`

---

**Built with ❤️ for flood monitoring and disaster management**
