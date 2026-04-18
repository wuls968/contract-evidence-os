# Cross-Host Safe Dispatch

Two workers on different hosts register against the shared coordination backend. The dispatcher admits a task, the queue grants a lease, and the coordination layer binds ownership to a host-aware fencing token. Audit and queue state show who owns the lease, why that worker was chosen, and which provider reservations applied.

