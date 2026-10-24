"""Catalog database support: schema migrations, course composition, object-store bodies.

Nothing here changes production behavior by itself: the curriculum service only uses the
Postgres store when CATALOG_DATABASE_URL is set. See docs/catalog-db.txt.
"""
