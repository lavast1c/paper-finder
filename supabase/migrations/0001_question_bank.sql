-- Paper Finder — public question index for the deployed (Vercel) web UI.
--
-- Holds ONLY: filename-derived paper metadata + question text + answer text.
-- No PDFs, no source URLs, no download log. The PDFs and the local SQLite
-- question bank never leave the author's machine. Populated by
-- `paper-finder publish` (replace-all). Contains no paper content in git — this
-- file is schema only.
--
-- Access model: every signed-in user (email one-time-code via Supabase Auth) may
-- read the whole corpus. anon may read nothing. "Allow all emails for now" — to
-- add an email allowlist later, swap `using (true)` for `(select
-- private.is_member())` and add that table + SECURITY DEFINER helper.

create table if not exists public.papers (
    id           integer primary key,      -- carried over from local SQLite
    subject_code text    not null,
    subject_name text,
    year         integer not null,
    session      text    not null check (session in ('s', 'w', 'm')),
    paper        integer,
    variant      integer,
    filename     text    not null unique
);

create table if not exists public.questions (
    id              integer primary key,   -- carried over from local SQLite
    paper_id        integer not null references public.papers (id) on delete cascade,
    question_number integer not null,
    question_text   text    not null,
    answer_text     text,                  -- flattened from the local answers table
    marks           integer,
    question_search tsvector
        generated always as (to_tsvector('pg_catalog.english', question_text)) stored,
    unique (paper_id, question_number)
);

create index if not exists questions_search_idx on public.questions using gin (question_search);
create index if not exists questions_paper_id_idx on public.questions (paper_id);

-- --- Row Level Security -------------------------------------------------------
-- `to authenticated using (true)` is deliberate: this is shared read-only
-- reference data, not user-owned rows, so every authenticated user should see
-- all of it. (The BOLA/IDOR caveat about `using(true)` concerns per-user data.)
alter table public.papers    enable row level security;
alter table public.questions enable row level security;

drop policy if exists "authenticated read" on public.papers;
drop policy if exists "authenticated read" on public.questions;
create policy "authenticated read" on public.papers
    for select to authenticated using (true);
create policy "authenticated read" on public.questions
    for select to authenticated using (true);

grant select on public.papers    to authenticated;
grant select on public.questions to authenticated;
revoke all on public.papers    from anon;
revoke all on public.questions from anon;

-- --- Search ------------------------------------------------------------------
-- OR-combine the query words over the same [0-9a-z] tokenisation the local
-- SQLite side uses. websearch_to_tsquery ANDs terms — one mis-remembered word
-- would then return nothing, which is the opposite of what a "half-remembered
-- question" tool needs. quote_literal + the [^0-9a-z] split make it injection
-- proof; plainto_tsquery(...) <> '' drops stop words before to_tsquery sees them.
create or replace function public.or_tsquery(q text)
    returns tsquery
    language sql
    immutable
    set search_path = ''
as $$
    select pg_catalog.to_tsquery(
        'pg_catalog.english',
        pg_catalog.array_to_string(
            array(
                select pg_catalog.quote_literal(t)
                from pg_catalog.unnest(
                    pg_catalog.regexp_split_to_array(
                        pg_catalog.lower(coalesce(q, '')), '[^0-9a-z]+'
                    )
                ) as t
                where t <> ''
                  and pg_catalog.plainto_tsquery('pg_catalog.english', t) <> ''::pg_catalog.tsquery
            ),
            ' | '
        )
    );
$$;

-- SECURITY INVOKER: runs as the caller, so the RLS policies above apply inside
-- the function. anon has no EXECUTE grant and, even if it did, would get zero
-- rows. Every column reference is table-qualified because RETURNS TABLE columns
-- are OUT parameters in scope in the body; `questions` is aliased `qu` so it
-- cannot collide with the `tsq` CTE.
create or replace function public.search_questions(query text, max_results integer default 5)
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
        marks           integer
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    with tsq as (select public.or_tsquery(query) as tq)
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
        cross join tsq
    where tsq.tq <> ''::pg_catalog.tsquery
      and qu.question_search @@ tsq.tq
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

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
        'subjects',        coalesce(
            (select pg_catalog.json_agg(distinct subject_name order by subject_name)
             from public.papers where subject_name is not null),
            '[]'::json
        )
    );
$$;

-- Anon-callable, reads nothing. The Vercel cron hits /api/health daily, which
-- calls this, so the free Supabase project does not hit its 7-day idle pause.
create or replace function public.ping()
    returns text
    language sql
    immutable
    set search_path = ''
as $$
    select 'ok'::text;
$$;

revoke all on function public.search_questions(text, integer) from public, anon;
revoke all on function public.corpus_stats()                   from public, anon;
grant execute on function public.search_questions(text, integer) to authenticated;
grant execute on function public.corpus_stats()                  to authenticated;
grant execute on function public.ping()                          to anon, authenticated;
