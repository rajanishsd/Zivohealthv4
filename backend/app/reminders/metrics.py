from prometheus_client import Counter, Gauge


reminders_created_total = Counter(
    "reminders_created_total",
    "Total reminders created via API",
)

reminders_acknowledged_total = Counter(
    "reminders_acknowledged_total",
    "Total reminders acknowledged by clients",
)

scheduler_scans_total = Counter(
    "reminder_scheduler_scans_total",
    "Total scheduler scan cycles",
)

scheduler_dispatched_total = Counter(
    "reminder_scheduler_dispatched_total",
    "Total reminders dispatched by scheduler",
)

reminders_dispatch_success_total = Counter(
    "reminders_dispatch_success_total",
    "Total successful push dispatches",
)

reminders_dispatch_failed_total = Counter(
    "reminders_dispatch_failed_total",
    "Total failed push dispatches",
)


