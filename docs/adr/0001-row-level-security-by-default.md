# Row-level security by default for Customer data

Storage is shared across Businesses and Customers, so a naive schema makes
it easy for one Customer's data to leak into another's response by
application-code mistake rather than by design. We're enabling RLS by
default so a Customer's own data is invisible to other Customers unless a
query is explicitly written as an aggregate-only exception. This makes
"customers can't see each other's data" true by construction, which matters
here specifically because action-safety and data-access discipline are
what the reviewer is evaluating.
