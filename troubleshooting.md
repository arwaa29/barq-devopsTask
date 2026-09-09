# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.

## Entry 1 / 9-9-2026 / 8:00 pm
- Symptom: `docker compose -p barq-assessment ps -a` shows that app01 and app02 both as "up (unhealthy)" 
while postgress and redis are "healthy" 
- Hypothesis: docker healthcheck is targeting a URL path that doesnot exist on app
- Command or test:  `docker compose -p barq-assessment logs app-01`
- Actual output: repeated log lines every 5s (`app-01  | 127.0.0.1 - - [09/Sep/2026 13:31:00] "GET /healthz HTTP/1.1" 404 -`)

- Failed attempt and what changed your thinking: first hypothesis matches the evidence so i was right
- Root cause: `docker-compose.yml` heathcheck test calls `('http://127.0.0.1:8080/healthz')` but `assessment/APPLICATION.md` difine the end point as `/health ` so there is no (z), app never implemnts /healthz so every check gets 404 and docker marks those container as unhealthy after repeated failures
- Fix: not applied yet
- Retest evidence: pending
- Related commit: pending
- Remaining uncertainty:Need to confirm the Flask app actually implements
  `/health` correctly (returns 200) once we look at the app code directly
  the 404 only proves the *path* is wrong, not that `/health` itself works


## Entry 2 / 10-9-2026 / 1:00 Am
- Symptom: docker-compose.yml showed app-02's INSTANCE_ID set to "app01" and this is identical to app01's instance so both backends will report the same and this violate distinct INSTANCE_ID requirement
- Hypothesis: may be a copy paste error app-02 service block was created from app-01's
- Command or test: manual review of docker-compose.yml
- Actual output: both blocks read `INSTANCE_ID: "app-01"`
- Failed attempt and what changed your thinking: nothing , i found it during manual review so there is no trials
- Root cause: app-02's environment block incorrectly overrides INSTANCE_ID
  with "app-01" instead of "app-02"
- Fix:change app-02's instance with "app-02 in docker-compose.yml
- Retest evidence:(pending, will confirm via curl to /instance on each
  container after rebuild)
- Related commit:pending
- Remaining uncertainty:None on the config itself; still need to verify
  NGINX correctly load-balances between both and returns different IDs
  on repeated requests