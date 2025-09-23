# Reminder Module Architecture

## System Overview

The reminder module is a distributed system built with FastAPI, Celery, RabbitMQ, and Firebase Cloud Messaging (FCM) for handling one-time reminders.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              REMINDER MODULE ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLIENT APP    │    │   MOBILE APP    │    │   WEB APP       │    │   EXTERNAL API  │
│   (iOS/Android) │    │   (iOS/Android) │    │   (Dashboard)   │    │   (Third-party) │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │                      │
          │ HTTP/HTTPS           │ HTTP/HTTPS           │ HTTP/HTTPS           │ HTTP/HTTPS
          │                      │                      │                      │
          └──────────────────────┼──────────────────────┼──────────────────────┘
                                 │                      │
                    ┌─────────────▼─────────────┐      │
                    │     FASTAPI SERVER        │      │
                    │   (Reminder API)         │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   API ENDPOINTS    │ │      │
                    │  │                     │ │      │
                    │  │ • POST /reminders   │ │      │
                    │  │ • GET /reminders    │ │      │
                    │  │ • GET /reminders/{id}│ │      │
                    │  │ • POST /reminders/{id}/ack│ │      │
                    │  │ • POST /devices     │ │      │
                    │  │ • GET /devices      │ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │     DATABASE LAYER       │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   POSTGRESQL DB     │ │      │
                    │  │                     │ │      │
                    │  │ • reminders table   │ │      │
                    │  │ • device_tokens     │ │      │
                    │  │ • user_profiles     │ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │   REPOSITORY LAYER        │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   SQLAlchemy ORM     │ │      │
                    │  │                     │ │      │
                    │  │ • create_reminder()  │ │      │
                    │  │ • get_due_reminders() │ │      │
                    │  │ • mark_processed()   │ │      │
                    │  │ • mark_acknowledged()│ │      │
                    │  │ • upsert_device_token│ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │   MESSAGE QUEUE SYSTEM   │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │     RABBITMQ        │ │      │
                    │  │                     │ │      │
                    │  │ • Input Queue       │ │      │
                    │  │ • Output Queue      │ │      │
                    │  │ • Exchange          │ │      │
                    │  │ • Routing Keys      │ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │     CELERY WORKERS        │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   TASK PROCESSORS   │ │      │
                    │  │                     │ │      │
                    │  │ • reminders.ingest │ │      │
                    │  │ • reminders.scan_and_dispatch│ │      │
                    │  │ • reminders.dispatch│ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │   CELERY BEAT SCHEDULER  │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   PERIODIC TASKS    │ │      │
                    │  │                     │ │      │
                    │  │ • scan_and_dispatch │ │      │
                    │  │   (every N seconds) │ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │   NOTIFICATION DISPATCH  │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   FCM DISPATCHER    │ │      │
                    │  │                     │ │      │
                    │  │ • send_push_via_fcm │ │      │
                    │  │ • Firebase Admin SDK│ │      │
                    │  │ • APNs Integration  │ │      │
                    │  └─────────────────────┘ │      │
                    └─────────────┬─────────────┘      │
                                 │                    │
                    ┌─────────────▼─────────────┐      │
                    │   EXTERNAL SERVICES       │      │
                    │                          │      │
                    │  ┌─────────────────────┐ │      │
                    │  │   FIREBASE CLOUD     │ │      │
                    │  │   MESSAGING (FCM)    │ │      │
                    │  │                     │ │      │
                    │  │ • Push Notifications│ │      │
                    │  │ • iOS APNs          │ │      │
                    │  │ • Android GCM       │ │      │
                    │  └─────────────────────┘ │      │
                    └──────────────────────────┘      │
                                                      │
                    ┌─────────────────────────────────▼─────────────────────────┐
                    │                    END USERS                                 │
                    │                                                             │
                    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
                    │  │   iOS APP   │  │ ANDROID APP │  │   WEB APP    │        │
                    │  │             │  │             │  │             │        │
                    │  │ • Push      │  │ • Push      │  │ • In-app    │        │
                    │  │   Notifications│  │   Notifications│  │   Notifications│        │
                    │  └─────────────┘  └─────────────┘  └─────────────┘        │
                    └─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Reminder Creation Flow
```
Client → FastAPI → Repository → Database
                ↓
            RabbitMQ Input Queue → Celery Worker → Database (Idempotency)
```

### 2. Reminder Processing Flow
```
Celery Beat → Scan Database → Find Due Reminders → RabbitMQ Output Queue → FCM Dispatcher → Firebase → Device
```

### 3. Device Token Management
```
Client → FastAPI → Repository → Database (device_tokens table)
```

## Key Components

### 1. **FastAPI Server** (`api.py`)
- RESTful API endpoints
- Request validation with Pydantic schemas
- API key authentication
- Database session management

### 2. **Repository Layer** (`repository.py`)
- Database operations with SQLAlchemy
- CRUD operations for reminders and device tokens
- Query optimization with indexes

### 3. **Database Schema**
- `reminders` table: Core reminder data
- `device_tokens` table: FCM token management
- `user_profiles` table: User timezone data

### 4. **Message Queue System**
- **RabbitMQ** as message broker
- **Input Queue**: For reminder ingestion
- **Output Queue**: For notification dispatch
- **Exchange**: Message routing

### 5. **Celery Workers**
- **reminders.ingest**: Process incoming reminders
- **reminders.scan_and_dispatch**: Find and dispatch due reminders
- **reminders.dispatch**: Send notifications via FCM

### 6. **Celery Beat Scheduler**
- Periodic scanning for due reminders
- Configurable scan interval
- Batch processing for performance

### 7. **FCM Dispatcher** (`dispatcher.py`)
- Firebase Cloud Messaging integration
- Push notification delivery
- iOS APNs and Android GCM support
- Timezone handling

## Configuration

### Environment Variables
- `REMINDER_SERVICE_HOST/PORT`: API server configuration
- `REMINDER_RABBITMQ_*`: Message queue configuration
- `REMINDER_SCHEDULER_*`: Scheduler configuration
- `REMINDER_FCM_*`: Firebase configuration
- `REMINDER_METRICS_ENABLED`: Metrics collection

## Metrics & Monitoring
- Prometheus metrics for reminder operations
- Scheduler scan counts
- Dispatch success/failure rates
- Acknowledgment tracking

## Limitations
- **One-time reminders only** (no recurrence support)
- No reminder modification after creation
- No bulk operations
- No reminder templates
- No advanced scheduling patterns

## Scalability Considerations
- Horizontal scaling with multiple Celery workers
- Database indexing for performance
- Message queue partitioning
- FCM rate limiting handling
