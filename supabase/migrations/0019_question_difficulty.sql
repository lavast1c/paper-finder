-- 0019 -- relative question difficulty (1-5)
--
-- 1. questions.difficulty: a 1-5 rating relative to the question's own subject,
--    from labels/question_difficulty.tsv via `paper-finder publish`. NULL =
--    not rated yet (only Pure Mathematics 1 so far).
--
-- 2. search_questions / browse_questions / topic_counts gain a trailing
--    `difficulties integer[]` filter (default null = no restriction, so the
--    currently deployed browser code keeps working unchanged), and
--    search/browse return `difficulty` so the page can show a badge. Bodies are
--    otherwise verbatim from 0016. A new return column can't go through
--    CREATE OR REPLACE, and a new parameter would otherwise leave an ambiguous
--    overload, so the old signatures are dropped first; grants are explicit
--    since 0015 removed the default EXECUTE grants.

alter table public.questions add column if not exists difficulty smallint;
alter table public.questions drop constraint if exists questions_difficulty_range;
alter table public.questions add constraint questions_difficulty_range
    check (difficulty is null or difficulty between 1 and 5);

-- --- search_questions + difficulties ---------------------------------
drop function if exists
    public.search_questions(text, integer, text, integer[], text[], integer[], text[], integer[]);

create function public.search_questions(
    query text,
    max_results integer default 5,
    kind text default 'all',
    years integer[] default null,
    sessions text[] default null,
    variants integer[] default null,
    subjects text[] default null,
    papers integer[] default null,
    difficulties integer[] default null
)
returns table (
    filename text, subject_name text, year integer, session text, paper integer,
    variant integer, question_number integer, question_text text, answer_text text,
    marks integer, has_figure boolean, topic_codes text[], crop_count integer,
    answer_crop_count integer, difficulty smallint
)
language sql
stable
set search_path = ''
as $$
    with tsq as (select public.or_tsquery(query) as tq)
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes, qu.crop_count, qu.answer_crop_count,
           qu.difficulty
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
        cross join tsq
    where tsq.tq <> ''::pg_catalog.tsquery
      and qu.question_search @@ tsq.tq
      and (
            coalesce(kind, 'all') = 'all'
         or (kind = 'mcq'    and qu.is_mcq)
         or (kind = 'theory' and not qu.is_mcq)
      )
      and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
      and (sessions is null or pg_catalog.cardinality(sessions) = 0 or p.session = any(sessions))
      and (variants is null or pg_catalog.cardinality(variants) = 0 or p.variant = any(variants))
      and (subjects is null or pg_catalog.cardinality(subjects) = 0
           or p.subject_name = any(subjects))
      and (search_questions.papers is null or pg_catalog.cardinality(search_questions.papers) = 0
           or p.paper = any(search_questions.papers))
      and (difficulties is null or pg_catalog.cardinality(difficulties) = 0
           or qu.difficulty = any(difficulties))
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

-- --- browse_questions + difficulties ---------------------------------
drop function if exists
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[]);

create function public.browse_questions(
    codes text[],
    kind text default 'all',
    years integer[] default null,
    sessions text[] default null,
    variants integer[] default null,
    subjects text[] default null,
    max_results integer default 20,
    skip integer default 0,
    papers integer[] default null,
    difficulties integer[] default null
)
returns table (
    filename text, subject_name text, year integer, session text, paper integer,
    variant integer, question_number integer, question_text text, answer_text text,
    marks integer, has_figure boolean, topic_codes text[], crop_count integer,
    answer_crop_count integer, difficulty smallint, total_count bigint
)
language sql
stable
set search_path = ''
as $$
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes, qu.crop_count, qu.answer_crop_count,
           qu.difficulty,
           pg_catalog.count(*) over () as total_count
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
    where qu.topic_codes && codes
      and (
            coalesce(kind, 'all') = 'all'
         or (kind = 'mcq'    and qu.is_mcq)
         or (kind = 'theory' and not qu.is_mcq)
      )
      and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
      and (sessions is null or pg_catalog.cardinality(sessions) = 0 or p.session = any(sessions))
      and (variants is null or pg_catalog.cardinality(variants) = 0 or p.variant = any(variants))
      and (subjects is null or pg_catalog.cardinality(subjects) = 0
           or p.subject_name = any(subjects))
      and (browse_questions.papers is null or pg_catalog.cardinality(browse_questions.papers) = 0
           or p.paper = any(browse_questions.papers))
      and (difficulties is null or pg_catalog.cardinality(difficulties) = 0
           or qu.difficulty = any(difficulties))
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

-- --- topic_counts + difficulties -------------------------------------
drop function if exists
    public.topic_counts(text, integer[], text[], integer[], text[], text, integer[]);

create function public.topic_counts(
    kind text default 'all',
    years integer[] default null,
    sessions text[] default null,
    variants integer[] default null,
    subjects text[] default null,
    topic_subject text default null,
    papers integer[] default null,
    difficulties integer[] default null
)
returns table (code text, number integer, name text, subsections text[], count bigint)
language sql
stable
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
              and (topic_counts.papers is null or pg_catalog.cardinality(topic_counts.papers) = 0
                   or p.paper = any(topic_counts.papers))
              and (difficulties is null or pg_catalog.cardinality(difficulties) = 0
                   or qu.difficulty = any(difficulties))
        )::bigint as count
    from public.topics t
    where topic_subject is null or t.subject = topic_subject
    order by t.number;
$$;

-- --- grants ------------------------------------------------------
revoke all on function
    public.search_questions(text, integer, text, integer[], text[], integer[], text[], integer[],
                            integer[])
    from public, anon;
revoke all on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[], integer[])
    from public, anon;
revoke all on function
    public.topic_counts(text, integer[], text[], integer[], text[], text, integer[], integer[])
    from public, anon;
grant execute on function
    public.search_questions(text, integer, text, integer[], text[], integer[], text[], integer[],
                            integer[])
    to authenticated;
grant execute on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[], integer[])
    to authenticated;
grant execute on function
    public.topic_counts(text, integer[], text[], integer[], text[], text, integer[], integer[])
    to authenticated;

notify pgrst, 'reload schema';
