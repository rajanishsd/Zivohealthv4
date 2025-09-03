#!/bin/bash

# Emergency Worker Fix Script
# This script handles stuck workers and multiple upload scenarios

set -e

echo "=== Emergency Worker Fix ==="

# 1. Kill any stuck worker processes
echo "1. Killing stuck worker processes..."
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api bash -c "pkill -f worker_process || true" || echo "No worker processes to kill"

# 2. Force restart API container to clear worker state
echo "2. Restarting API container to clear worker state..."
sudo docker compose -f /opt/zivohealth/docker-compose.yml restart api

# 3. Wait for container to be ready
echo "3. Waiting for API container to be ready..."
sleep 15

# 4. Check pending entries
echo "4. Checking pending entries..."
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api python -c "
from app.db.session import SessionLocal
from app.crud.vitals import VitalsCRUD
from app.crud.nutrition import nutrition_data as NutritionCRUD
try:
    db = SessionLocal()
    vitals_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1000))
    nutrition_pending = len(NutritionCRUD.get_pending_aggregation_entries(db, limit=1000))
    print(f'Vitals pending: {vitals_pending}')
    print(f'Nutrition pending: {nutrition_pending}')
    print(f'Total pending: {vitals_pending + nutrition_pending}')
    db.close()
except Exception as e:
    print(f'Error: {e}')
"

# 5. Start fresh worker process
echo "5. Starting fresh worker process..."
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api python aggregation/worker_process.py > /tmp/worker_output.log 2>&1 &
WORKER_PID=$!

echo "Worker started with PID: $WORKER_PID"

# 6. Monitor worker for 30 seconds
echo "6. Monitoring worker for 30 seconds..."
timeout 30s sudo docker compose -f /opt/zivohealth/docker-compose.yml logs -f api | grep -E "(SmartWorker|Worker|Aggregation)" || true

# 7. Check final status
echo "7. Final status check..."
echo "Worker process status:"
ps aux | grep worker_process || echo "No worker process found"

echo "Recent worker logs:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml logs --tail 20 api | grep -E "(SmartWorker|Worker|Aggregation)" || echo "No worker logs found"

echo "=== Emergency Fix Complete ==="
