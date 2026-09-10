-- Paper Finder — carry the per-question mark-scheme crop count to the cloud.
--
-- Local side: `paper-finder figures` now also renders the mark scheme for each
-- structured question (one PNG per page-region) into
-- data/crops/<ms_stem>/q<NN>_p<K>.png, and records answers.answer_crop_count.
-- `paper-finder publish` carries that count on the flat question row so the
-- browser knows how many mark-scheme images a revealed card has WITHOUT probing
-- storage; the PNGs ride the existing `question-crops` bucket (its
-- `authenticated`-read policy from 0005 already covers the `ms_` folders, and
-- `paper-finder publish-figures` already walks every data/crops/*/ dir).
--
-- Adding an OUT column changes each function's return type, which CREATE OR
-- REPLACE forbids -- drop-then-create. Signatures are unchanged from 0006.
-- Conventions carried from 0001–0006: `security invoker` + `set search_path =
-- ''`; every column table-qualified; `revoke all … from public, anon` then
-- `grant execute … to authenticated`; `notify pgrst, 'reload schema'` last.

-- --- answer_crop_count on the (flat) question row --------------------
alter table public.questions
    add column if not exists answer_crop_count integer not null default 0;

-- --- browse_questions: + answer_crop_count OUT column ---------------
drop function if exists
    public.browse_questions(text[], text, integer[], text[], integer[], integer, integer);

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
        filename          text,
        subject_name      text,
        year              integer,
        session           text,
        paper             integer,
        variant           integer,
        question_number   integer,
        question_text     text,
        answer_text       text,
        marks             integer,
        has_figure        boolean,
        topic_codes       text[],
        crop_count        integer,
        answer_crop_count integer,
        total_count       bigint
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes, qu.crop_count, qu.answer_crop_count,
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

-- --- search_questions: + answer_crop_count OUT column --------------
drop function if exists public.search_questions(text, integer, text, integer[], text[], integer[]);

create function public.search_questions(
        query       text,
        max_results integer   default 5,
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null
    )
    returns table (
        filename          text,
        subject_name      text,
        year              integer,
        session           text,
        paper             integer,
        variant           integer,
        question_number   integer,
        question_text     text,
        answer_text       text,
        marks             integer,
        has_figure        boolean,
        topic_codes       text[],
        crop_count        integer,
        answer_crop_count integer
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    with tsq as (select public.or_tsquery(query) as tq)
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes, qu.crop_count, qu.answer_crop_count
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

-- --- grants (unchanged shape, re-applied for the recreated functions) --
revoke all on function
    public.browse_questions(text[], text, integer[], text[], integer[], integer, integer)
    from public, anon;
revoke all on function public.search_questions(text, integer, text, integer[], text[], integer[])
    from public, anon;
grant execute on function
    public.browse_questions(text[], text, integer[], text[], integer[], integer, integer)
    to authenticated;
grant execute on function
    public.search_questions(text, integer, text, integer[], text[], integer[])
    to authenticated;

notify pgrst, 'reload schema';
