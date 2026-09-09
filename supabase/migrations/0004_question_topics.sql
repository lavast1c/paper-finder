-- Paper Finder — carry the syllabus-topic labels to the cloud, and add the
-- topic-browse (flashcard) RPCs the deployed /topics page calls.
--
-- Local side: `paper-finder topics` loads labels/question_topics.tsv into a
-- question_topics join table. The cloud index has no join table — `publish`
-- does DELETE public.papers (cascade) then a single bulk re-insert, so the
-- labels ride along as a `text[]` column on the question row: one sync path
-- that cannot desync from its question. A CHECK constraint listing the 11
-- section codes stands in for the FK a join table would have given; the
-- taxonomy is fixed reference data on a multi-year syllabus cycle.
--
-- Conventions carried from 0001–0003: `security invoker` + `set search_path =
-- ''` on every function; every column table-qualified; `revoke all … from
-- public, anon` then `grant execute … to authenticated`; `drop function`
-- before any return-type change; `notify pgrst, 'reload schema'` last.

-- --- taxonomy table --------------------------------------------------------
-- Display names/subsections shown by the UI come from this table in cloud
-- mode (there is no paper_finder.topics import on Vercel's fastapi-only
-- chain). `publish` upserts it from paper_finder.topics on every run, so that
-- module stays the single source of truth even though the seed below also
-- populates it on a fresh database.
create table if not exists public.topics (
    code        text    primary key,
    number      integer not null,
    name        text    not null,
    subsections text[]  not null default '{}'
);

insert into public.topics (code, number, name, subsections) values
    ('s01', 1, 'Physical quantities and units',
        array['1.1 Physical quantities', '1.2 SI units',
              '1.3 Errors and uncertainties', '1.4 Scalars and vectors']),
    ('s02', 2, 'Kinematics',
        array['2.1 Equations of motion']),
    ('s03', 3, 'Dynamics',
        array['3.1 Momentum and Newton''s laws of motion', '3.2 Non-uniform motion',
              '3.3 Linear momentum and its conservation']),
    ('s04', 4, 'Forces, density and pressure',
        array['4.1 Turning effects of forces', '4.2 Equilibrium of forces',
              '4.3 Density and pressure']),
    ('s05', 5, 'Work, energy and power',
        array['5.1 Energy conservation',
              '5.2 Gravitational potential energy and kinetic energy']),
    ('s06', 6, 'Deformation of solids',
        array['6.1 Stress and strain', '6.2 Elastic and plastic behaviour']),
    ('s07', 7, 'Waves',
        array['7.1 Progressive waves', '7.2 Transverse and longitudinal waves',
              '7.3 Doppler effect for sound waves', '7.4 Electromagnetic spectrum',
              '7.5 Polarisation']),
    ('s08', 8, 'Superposition',
        array['8.1 Stationary waves', '8.2 Diffraction', '8.3 Interference',
              '8.4 The diffraction grating']),
    ('s09', 9, 'Electricity',
        array['9.1 Electric current', '9.2 Potential difference and power',
              '9.3 Resistance and resistivity']),
    ('s10', 10, 'D.C. circuits',
        array['10.1 Practical circuits', '10.2 Kirchhoff''s laws',
              '10.3 Potential dividers']),
    ('s11', 11, 'Particle physics',
        array['11.1 Atoms, nuclei and radiation', '11.2 Fundamental particles'])
on conflict (code) do update set
    number = excluded.number, name = excluded.name, subsections = excluded.subsections;

-- --- topic_codes on the question row -------------------------------------
alter table public.questions
    add column if not exists topic_codes text[] not null default '{}';

alter table public.questions drop constraint if exists questions_topic_codes_valid;
alter table public.questions add constraint questions_topic_codes_valid
    check (topic_codes <@ array[
        's01', 's02', 's03', 's04', 's05', 's06',
        's07', 's08', 's09', 's10', 's11'
    ]::text[]);

-- GIN array_ops serves both `&&` (overlap → union for browse) and `@>`
-- (containment → per-topic counts).
create index if not exists questions_topic_codes_idx
    on public.questions using gin (topic_codes);

-- --- Row Level Security ---------------------------------------------------
-- Shared read-only reference data, same model as public.papers/questions.
alter table public.topics enable row level security;
drop policy if exists "authenticated read" on public.topics;
create policy "authenticated read" on public.topics
    for select to authenticated using (true);
grant select on public.topics to authenticated;
revoke all on public.topics from anon;

-- --- browse RPC --------------------------------------------------------
-- Every question tagged with ANY of `codes` (union via &&), newest paper
-- first. `count(*) over ()` is evaluated after WHERE and before LIMIT, so it
-- is the full match count on every row and one round trip fills the pager —
-- this holds only while the query has no GROUP BY. The parameter is `codes`,
-- not `topic_codes`, so it does not shadow the RETURNS TABLE OUT column.
drop function if exists public.browse_questions(text[], text, integer[], text[], integer, integer);

create function public.browse_questions(
        codes       text[],
        kind        text      default 'all',
        years       integer[] default null,
        sessions    text[]    default null,
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
        total_count     bigint
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes,
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
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

-- --- per-topic counts RPC --------------------------------------------
-- One correlated count per section (11 rows, trivial). Every topic is
-- returned even at zero so the chip row stays stable.
drop function if exists public.topic_counts(text, integer[], text[]);

create function public.topic_counts(
        kind     text      default 'all',
        years    integer[] default null,
        sessions text[]    default null
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
        )::bigint as count
    from public.topics t
    order by t.number;
$$;

-- --- corpus_stats gains labelled / unlabelled ------------------------
create or replace function public.corpus_stats()
    returns json
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    select pg_catalog.json_build_object(
        'papers',          (select count(*) from public.papers),
        'question_papers', (select count(*) from public.papers),
        'questions',       (select count(*) from public.questions),
        'answers',         (select count(*) from public.questions where answer_text is not null),
        'labelled',        (select count(*) from public.questions
                            where pg_catalog.cardinality(topic_codes) > 0),
        'unlabelled',      (select count(*) from public.questions
                            where pg_catalog.cardinality(topic_codes) = 0),
        'subjects',        coalesce(
            (select pg_catalog.json_agg(distinct subject_name order by subject_name)
             from public.papers where subject_name is not null),
            '[]'::json
        )
    );
$$;

-- --- search_questions recreated with a topic_codes column ------------
-- adding an OUT column changes the return type, which CREATE OR REPLACE forbids
drop function if exists public.search_questions(text, integer, text);

create function public.search_questions(
        query       text,
        max_results integer default 5,
        kind        text    default 'all'
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
        topic_codes     text[]
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    with tsq as (select public.or_tsquery(query) as tq)
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure, qu.topic_codes
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
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

-- --- grants ----------------------------------------------------------
revoke all on function public.browse_questions(text[], text, integer[], text[], integer, integer)
    from public, anon;
revoke all on function public.topic_counts(text, integer[], text[])   from public, anon;
revoke all on function public.corpus_stats()                          from public, anon;
revoke all on function public.search_questions(text, integer, text)   from public, anon;
grant execute on function public.browse_questions(text[], text, integer[], text[], integer, integer)
    to authenticated;
grant execute on function public.topic_counts(text, integer[], text[])   to authenticated;
grant execute on function public.corpus_stats()                          to authenticated;
grant execute on function public.search_questions(text, integer, text)   to authenticated;

notify pgrst, 'reload schema';
