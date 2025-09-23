brew install --cask session-manager-plugin
aws --version && session-manager-plugin


export AWS_PROFILE=zivohealth
export AWS_REGION=us-east-1

aws sts get-caller-identity
aws ssm get-parameter --with-decryption --name /zivohealth/dev/db/password --query 'Parameter.Value' --output text

export AWS_PROFILE=zivohealth
export AWS_REGION=us-east-1
cd /Users/rajanishsd/Documents/ZivohealthPlatform/infra/terraform
IID=$(terraform output -raw ec2_instance_id)

aws ssm start-session --target "$IID" --profile $AWS_PROFILE --region $AWS_REGION



build docker image

export AWS_DEFAULT_REGION=us-east-1
export ECR=474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend
export TAG=$(aws ssm get-parameter --name /zivohealth/dev/deploy/image_tag --query 'Parameter.Value' --output text)
sudo cat /opt/zivohealth/.env

#Login to ECR and pull the exact tag
aws ecr get-login-password --region $AWS_DEFAULT_REGION \
  | sudo docker login --username AWS --password-stdin "$(echo $ECR | cut -d'/' -f1)"
sudo docker pull "$ECR:$TAG"

#Start compose (images are pinned in the file)
sudo docker compose -f /opt/zivohealth/docker-compose.yml down
sudo docker system df; sudo docker system prune -af
sudo docker compose -f /opt/zivohealth/docker-compose.yml pull
sudo docker compose -f /opt/zivohealth/docker-compose.yml build api --no-cache
sudo docker compose -f /opt/zivohealth/docker-compose.yml up -d

#Check status and health
sudo docker compose -f /opt/zivohealth/docker-compose.yml ps
sudo docker compose -f /opt/zivohealth/docker-compose.yml logs --tail 200 api || true
curl -sS -m 10 http://127.0.0.1/health || true
sudo vim /opt/zivohealth/.env


sudo docker compose -f /opt/zivohealth/docker-compose.yml logs --tail 200 api || true

sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml logs -f --tail=200 reminders
sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml logs -f --tail=200 reminders-beat
sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml logs -f --tail=200 reminders-worker

sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml exec reminders bash -lc 'tail -f -n 200 /var/log/reminders-worker.log'

patient@zivohealth.com

rebuild

export AWS_PROFILE=zivohealth AWS_REGION=us-east-1
ECR=$(terraform output -raw ecr_repository_url)
TAG=$(git -C .. rev-parse --short HEAD)

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $(echo $ECR | cut -d'/' -f1)
docker buildx create --use --name zivo-builder >/dev/null 2>&1 || docker buildx use zivo-builder
docker buildx build --platform linux/amd64 -t $ECR:$TAG -f backend/Dockerfile backend --push


build_ecr_backend.sh -p zivohealth -r us-east-1 --no-latest 
./scripts/dev/build_ecr_backend.sh -p zivohealth -r us-east-1  
./scripts/dev/ssm_shell.sh -p zivohealth -r us-east-1
./scripts/dev/deploy_compose_on_ec2.sh -p zivohealth -r us-east-1

sudo docker system df; sudo docker system prune -af



db 
#tunnel on terminal 1
export AWS_PROFILE=zivohealth
export AWS_REGION=us-east-1
cd infra/terraform
IID=$(terraform output -raw ec2_instance_id)
RDS=$(terraform output -raw rds_endpoint)

aws ssm start-session \
  --target "$IID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host="$RDS",portNumber="5432",localPortNumber="15432"

#terminal 2
pg_dump -h localhost -p 5432 -U rajanishsd -d zivohealth \
  --schema-only --no-owner --no-privileges > schema.sql

psql -h localhost -p 15432 -U zivo -d zivohealth_dev -f schema.sql

pg_dump -h localhost -p 5432 -U rajanishsd -d zivohealth \
  --format=custom --no-owner --no-privileges --data-only --file=local_data.dump

pg_restore --no-owner --no-privileges --data-only --disable-triggers \
  -h localhost -p 15432 -U zivo -d zivohealth_dev local_data.dump

pg_restore -l local_data.dump > toc.list

pg_restore --verbose --no-owner --no-privileges --data-only --single-transaction \
  -h localhost -p 15432 -U zivo -d zivohealth_dev \
  -L toc.list local_data.dump

