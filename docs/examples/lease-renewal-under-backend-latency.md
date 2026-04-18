# Lease Renewal Under Backend Latency

A worker renews an active lease while the external backend is experiencing higher latency. The runtime records renewal attempts, expiry forecasts, and pressure hints, then uses policy thresholds to decide whether to keep renewing, defer non-critical work, or prepare safe reclamation.

