# Example: Multi-Worker Safe Dispatch

Two workers share one queue. A task is admitted, leased to one worker, and tracked through a separate ownership record with a fencing token. Another worker cannot safely complete that task unless ownership is re-assigned.
