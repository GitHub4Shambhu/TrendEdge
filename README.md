# TrendEdge

AI-powered momentum trading analysis platform for stocks, ETFs, options, and futures.

## Overview

TrendEdge provides real-time trading opportunities based on advanced momentum algorithms combined with social sentiment analysis. The platform offers:

- **Momentum Scoring** - AI-based momentum calculation combining price action, volume, and trend strength
- **Sentiment Analysis** - Social media sentiment using FinBERT financial language model
- **Multi-Asset Coverage** - Stocks, ETFs, options, and futures markets
- **Interactive Dashboard** - Real-time visualization of top opportunities

## Architecture

```
TrendEdge/
├── frontend/          # Next.js 14 + TypeScript dashboard
│   ├── src/
│   │   ├── app/       # App router pages
│   │   ├── components/# React components
│   │   └── lib/       # API client & utilities
│   └── package.json
│
├── backend/           # Python FastAPI + ML services
│   ├── app/
│   │   ├── api/       # REST API endpoints
│   │   ├── core/      # Configuration
│   │   ├── models/    # Database models
│   │   ├── schemas/   # Pydantic schemas
│   │   └── services/  # Business logic (momentum, sentiment)
│   ├── tests/         # Test suite
│   └── requirements.txt
│
└── .vscode/           # VS Code tasks
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | Python 3.11, FastAPI, Pydantic |
| ML/AI | scikit-learn, XGBoost, PyTorch, Transformers |
| Market Data | yfinance |
| Sentiment | FinBERT (ProsusAI/finbert) |

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- npm

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TrendEdge
   ```

2. **Set up the backend**
   ```bash
   cd backend
   python -m venv ../.venv
   source ../.venv/bin/activate  # Windows: ..\.venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env  # Configure API keys
   ```

3. **Set up the frontend**
   ```bash
   cd frontend
   npm install
   ```

### Running the Application

**Option 1: Using VS Code Tasks**
- Open VS Code Command Palette (Cmd/Ctrl + Shift + P)
- Run "Tasks: Run Task"
- Select "Backend: Start API Server" and "Frontend: Start Dev Server"

**Option 2: Manual**
```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Access the application:
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/dashboard/` | GET | Main dashboard with top opportunities |
| `/api/v1/dashboard/stocks` | GET | Momentum scores for specific stocks |
| `/api/v1/dashboard/symbol/{symbol}` | GET | Detailed analysis for single symbol |
| `/health` | GET | Health check |

## Momentum Algorithm

The momentum score (range: -1 to +1) combines:

1. **Technical Momentum (40%)** - Rate of Change (ROC) + RSI signals
2. **Volume Analysis (20%)** - Current volume vs 20-day average
3. **Trend Strength (20%)** - ADX-based directional movement
4. **Social Sentiment (20%)** - FinBERT-analyzed social media sentiment

Trading signals:
- **BUY**: Score > threshold & RSI < 70
- **SELL**: Score < -threshold or RSI > 80
- **HOLD**: Otherwise

## Configuration

Environment variables (backend `.env`):

```env
ENVIRONMENT=development
DEBUG=true
ALPHA_VANTAGE_API_KEY=your_key
POLYGON_API_KEY=your_key
CORS_ORIGINS=["http://localhost:3000"]
```

## Development

### Running Tests

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd frontend
npm test
```

### Code Structure for AI Maintainability

- All functions have clear docstrings with Args/Returns
- Pydantic schemas define all data structures
- Configuration centralized in `core/config.py`
- Services are isolated and independently testable
- TypeScript interfaces mirror backend schemas

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request
