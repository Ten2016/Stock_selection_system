# Stock Selection System

A stock selection system with K-line chart display and data sync functionality.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + SQLite + Akshare
- **Frontend**: Vue 3 + Element Plus + ECharts

## Setup

### Backend Setup (Windows 10)

1. Navigate to the backend directory:
```
cd h:\gitCode\Stock_selection_system\backend
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Run the backend server:
```
python run.py
```

The backend will start on http://127.0.0.1:8001

### Frontend Setup (Windows 10)

1. Navigate to the frontend directory:
```
cd h:\gitCode\Stock_selection_system\frontend
```

2. Install dependencies (requires Node.js):
```
npm install
```

3. Run the frontend dev server:
```
npm run dev
```

The frontend will start on http://localhost:5173

## Usage

1. Open http://localhost:5173 in your browser
2. Go to "数据同步" (Data Sync) and click "开始同步" to download stock data
3. After syncing, browse the stock list and click "详情" to view K-line charts

## Project Structure

```
Stock_selection_system/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── core/          # Configuration
│   │   ├── models/        # Database models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── utils/        # Utilities
│   │   └── main.py       # FastAPI app
│   ├── data/             # SQLite database
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/          # API client
    │   ├── router/       # Vue router
    │   ├── views/        # Page components
    │   └── App.vue       # Main app
    └── package.json
```
