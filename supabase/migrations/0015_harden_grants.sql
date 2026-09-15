-- 0015 -- Least-privilege grants for the browser-facing roles
--
-- RLS was already on for every public table (papers / questions / topics),
-- each with a single `for select to authenticated` policy, and a live test as
-- `authenticated` confirmed INSERT is rejected and UPDATE/DELETE touch 0 rows.
-- But the tables still carried Supabase's default GRANT ALL to
-- `authenticated`, so RLS was the only thing standing between a signed-in
-- user and a write. Two holes that leaves:
--   * TRUNCATE is not governed by RLS at all -- only by the table privilege.
--   * Any future permissive policy or SECURITY DEFINER function would turn
--     the dormant INSERT/UPDATE/DELETE grants live.
-- The index is read-only from the browser; `paper-finder publish` writes as
-- `postgres` and `publish-figures` as `service_role`, neither affected here.
--
-- Default privileges: new tables/sequences/functions created by `postgres` in
-- `public` were auto-granted to anon + authenticated (and functions to
-- PUBLIC), so a future table added without RLS would be world-readable and
-- writable via the publishable key. Revoke those defaults -- every future
-- migration must now grant exactly what it means to expose.

revoke insert, update, delete, truncate, references, trigger
    on public.papers, public.questions, public.topics
    from anon, authenticated;
revoke all on public.papers, public.questions, public.topics from anon;

alter default privileges for role postgres in schema public
    revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
    revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
    revoke execute on functions from anon, authenticated, public;

notify pgrst, 'reload schema';
