-- 0009 -- fix topic_counts: the scalar subject filter never worked
--
-- 0008 gave topic_counts a `subject text` parameter meant to restrict the
-- returned topic LIST to that subject's taxonomy (`where subject is null or
-- t.subject = subject`). But the parameter shares its name with the
-- `public.topics.subject` column it is compared against, and in a
-- LANGUAGE sql function an unqualified identifier that matches a column in
-- scope resolves to the column -- so the clause became
-- `t.subject is null or t.subject = t.subject`, i.e. always true, and every
-- subject saw all 23 topics in the Topic dropdown.
--
-- Rename the parameter to `topic_subject` so there is no collision. The
-- browser (topics.js `fetchCounts`) is updated to pass `topic_subject`.
-- Everything else about the function is unchanged from 0008.

drop function if exists
    public.topic_counts(text, integer[], text[], integer[], text[], text);

create function public.topic_counts(
        kind          text      default 'all',
        years         integer[] default null,
        sessions      text[]    default null,
        variants      integer[] default null,
        subjects      text[]    default null,
        topic_subject text      default null
    )
    returns table (
        code        text,
        number      integer,
        name        text,
        subsections text[],
        count       bigint
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    select t.code, t.number, t.name, t.subsections,
        (
            select pg_catalog.count(*)
            from public.questions qu
                join public.papers p on p.id = qu.paper_id
            where t.code = any(qu.topic_codes)
              and (
                    coalesce(kind, 'all') = 'all'
                 or (kind = 'mcq'    and qu.is_mcq)
                 or (kind = 'theory' and not qu.is_mcq)
              )
              and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
              and (sessions is null or pg_catalog.cardinality(sessions) = 0
                   or p.session = any(sessions))
              and (variants is null or pg_catalog.cardinality(variants) = 0
                   or p.variant = any(variants))
              and (subjects is null or pg_catalog.cardinality(subjects) = 0
                   or p.subject_name = any(subjects))
        )::bigint as count
    from public.topics t
    where topic_subject is null or t.subject = topic_subject
    order by t.number;
$$;

revoke all on function
    public.topic_counts(text, integer[], text[], integer[], text[], text)
    from public, anon;
grant execute on function
    public.topic_counts(text, integer[], text[], integer[], text[], text)
    to authenticated;

notify pgrst, 'reload schema';
