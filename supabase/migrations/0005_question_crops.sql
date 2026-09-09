-- Paper Finder — carry the per-question crop count to the cloud, and stand up
-- the private Storage bucket the rendered question images live in.
--
-- Local side: `paper-finder figures` renders one PNG per page-region of every
-- question into data/crops/<stem>/q<NN>_p<K>.png. `paper-finder publish` now
-- carries questions.crop_count so the browser knows how many images a card has
-- WITHOUT probing storage; `paper-finder publish-figures` uploads the PNGs.
--
-- The bucket is private (public = false): an object is only reachable through a
-- signed URL, and a signed URL is only mintable by a session that passed the
-- email-code gate. anon gets nothing — the same access model as
-- public.papers/questions (0001).
--
-- Conventions carried from 0001–0004: `security invoker` + `set search_path =
-- ''` on every function; every column table-qualified; `revoke all … from
-- public, anon` then `grant execute … to authenticated`; `drop function` before
-- any return-type change (adding an OUT column changes the return type, which
-- CREATE OR REPLACE forbids); `notify pgrst, 'reload schema'` last.

-- --- crop_count on the question row ------------------------------------
alter table public.questions
    add column if not exists crop_count integer not null default 0;

-- --- browse RPC: + crop_count OUT column ------------------------------
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
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

-- --- search_questions: + crop_count OUT column ----------------------
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
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

-- --- grants (unchanged shape, re-applied for the recreated functions) --
revoke all on function public.browse_questions(text[], text, integer[], text[], integer, integer)
    from public, anon;
revoke all on function public.search_questions(text, integer, text)   from public, anon;
grant execute on function public.browse_questions(text[], text, integer[], text[], integer, integer)
    to authenticated;
grant execute on function public.search_questions(text, integer, text)   to authenticated;

-- --- private Storage bucket for the question crops ------------------
insert into storage.buckets (id, name, public)
    values ('question-crops', 'question-crops', false)
    on conflict (id) do nothing;

drop policy if exists "authenticated read crops" on storage.objects;
create policy "authenticated read crops" on storage.objects
    for select to authenticated using (bucket_id = 'question-crops');

notify pgrst, 'reload schema';
