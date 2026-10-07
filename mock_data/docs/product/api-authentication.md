# API authentication and rate limits

The SmartHelper API uses personal access tokens. The base URL in this mock environment is `https://api.smarthelper.example/v1`; it is illustrative and does not resolve to a service.

## Create and use a token

In the web app, open **Profile > Developer settings > Personal access tokens**, select **Create token**, choose a name and expiration date, and copy the token. The token is displayed only once. Send it in the `Authorization: Bearer <token>` header over HTTPS. Do not place tokens in URLs or commit them to source control.

Tokens inherit the creating user's workspace permissions. A token cannot access a workspace that its creator cannot access. Revoking a token takes effect immediately. The maximum token lifetime is 90 days.

## Rate limits

The API allows 120 requests per minute per token. When a token exceeds the limit, the API responds with HTTP 429 and a `Retry-After` header in seconds. Clients should wait for that interval and retry with backoff. Rate limits apply independently to each token.

## Pagination

List endpoints return at most 100 items per page. If more items are available, the response contains a `next_cursor`. Pass it as the `cursor` query parameter to get the next page. An absent `next_cursor` means the list is complete.
