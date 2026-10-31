# Service boundaries

Keep external integrations behind service adapters:

- `communications/`: Twilio calls, keypad handling, SMS links and recorded Hindi prompts.
- `risk/`: Open-Meteo retrieval, crop-stage features and the rule-based risk score.
- `vision/`: trap insect counts, leaf symptom classification and image quality checks.
- `mapping/`: field geometry, heat map and affected-zone calculations.
- `missions/`: zone-only lawnmower route, `.waypoints` export and spray savings.

Do not let route handlers contain business logic. Keep low-confidence cases on the human-expert path.
