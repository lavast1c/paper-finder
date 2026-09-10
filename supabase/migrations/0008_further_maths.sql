-- Paper Finder — Further Mathematics 9231 (Papers 1 & 4) as two more subjects.
--
-- The corpus is no longer single-subject. papers.subject_name now takes three
-- values — 'Physics', 'Further Pure Mathematics' (9231 P1), 'Further
-- Probability & Statistics' (9231 P4) — each with its own syllabus taxonomy:
--   s01..s11  Physics
--   fp1..fp7  Further Pure Mathematics
--   fs1..fs5  Further Probability & Statistics
--
-- Changes here:
--   1. questions.is_mcq — published from the local bank so `kind` can stop
--      guessing from p.paper. 9231 Paper 1 is structured, NOT multiple choice,
--      so the old `p.paper = 1` test was wrong for it.
--   2. topic_codes CHECK widened to the union of all three taxonomies.
--   3. topics.subject — which taxonomy a row belongs to (matches subject_name).
--   4. search_questions / browse_questions / topic_counts gain a `subjects
--      text[]` filter (p.subject_name = any(subjects) when non-empty); the
--      Subject dropdown sends one value so search stays within one subject.
--      topic_counts also takes a scalar `subject` to filter the topic LIST
--      (public.topics.subject) to that taxonomy.
--   5. all three `kind` predicates switch from `p.paper = 1` to `qu.is_mcq`.
--
-- Adding params / OUT columns changes each signature -> drop-then-create (not
-- CREATE OR REPLACE). Conventions carried from 0001–0007: `security invoker` +
-- `set search_path = ''`; every column table-qualified; `revoke all … from
-- public, anon` then `grant execute … to authenticated`; `notify pgrst,
-- 'reload schema'` last.

-- --- 1. is_mcq on the (flat) question row ---------------------------
alter table public.questions
    add column if not exists is_mcq boolean not null default false;

-- --- 2. widen the topic-code CHECK to the union of all taxonomies ---
alter table public.questions drop constraint if exists questions_topic_codes_valid;
alter table public.questions add constraint questions_topic_codes_valid check (
    topic_codes <@ array[
        's01','s02','s03','s04','s05','s06','s07','s08','s09','s10','s11',
        'fp1','fp2','fp3','fp4','fp5','fp6','fp7',
        'fs1','fs2','fs3','fs4','fs5'
    ]::text[]
);

-- --- 3. topics.subject --------------------------------------------
alter table public.topics
    add column if not exists subject text not null default 'Physics';

-- --- 4 + 5. search_questions: + subjects, is_mcq kind -------------
drop function if exists public.search_questions(text, integer, text, integer[], text[], integer[]);

create function public.search_questions(
        query       text,
        max_results integer   default 5,
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null,
        subjects    text[]    default null
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
         or (kind = 'mcq'    and qu.is_mcq)
         or (kind = 'theory' and not qu.is_mcq)
      )
      and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
      and (sessions is null or pg_catalog.cardinality(sessions) = 0 or p.session = any(sessions))
      and (variants is null or pg_catalog.cardinality(variants) = 0 or p.variant = any(variants))
      and (subjects is null or pg_catalog.cardinality(subjects) = 0
           or p.subject_name = any(subjects))
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

-- --- 4 + 5. browse_questions: + subjects, is_mcq kind ------------
drop function if exists
    public.browse_questions(text[], text, integer[], text[], integer[], integer, integer);

create function public.browse_questions(
        codes       text[],
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null,
        subjects    text[]    default null,
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
         or (kind = 'mcq'    and qu.is_mcq)
         or (kind = 'theory' and not qu.is_mcq)
      )
      and (years is null or pg_catalog.cardinality(years) = 0 or p.year = any(years))
      and (sessions is null or pg_catalog.cardinality(sessions) = 0 or p.session = any(sessions))
      and (variants is null or pg_catalog.cardinality(variants) = 0 or p.variant = any(variants))
      and (subjects is null or pg_catalog.cardinality(subjects) = 0
           or p.subject_name = any(subjects))
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

-- --- 4 + 5. topic_counts: + subjects (counts) + subject (topic list) --
drop function if exists public.topic_counts(text, integer[], text[], integer[]);

create function public.topic_counts(
        kind     text      default 'all',
        years    integer[] default null,
        sessions text[]    default null,
        variants integer[] default null,
        subjects text[]    default null,
        subject  text      default null
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
    where subject is null or t.subject = subject
    order by t.number;
$$;

-- --- grants ------------------------------------------------------
revoke all on function
    public.search_questions(text, integer, text, integer[], text[], integer[], text[])
    from public, anon;
revoke all on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer)
    from public, anon;
revoke all on function
    public.topic_counts(text, integer[], text[], integer[], text[], text)
    from public, anon;
grant execute on function
    public.search_questions(text, integer, text, integer[], text[], integer[], text[])
    to authenticated;
grant execute on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer)
    to authenticated;
grant execute on function
    public.topic_counts(text, integer[], text[], integer[], text[], text)
    to authenticated;

notify pgrst, 'reload schema';
