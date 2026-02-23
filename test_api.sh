#!/bin/bash
# Start backend, wait, test endpoints, then kill backend
cd /Users/shambhuk/Developer/Projects/VSCodeProjects/TrendEdge/backend

# Start server in background, suppress output
/Users/shambhuk/Developer/Projects/VSCodeProjects/TrendEdge/.venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to be ready
for i in $(seq 1 15); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs 2>/dev/null | grep -q "200"; then
        echo "Server ready after ${i}s"
        break
    fi
    sleep 1
done

echo ""
echo "=== Testing Market Sentiment ==="
curl -s --max-time 60 "http://localhost:8000/api/v1/dashboard/market-sentiment?window=10" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('data_source:', d.get('data_source'))
    print('overall_sentiment:', round(d.get('overall_sentiment', 0), 2))
except: print('FAILED to parse')
"

echo ""
echo "=== Testing Max Risk Portfolio ==="
curl -s --max-time 60 "http://localhost:8000/api/v1/dashboard/max-risk-portfolio?top_n=2" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('data_source:', d.get('data_source'))
    print('positions:', len(d.get('positions', [])))
except: print('FAILED to parse')
"

echo ""
echo "=== Testing Institutional Portfolio ==="
curl -s --max-time 60 "http://localhost:8000/api/v1/dashboard/institutional-portfolio?top_n=2" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('data_source:', d.get('data_source'))
    print('positions:', len(d.get('positions', [])))
except: print('FAILED to parse')
"

echo ""
echo "=== Testing Dashboard ==="
curl -s --max-time 60 "http://localhost:8000/api/v1/dashboard/?symbols=AAPL" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('data_source:', d.get('data_source'))
    print('scores:', len(d.get('scores', [])))
except: print('FAILED to parse')
"

echo ""
echo "=== All tests done ==="
kill $SERVER_PID 2>/dev/null
