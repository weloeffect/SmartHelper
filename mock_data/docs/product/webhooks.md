# Webhooks

Webhooks notify your application when SmartHelper tasks change. An Owner or Admin can create a webhook in **Settings > Integrations > Webhooks**. Each workspace can have up to ten active webhook endpoints.

## Events and delivery

The supported event types are `task.created`, `task.updated`, and `task.completed`. SmartHelper sends each event as a JSON POST to the endpoint URL. Delivery is at least once, so consumers should deduplicate by the `event_id` field. Events can arrive out of order; use the event timestamp and fetch the task if current state matters.

## Verify a signature

Each request includes an `X-SmartHelper-Signature` header containing an HMAC-SHA256 signature of the raw request body. Use the webhook signing secret shown at creation to verify the signature before processing the event. The secret is displayed only once and can be rotated in webhook settings.

## Retries and failures

The endpoint should return a 2xx status within five seconds. A timeout or non-2xx status triggers retries after approximately 1, 5, and 30 minutes. After the final failed attempt, delivery is marked failed in **Settings > Integrations > Webhooks > Delivery log**. SmartHelper does not automatically replay failed deliveries; an Admin or Owner can manually retry one from the delivery log.
