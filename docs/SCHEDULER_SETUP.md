# Reminder Scheduler Setup

## Overview

The reminder scheduler is configured to run daily at 9:00 AM to check if reminder notifications should be sent to workers who haven't submitted their shift requests for the next month.

## Implementation

### Scheduler Module

The scheduler is implemented in `app/scheduler/reminder_scheduler.py` using APScheduler's `AsyncIOScheduler`.

### Key Components

1. **check_and_send_reminders()**: The main function that runs daily
   - Creates a database session
   - Calls `ReminderService.send_reminders()`
   - Handles errors gracefully
   - Closes the database session

2. **start_scheduler()**: Initializes and starts the scheduler
   - Configures a cron job to run at 9:00 AM daily
   - Starts the scheduler
   - Called during application startup

3. **stop_scheduler()**: Stops the scheduler gracefully
   - Shuts down the scheduler
   - Called during application shutdown

### Integration with FastAPI

The scheduler is integrated with the FastAPI application lifecycle in `main.py`:

```python
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    init_db()
    start_scheduler()  # Start the reminder scheduler

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on application shutdown."""
    stop_scheduler()  # Stop the reminder scheduler
```

## Configuration

The scheduler behavior is configured in `app/config.py`:

- **reminder_days_before**: List of days before deadline to send reminders (default: [7, 3, 1])
- **default_deadline_day**: The default deadline day of the month (default: 10)

## Reminder Logic

The scheduler runs daily and:

1. Checks if today is a reminder day (7, 3, or 1 day before the deadline)
2. If yes, identifies workers who haven't submitted requests for next month
3. Sends LINE notifications to those workers
4. Records the reminder in the `reminder_logs` table

## Testing

Tests are located in `tests/test_scheduler.py` and verify:

- Database session management
- ReminderService integration
- Error handling
- Scheduler configuration
- Start/stop functionality

## Manual Testing

To manually trigger the reminder check (for testing purposes):

```python
from app.scheduler.reminder_scheduler import check_and_send_reminders

# This will run the reminder check immediately
check_and_send_reminders()
```

## Deployment Considerations

- The scheduler runs in-process with the FastAPI application
- Ensure only one instance of the application is running to avoid duplicate reminders
- For multi-instance deployments, consider using a distributed task queue (e.g., Celery) instead
- The scheduler uses UTC time internally; adjust the cron schedule if needed for your timezone

## Monitoring

The scheduler logs important events:

- Scheduler start/stop
- Daily reminder checks
- Number of reminders sent
- Errors during reminder processing

Check application logs for scheduler activity.
