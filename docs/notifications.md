# Failure notifications

AgentCron sends a webhook only after the final attempt ends in `failed`, `timeout`, or `silent-fail`. The default payload contains operational metadata only. Prompt text and agent output are excluded unless `include_prompt` or `include_output` is explicitly enabled.

Only HTTP and HTTPS webhook URLs are accepted. Requests use a bounded timeout, and notification failures never change the job result. Treat any webhook endpoint as a data processor; do not include prompt or output content unless you control and trust it.
