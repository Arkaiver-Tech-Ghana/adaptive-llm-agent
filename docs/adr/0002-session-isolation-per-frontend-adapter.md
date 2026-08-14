# Session context is isolated per Frontend Adapter

A Customer could in principle reach the same Business through more than
one Frontend Adapter (WhatsApp now, web later). We're keying Sessions by
`frontend-type + Customer identity` rather than by Customer identity alone,
so context never bleeds between a Customer's WhatsApp Session and their web
Session for the same Business, even though both belong to the same person.
This is deliberately conservative: unifying Sessions across channels later
is an additive change, but un-merging a shared Session once Customers
depend on cross-channel context would not be. Revisit if a real
cross-channel use case appears (P2 territory).
