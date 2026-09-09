-- Paper Finder — add year / session / variant filtering to the cloud RPCs.
--
-- Local side: search() / browse_by_topic() / topic_counts() gained a shared
-- `_paper_scope` helper. The deployed /search and /topics filter bars send
-- `years` / `sessions` / `variants` (variant is surfaced as the "Paper(s)" box),
-- so search_questions / browse_questions / topic_counts grow matching params.
--
-- Every filter follows the null-or-empty-means-unrestricted idiom already used
-- for years/sessions in 0004. Adding params changes each function's signature,
-- so drop-then-create (not CREATE OR REPLACE). Conventions carried from
-- 0001–0005: `security invoker` + `set search_path = ''`, every column
-- table-qualified, `revoke all … from public, anon` then `grant … to
-- authenticated`, `notify pgrst, 'reload schema'` last.

-- --- search_questions: + years / sessions / variants ------------------
drop function if exists public.search_questions(text, integer, text);

create function public.search_questions(
        query       text,
        max_results integer   default 5,
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null
    )
    returns table (
        filename        text,
        subject_name    text,
        year            integer,
        session         text,
        paper           integer,
        variant         integer,
        question_number integer,
        question_text   text,
        answer_text     text,
        marks           integer,
        has_figure      boolean,
        topic_codes     text[],
        crop_count      integer
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    with tsq as (select public.or_tsquery(query) as tq)
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes, qu.crop_count
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
        cross join tsq
    where tsq.tq <> ''::pg_catalog.tsquery
      and qu.question_search @@ tsq.tq
      and (
            coalesce(kind, 'all') = 'all'
         or (kind = 'mcq'    and p.paper = 1)
         or (kind = 'theory' and p.paper is not null and p.paper <> 1)
      )
      and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
      and (sessions is null or pg_catalog.cardinality(sessions) = 0 or p.session = any(sessions))
      and (variants is null or pg_catalog.cardinality(variants) = 0 or p.variant = any(variants))
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

-- --- browse_questions: + variants -----------------------------------
drop function if exists public.browse_questions(text[], text, integer[], text[], integer, integer);

create function public.browse_questions(
        codes       text[],
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null,
        max_results integer   default 20,
        skip        integer   default 0
    )
    returns table (
        filename        text,
        subject_name    text,
        year            integer,
        session         text,
        paper           integer,
        variant         integer,
        question_number integer,
        question_text   text,
        answer_text     text,
        marks           integer,
        has_figure      boolean,
        topic_codes     text[],
        crop_count      integer,
        total_count     bigint
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes, qu.crop_count,
           pg_catalog.count(*) over () as total_count
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
    where qu.topic_codes && codes
      and (
            coalesce(kind, 'all') = 'all'
         or (kind = 'mcq'    and p.paper = 1)
         or (kind = 'theory' and p.paper is not null and p.paper <> 1)
      )
      and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
      and (sessions is null or pg_catalog.cardinality(sessions) = 0 or p.session = any(sessions))
      and (variants is null or pg_catalog.cardinality(variants) = 0 or p.variant = any(variants))
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

-- --- topic_counts: + variants -------------------------------------
drop function if exists public.topic_counts(text, integer[], text[]);

create function public.topic_counts(
        kind     text      default 'all',
        years    integer[] default null,
        sessions text[]    default null,
        variants integer[] default null
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
                 or (kind = 'mcq'    and p.paper = 1)
                 or (kind = 'theory' and p.paper is not null and p.paper <> 1)
              )
              and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
              and (sessions is null or pg_catalog.cardinality(sessions) = 0
                   or p.session = any(sessions))
              and (variants is null or pg_catalog.cardinality(variants) = 0
                   or p.variant = any(variants))
        )::bigint as count
    from public.topics t
    order by t.number;
$$;

-- --- grants --------------------------------------------------------
revoke all on function public.search_questions(text, integer, text, integer[], text[], integer[])
    from public, anon;
revoke all on function
    public.browse_questions(text[], text, integer[], text[], integer[], integer, integer)
    from public, anon;
revoke all on function public.topic_counts(text, integer[], text[], integer[]) from public, anon;
grant execute on function
    public.search_questions(text, integer, text, integer[], text[], integer[])
    to authenticated;
grant execute on function
    public.browse_questions(text[], text, integer[], text[], integer[], integer, integer)
    to authenticated;
grant execute on function public.topic_counts(text, integer[], text[], integer[]) to authenticated;

notify pgrst, 'reload schema';
