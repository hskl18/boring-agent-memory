# Deployment Token Handling

Never store raw deployment credentials in memory output.

DEPLOYMENT_TOKEN_VALUE=fixture-token-for-redaction

The expected indexed text should redact the token value and keep only enough
context for source-grounded recall.
