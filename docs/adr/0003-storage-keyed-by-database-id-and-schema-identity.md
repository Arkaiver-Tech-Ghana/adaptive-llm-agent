# Storage keyed by database-id + schema identity per Business

As the number of Businesses grows, some will need schema-level or even
database-level isolation (blast radius, per-client scaling, compliance) —
a single shared schema with a `business_id` column won't hold for all of
them indefinitely. We're keying all storage access by a
`database-id + schema-identity` pair from day one instead of a single
shared schema, even though v1 only stands up one schema for its two
Businesses. Retrofitting per-Business schema/database routing onto a
codebase built around one shared schema is a much larger migration than
building the identity system in from the start.
