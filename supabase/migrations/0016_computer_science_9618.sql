-- 0016 -- Computer Science 9618 + a paper-number filter
--
-- papers.subject_name gains "Computer Science" (9618 Papers 1 & 2, one subject
-- with one taxonomy, cs01..cs12). Two schema changes:
--
-- 1. Widen questions_topic_codes_valid to the union of all twelve taxonomies.
--
-- 2. search_questions / browse_questions / topic_counts gain a trailing
--    `papers integer[]` filter on papers.paper. Both 9618 papers are
--    structured, so the existing `kind` (is_mcq) filter can't tell them apart,
--    and `variants` only holds the second digit of `_12`. The syllabus splits
--    9618 content by paper (P1 = sections 1-8, P2 = 9-12), so the browser's
--    Paper(s) filter sends this for Computer Science. Default null = no
--    restriction, so existing callers are unaffected. Bodies are otherwise
--    verbatim from 0008 (search/browse) and 0009 (topic_counts). The old
--    signatures are dropped first so the new ones aren't ambiguous overloads,
--    and grants are explicit since 0015 removed the default EXECUTE grants.

alter table public.questions drop constraint if exists questions_topic_codes_valid;
alter table public.questions add constraint questions_topic_codes_valid check (
    topic_codes <@ array[
        's01','s02','s03','s04','s05','s06','s07','s08','s09','s10','s11',
        'fp1','fp2','fp3','fp4','fp5','fp6','fp7',
        'fs1','fs2','fs3','fs4','fs5',
        'pm1','pm2','pm3','pm4','pm5','pm6','pm7','pm8',
        'ps1','ps2','ps3','ps4','ps5',
        'pm31','pm32','pm33','pm34','pm35','pm36','pm37','pm38','pm39',
        'mc1','mc2','mc3','mc4','mc5',
        'ps21','ps22','ps23','ps24','ps25',
        'ch01','ch02','ch03','ch04','ch05','ch06','ch07','ch08','ch09','ch10',
        'ch11','ch12','ch13','ch14','ch15','ch16','ch17','ch18','ch19','ch20',
        'ch21','ch22',
        'bi01','bi02','bi03','bi04','bi05','bi06','bi07','bi08','bi09','bi10',
        'bi11',
        'ec01','ec02','ec03','ec04','ec05','ec06',
        'cs01','cs02','cs03','cs04','cs05','cs06','cs07','cs08','cs09','cs10',
        'cs11','cs12'
    ]::text[]
);

-- --- search_questions + papers --------------------------------------
drop function if exists
    public.search_questions(text, integer, text, integer[], text[], integer[], text[]);

create function public.search_questions(
        query       text,
        max_results integer   default 5,
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null,
        subjects    text[]    default null,
        papers      integer[] default null
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
      and (search_questions.papers is null or pg_catalog.cardinality(search_questions.papers) = 0
           or p.paper = any(search_questions.papers))
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

-- --- browse_questions + papers --------------------------------------
drop function if exists
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer);

create function public.browse_questions(
        codes       text[],
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
        variants    integer[] default null,
        subjects    text[]    default null,
        max_results integer   default 20,
        skip        integer   default 0,
        papers      integer[] default null
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
      and (browse_questions.papers is null or pg_catalog.cardinality(browse_questions.papers) = 0
           or p.paper = any(browse_questions.papers))
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

-- --- topic_counts + papers ------------------------------------------
drop function if exists
    public.topic_counts(text, integer[], text[], integer[], text[], text);

create function public.topic_counts(
        kind          text      default 'all',
        years         integer[] default null,
        sessions      text[]    default null,
        variants      integer[] default null,
        subjects      text[]    default null,
        topic_subject text      default null,
        papers        integer[] default null
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
              and (topic_counts.papers is null or pg_catalog.cardinality(topic_counts.papers) = 0
                   or p.paper = any(topic_counts.papers))
        )::bigint as count
    from public.topics t
    where topic_subject is null or t.subject = topic_subject
    order by t.number;
$$;

-- --- grants ------------------------------------------------------
revoke all on function
    public.search_questions(text, integer, text, integer[], text[], integer[], text[], integer[])
    from public, anon;
revoke all on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[])
    from public, anon;
revoke all on function
    public.topic_counts(text, integer[], text[], integer[], text[], text, integer[])
    from public, anon;
grant execute on function
    public.search_questions(text, integer, text, integer[], text[], integer[], text[], integer[])
    to authenticated;
grant execute on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[])
    to authenticated;
grant execute on function
    public.topic_counts(text, integer[], text[], integer[], text[], text, integer[])
    to authenticated;

notify pgrst, 'reload schema';
