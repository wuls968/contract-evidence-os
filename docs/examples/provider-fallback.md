# Provider Fallback

Scenario:
- A live or primary provider fails during extraction.
- The runtime records a provider incident.
- The scheduler triggers replanning.
- A recovery branch re-executes the extraction path with a safer route.

Expected artifacts:
- failed provider incident
- plan revision record
- execution branch history with the recovery branch selected
- provider usage records showing the failed and successful paths
