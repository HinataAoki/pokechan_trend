from typing import Callable

from supabase import Client, create_client

import config

_client: Client | None = None

_PAGE_SIZE = 1000  # PostgREST's default/max rows per response


def get_client() -> Client:
    """Server-side Supabase client authenticated with the service_role key.

    This bypasses RLS entirely, so it must never be used outside the
    backend (GitHub Actions job). The frontend uses the anon key instead.
    """
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def select_all(
    client: Client,
    table: str,
    columns: str,
    filter_fn: Callable[[object], object] | None = None,
) -> list[dict]:
    """Page through every row of a query - a plain .execute() silently caps
    out at PostgREST's default row limit (1000 rows), which has already
    truncated results more than once as this project's tables grew."""
    rows = []
    offset = 0
    while True:
        query = client.table(table).select(columns)
        if filter_fn is not None:
            query = filter_fn(query)
        page = query.range(offset, offset + _PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return rows
