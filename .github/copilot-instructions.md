# TrendEdge - Copilot Instructions

## Project Overview
TrendEdge is an AI-powered momentum trading analysis platform with a Next.js frontend and Python FastAPI backend.

## Architecture
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS in `/frontend`
- **Backend**: Python 3.11, FastAPI, ML services in `/backend`

## Key Files

### Backend
- `backend/app/main.py` - FastAPI application entry point
- `backend/app/services/momentum_service.py` - Core momentum algorithm
- `backend/app/services/sentiment_service.py` - Social sentiment analysis
- `backend/app/schemas/momentum.py` - Pydantic data models
- `backend/app/api/dashboard.py` - REST API endpoints
- `backend/app/core/config.py` - Configuration settings

### Frontend
- `frontend/src/app/page.tsx` - Main dashboard page
- `frontend/src/components/Dashboard.tsx` - Dashboard component
- `frontend/src/components/OpportunityCard.tsx` - Trading opportunity card
- `frontend/src/lib/api.ts` - Backend API client

## Development Commands

### Start Backend
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

### Start Frontend
```bash
cd frontend && npm run dev
```

## API Endpoints
- `GET /api/v1/dashboard/` - Main dashboard data
- `GET /api/v1/dashboard/stocks?symbols=AAPL,MSFT` - Specific stocks
- `GET /api/v1/dashboard/symbol/{symbol}` - Single symbol analysis

## Data Types
- `MomentumScore` - Score, signal, confidence, price data
- `TopOpportunity` - Ranked opportunity with targets
- `DashboardResponse` - Full dashboard response

## Momentum Algorithm
Combines: Technical (40%) + Volume (20%) + Trend (20%) + Sentiment (20%)
Signals: BUY (score > threshold), SELL (score < -threshold), HOLD

## Advanced AI Momentum Algorithm

The advanced algorithm (`backend/app/services/advanced_momentum.py`) uses multi-factor analysis:

### Components & Weights:
- **Price Momentum (30%)** - Multi-timeframe ROC (5, 10, 20, 60 days)
- **Volume Momentum (15%)** - Volume ratio, trend, accumulation/distribution
- **Technical Indicators (25%)** - RSI, MACD, Bollinger Bands, ADX, MFI, Stochastic
- **ML Prediction (20%)** - Ensemble of signals simulating XGBoost
- **Sentiment (10%)** - Social media sentiment (when available)

### Technical Indicators Calculated:
- RSI (7 & 14 period)
- MACD with signal line and histogram
- Bollinger Band position (0-1)
- ADX trend strength
- ATR volatility percentage
- SMA distances (20, 50, 200 day)
- EMA crossover (9/21)
- On-Balance Volume trend
- Money Flow Index
- Stochastic %K and %D

### New API Endpoints:
- `GET /api/v1/dashboard/scan` - Full market scan with AI algorithm
- `GET /api/v1/dashboard/analyze/{symbol}` - Detailed symbol analysis

### Stock Universe:
- S&P 500 components
- NASDAQ 100 components  
- High momentum/volatile stocks
- Sector ETFs for market breadth
