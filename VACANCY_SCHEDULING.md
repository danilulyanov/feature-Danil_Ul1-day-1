# Daily Vacancy Delivery (plan)

Checklist for adding daily delivery at `preferences.vacancy_schedule_time` (HH:MM).

## Architecture
- `BotScheduler` (APScheduler) already in `bot/utils/scheduler.py`, launched in `main.py` via `setup_scheduler()`.
- Store settings in `users.preferences`:
  - `vacancy_schedule_time`: `HH:MM` (local user time; default to `Europe/Moscow` for now).
  - `vacancy_last_sent_at`: UTC ISO, to ensure “once per day”.
  - (optional) `sent_vacancy_ids`: list of IDs to prevent duplicates.

## Flow
1) **Scheduler**  
   - In `setup_scheduler`, add a job `CronTrigger(minute="*")` → `run_daily_vacancies` (runs every minute; inside we match user HH:MM in their timezone).
   - Job lives in a separate module, not in handlers.

2) **User selection**  
   - Repo method: fetch `users` with `is_active=True` and `preferences->>'vacancy_schedule_time' = HH:MM` (in a chosen TZ) where `vacancy_last_sent_at` is not today.  
   - If TZ is needed, later add `preferences.timezone` and convert to UTC for comparison.

3) **Vacancy search**  
   - For each user gather filters: `preferences.search_filters`, `city`, `desired_position`, `skills`.  
   - Use the existing search service (the one used by /search). Limit, e.g., top 10.
   - Dedup: exclude already sent (`sent_vacancy_ids` or `user_search_results` for recent days).

4) **Sending**  
   - Send a single message (list of links/short cards). You can reuse rendering from `bot/handlers/search/pagination.py` if convenient.  
   - Log successes/failures without blocking others.

5) **Persist**  
   - On success: update `vacancy_last_sent_at=utcnow()` and add IDs to `sent_vacancy_ids` (trim old ones).  
   - Commit per user in one transaction.

6) **Test**  
   - Locally create a test user with time “one minute from now,” wait for the job, verify sending and field updates.  
   - Expect a log line like “Job ‘daily_vacancies’ …”.

## Mini-tasks (to remember)
- [x] Add repo method to fetch users by time (`UserRepository.get_users_for_schedule(time_str, tz)`).
- [x] Add storage for `vacancy_last_sent_at`/`sent_vacancy_ids` (in prefs).
- [x] Implement `run_daily_vacancies` (search, send, log).
- [x] Register the job in `setup_scheduler`.
- [x] Add timezone selection in settings.