pg_restore --verbose --no-owner --no-privileges --data-only --single-transaction \
  -h localhost -p 15432 -U zivo -d zivohealth_dev \
  -T public.table1 -T public.table2 -T public.table3 \
  local_data.dump


export AWS_PROFILE=zivohealth
export AWS_REGION=us-east-1
export PGPASSWORD=$(aws ssm get-parameter --with-decryption --name /zivohealth/dev/db/password --query 'Parameter.Value' --output text)

psql -h localhost -p 15432 -U zivo -d zivohealth_dev -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO zivo;
GRANT ALL ON SCHEMA public TO public;
SQL

langchain_pg_embedding
snomed_pg_embedding
rxnorm_pg_embedding
loinc_pg_embedding


sudo grep -q '^  caddy:' /opt/zivohealth/docker-compose.yml || sudo cat >> /opt/zivohealth/docker-compose.yml <<'YAML'
  caddy:
    image: public.ecr.aws/docker/library/caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - api
YAML




./scripts/dev/build_ecr_backend.sh --also-latest
aws ssm put-parameter --profile zivohealth --region us-east-1 \
  --name "/zivohealth/dev/deploy/image_tag" --type String --value "latest" --overwrite



  AWS_PROFILE=zivohealth terraform plan -input=false -out=tfplan -var="image_tag=latest" | cat

sudo docker system prune -af --volumes

#update .env file to ec2
#first seed the keys
scripts/dev/seed_ssm_from_env.sh --project zivohealth --environment dev --profile "$AWS_PROFILE" --region "$AWS_REGION" --env-file backend/.env

# Regenerate .env by recreating EC2 (cleanest)
terraform -chdir=infra/terraform apply -auto-approve \
  -var "aws_region=$AWS_REGION" -var "image_tag=latest" \
  -replace=module.compute.aws_instance.host

#update in place
IID=$(terraform -chdir=infra/terraform output -raw ec2_instance_id)
CONTENT=$(base64 < backend/.env | tr -d '\n')
aws ssm send-command --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --instance-ids "$IID" --document-name AWS-RunShellScript \
  --parameters commands="[
\"sudo bash -lc 'echo $CONTENT | base64 -d > /opt/zivohealth/.env'\",
\"sudo bash -lc 'cd /opt/zivohealth && docker compose up -d'\"
]"

#verify on ec2
IID=$(terraform -chdir=infra/terraform output -raw ec2_instance_id)
CID=$(aws ssm send-command --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --instance-ids "$IID" --document-name AWS-RunShellScript \
  --parameters commands='["sudo head -n 200 /opt/zivohealth/.env","cd /opt/zivohealth && docker compose ps"]' \
  --query 'Command.CommandId' --output text)
aws ssm get-command-invocation --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --command-id "$CID" --instance-id "$IID" \
  --query 'StandardOutputContent' --output text


  #db connection
  AWS_PROFILE=zivohealth AWS_REGION=us-east-1 PGPASSWORD=$(aws ssm get-parameter --with-decryption --name /zivohealth/dev/db/password --query 'Parameter.Value' --output text) psql -h localhost -p 15432 -U zivo -d zivohealth_dev -v ON_ERROR_STOP=1 -c "select;" | cat
  AWS_PROFILE=zivohealth AWS_REGION=us-east-1 PGPASSWORD=$(aws ssm get-parameter --with-decryption --name /zivohealth/dev/db/password --query 'Parameter.Value' --output text) psql -h localhost -p 15432 -U zivo -d zivohealth_dev -v ON_ERROR_STOP=1 -c "select * from public.nutrition_raw_table order by id desc limit 10;"


  #aggregation run

  sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api python aggregation/worker_process.py
  

  python3 /Users/rajanishsd/Documents/ZivohealthPlatform/migration.py \
   --dump "/Users/rajanishsd/Documents/ZivohealthPlatform" \
  --table public.loinc_pg_collection \
  --host localhost --port 5432 --dbname zivohealth_dev --user zivo --password 'zivo_890' \
  --sslmode require --chunk-size 200000 --truncate-before --disable-triggers --statement-timeout-ms 0


  TOKEN=$(aws rds generate-db-auth-token --hostname zivohealth-dev-postgres.cabauc2kk65l.us-east-1.rds.amazonaws.com --port 5432 --username zivo --region us-east-1)
  python3 /Users/rajanishsd/Documents/ZivohealthPlatform/migration.py \
  --table public.loinc_pg_collection \
  --host 127.0.0.1 --port 5432 \
  --dbname zivohealth_dev --user zivo --password "$TOKEN" \
  --sslmode require --chunk-size 100000 --truncate-before


  ssh -i /Users/rajanishsd/Downloads/ec2-dbeaver.pem ubuntu@54.234.91.125


