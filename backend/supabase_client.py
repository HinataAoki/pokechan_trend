from supabase import Client, create_client

import config

_client: Client | None = None


def get_client() -> Client:
    """Server-side Supabase client authenticated with the service_role key.

    This bypasses RLS entirely, so it must never be used outside the
    backend (GitHub Actions job). The frontend uses the anon key instead.
    """
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client
