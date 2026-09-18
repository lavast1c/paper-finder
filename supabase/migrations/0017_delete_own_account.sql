-- 0017 -- Self-service account deletion
--
-- The privacy policy promises erasure without a published contact address --
-- "Delete account" in the UI needs an RPC a signed-in user can call to remove
-- their own auth.users row (the only place personal data lives; public.papers
-- / questions / topics hold no user data at all). `security definer` is
-- required because a plain `authenticated` role has no privilege on
-- `auth.users` itself; `auth.uid()` scopes the delete to the caller's own row
-- so this can never touch anyone else's account, and `set search_path = ''`
-- (the same guard every RPC here uses) stops it resolving an object from a
-- schema an attacker could inject via a mutable search_path.
--
-- 0015 revoked the default EXECUTE grant on new functions from anon/
-- authenticated/public, so -- same trap 0016 had to route around -- the
-- explicit `grant` below is mandatory or the browser can never reach this.

create function public.delete_my_account()
    returns void
    language plpgsql
    security definer
    set search_path = ''
as $$
begin
    if auth.uid() is null then
        raise exception 'not authenticated';
    end if;
    delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;

notify pgrst, 'reload schema';