# Check agent status and logs
sudo systemctl status amazon-ssm-agent | cat
sudo journalctl -u amazon-ssm-agent -n 200 --no-pager

# Restart and enable at boot
sudo systemctl restart amazon-ssm-agent
sudo systemctl enable amazon-ssm-agent

# If installed via snap, also try:
snap list amazon-ssm-agent || true
sudo snap restart amazon-ssm-agent || true

# Verify outbound to SSM endpoints
for h in ssm.us-east-1.amazonaws.com ec2messages.us-east-1.amazonaws.com ssmmessages.us-east-1.amazonaws.com; do
  echo $h; nc -zv $h 443
done

# If time drift suspected, resync time
timedatectl
sudo systemctl restart systemd-timesyncd || true

wget https://s3.amazonaws.com/amazon-ssm-us-east-1/latest/debian_amd64/amazon-ssm-agent.deb -O /tmp/amazon-ssm-agent.deb
sudo dpkg -i /tmp/amazon-ssm-agent.deb
sudo systemctl restart amazon-ssm-agent

# Check worker status and handle stuck workers
echo "=== Worker Status Commands ==="

# Check if worker process is running
echo "1. Check if worker process is running:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api ps aux | grep worker_process || echo "No worker process found"

# Check worker logs
echo "2. Check worker logs:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api tail -n 50 worker.log || echo "No worker.log found"

# Check background worker status in API logs
echo "3. Check background worker status in API logs:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml logs --tail 100 api | grep -E "(SmartWorker|Worker|Aggregation)" || echo "No worker logs found"

# Kill stuck worker processes
echo "4. Kill stuck worker processes:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api pkill -f worker_process || echo "No worker processes to kill"

# Check pending aggregation entries
echo "5. Check pending aggregation entries:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api python -c "
from app.db.session import SessionLocal
from app.crud.vitals import VitalsCRUD
from app.crud.nutrition import nutrition_data as NutritionCRUD
db = SessionLocal()
try:
    vitals_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1000))
    nutrition_pending = len(NutritionCRUD.get_pending_aggregation_entries(db, limit=1000))
    print(f'Vitals pending: {vitals_pending}')
    print(f'Nutrition pending: {nutrition_pending}')
    print(f'Total pending: {vitals_pending + nutrition_pending}')
finally:
    db.close()
" || echo "Failed to check pending entries"

# Force restart worker process
echo "6. Force restart worker process:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api python aggregation/worker_process.py &
echo "Worker process started in background"

# Check database connections
echo "7. Check database connections:"
sudo docker compose -f /opt/zivohealth/docker-compose.yml exec -T api python -c "
from app.db.session import engine
print(f'Database pool size: {engine.pool.size()}')
print(f'Database checked out: {engine.pool.checkedout()}')
print(f'Database overflow: {engine.pool.overflow()}')
" || echo "Failed to check database connections"

# Reset worker state (emergency)
echo "8. Emergency worker reset (restart API container):"
echo "sudo docker compose -f /opt/zivohealth/docker-compose.yml restart api"

# Monitor worker in real-time
echo "9. Monitor worker in real-time:"
echo "sudo docker compose -f /opt/zivohealth/docker-compose.yml logs -f api | grep -E '(SmartWorker|Worker|Aggregation)'"

# Emergency fix for stuck workers
echo "10. Emergency fix for stuck workers:"
echo "./scripts/dev/emergency_worker_fix.sh"



curl -sS -X POST "${BASE_URL}/" \
  -H "Content-Type: application/json" \
  -H "x-api-key: ${API_KEY}" \
  -d "{
    \"user_id\": \"1\",
    \"reminder_type\": \"test\",
    \"title\": \"Test from localhost\",
    \"message\": \"Should fire in 1 minute\",
    \"reminder_time\": \"${REMINDER_TIME}\",
    \"payload\": { \"source\": \"localhost\" }
  }" | jq .