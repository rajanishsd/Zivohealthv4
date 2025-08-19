# ZivoHealth Service Management

This document describes how to manage all ZivoHealth services: PostgreSQL, Redis, Backend API, and Dashboard.

## 🎯 Quick Start (Master Scripts)

### Start All Services
```bash
./scripts/start-all.sh
```

### Stop All Services
```bash
./scripts/stop-all.sh
```

### Restart All Services
```bash
./scripts/restart-all.sh
```

### Check Service Status
```bash
./scripts/status-all.sh
```

## 🏗️ Service Architecture

ZivoHealth consists of 4 main services:

1. **PostgreSQL Database** (Port 5433)
   - Stores user data, chat sessions, messages
   - Data location: `backend/data/postgres/`

2. **Redis Cache** (Port 6379)
   - Stores metrics, performance data, cache
   - Data location: `backend/data/redis/`

3. **FastAPI Backend** (Port 8000)
   - Main API server with all endpoints
   - Health check: http://localhost:8000/health

4. **React Dashboard** (Port 3000)
   - Web interface for monitoring and management
   - URL: http://localhost:3000

## 📁 Individual Service Scripts

### PostgreSQL Database
- **Location**: System-managed (brew services or manual)
- **Port**: 5433
- **Data**: `backend/data/postgres/`

```bash
# Manual PostgreSQL management
brew services start postgresql
brew services stop postgresql
```

### Redis Cache
- **Start**: `backend/scripts/start-redis.sh`
- **Stop**: `backend/scripts/stop-redis.sh`
- **Config**: `backend/data/redis/redis.conf`
- **Data**: `backend/data/redis/dump.rdb`

```bash
# Individual Redis management
./backend/scripts/start-redis.sh
./backend/scripts/stop-redis.sh
```

### Backend API Server
- **Start**: `backend/scripts/start_server.sh`
- **Stop**: `backend/scripts/kill_servers.sh`
- **Restart**: `backend/scripts/restart_server.sh`
- **Check**: `backend/scripts/check_server.sh`

```bash
# Individual Backend management
./backend/scripts/start_server.sh
./backend/scripts/kill_servers.sh
./backend/scripts/restart_server.sh
```

### Dashboard (React App)
- **Start**: `backend/start_dashboard.sh`
- **Stop**: Kill processes on port 3000
- **Location**: `backend/backend-dashboard/`

```bash
# Individual Dashboard management
cd backend && ./start_dashboard.sh
```

## 🔄 Service Dependencies

Services should be started in this order:
1. **PostgreSQL** (database first)
2. **Redis** (cache server)
3. **Backend** (API depends on DB and Redis)
4. **Dashboard** (frontend depends on Backend)

Services should be stopped in reverse order:
1. **Dashboard** (frontend first)
2. **Backend** (API server)
3. **Redis** (cache server)
4. **PostgreSQL** (database last)

## 📊 Port Usage

| Service | Port | URL |
|---------|------|-----|
| PostgreSQL | 5433 | `localhost:5433` |
| Redis | 6379 | `localhost:6379` |
| Backend | 8000 | http://localhost:8000 |
| Dashboard | 3000 | http://localhost:3000 |

## 🛠️ Troubleshooting

### Check What's Running
```bash
# Check all service status
./scripts/status-all.sh

# Check specific ports
lsof -ti:5433  # PostgreSQL
lsof -ti:6379  # Redis
lsof -ti:8000  # Backend
lsof -ti:3000  # Dashboard
```

### Force Kill Services
```bash
# Kill everything and restart
./scripts/stop-all.sh
sleep 5
./scripts/start-all.sh

# Manual force kill
sudo kill -9 $(lsof -ti:5433,6379,8000,3000)
```

### Common Issues

#### Backend Can't Connect to Database
```bash
# Check PostgreSQL is running
./scripts/status-all.sh

# Restart database
brew services restart postgresql
```

#### Backend Can't Connect to Redis
```bash
# Check Redis status
redis-cli ping

# Restart Redis with custom config
./backend/scripts/stop-redis.sh
./backend/scripts/start-redis.sh
```

#### Dashboard Not Loading
```bash
# Check if backend is running
curl http://localhost:8000/health

# Restart dashboard
pkill -f "react-scripts"
cd backend && ./start_dashboard.sh
```

#### Port Already in Use
```bash
# Find what's using the port
lsof -ti:PORT_NUMBER

# Kill the process
kill $(lsof -ti:PORT_NUMBER)
```

## 📝 Development Workflow

### Regular Development
```bash
# Start everything
./scripts/start-all.sh

# Check status
./scripts/status-all.sh

# Stop when done
./scripts/stop-all.sh
```

### Backend Development
```bash
# Start dependencies
./backend/scripts/start-redis.sh
brew services start postgresql

# Start backend with auto-reload
./backend/scripts/start_server.sh

# Backend will restart automatically on code changes
```

### Dashboard Development
```bash
# Ensure backend is running
./backend/scripts/start_server.sh

# Start dashboard
cd backend && ./start_dashboard.sh

# Dashboard will hot-reload on changes
```

## 🔧 Configuration Files

- **Redis**: `backend/data/redis/redis.conf`
- **Backend**: `backend/app/core/config.py`
- **Dashboard**: `backend/backend-dashboard/.env`
- **Database**: Environment variables in backend

## 📁 Log Files

- **PostgreSQL**: `backend/data/postgres.log`
- **Redis**: `backend/data/redis/redis.log`
- **Backend**: Console output or `backend/server.log`
- **Dashboard**: Console output or `backend/dashboard.log`

## 🚀 Production Deployment

For production, consider:
1. Using proper process managers (systemd, PM2)
2. Configuring proper logging
3. Setting up monitoring
4. Using environment-specific configs
5. Setting up reverse proxy (nginx)

## 🆘 Emergency Commands

```bash
# Nuclear option - kill everything
sudo pkill -f "postgres\|redis\|uvicorn\|react-scripts"

# Restart everything fresh
./stop-all.sh && sleep 10 && ./start-all.sh

# Check system resources
top -o cpu
df -h
free -m  # Linux
vm_stat  # macOS
``` 