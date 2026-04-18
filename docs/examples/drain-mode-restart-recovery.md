# Example: Drain Mode And Restart Recovery

The operator needs a controlled restart.

1. Set drain mode through the operator service.
2. Trigger graceful shutdown.
3. Restart the process.
4. Run startup validation.
5. Trigger restart recovery and resume queue dispatch.

This path preserves queue clarity and avoids silent lease loss.
