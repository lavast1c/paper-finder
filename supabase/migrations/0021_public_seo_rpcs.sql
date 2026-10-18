-- 0021 -- read-only RPCs for the public, crawlable SEO pages
--
-- The app itself stays behind the email-code login (every existing RPC and the
-- three tables remain `authenticated`-only). These four functions are the one
-- deliberate exception: the server renders /cie/... and /papers/... pages from
-- them with the publishable (anon) key so search engines can index question
-- text + answers. They expose exactly what those pages show -- no crop
-- metadata, no ids -- and the crops stay in the private Storage bucket.
--
-- `security definer` because anon has no SELECT on the tables (0015) and RLS
-- only admits `authenticated`; each function is a fixed, parameterised read
-- with `search_path = ''`, so it can't be steered at anything else. Grants are
-- explicit since 0015 removed the default EXECUTE grants.

create or replace function public.public_papers()
returns table (
    filename text, subject_code text, subject_name text, year integer, session text,
    paper integer, variant integer, question_count bigint
)
language sql
stable
security definer
set search_path = ''
as $$
    select p.filename, p.subject_code, p.subject_name, p.year, p.session, p.paper,
           p.variant, pg_catalog.count(qu.id) as question_count
    from public.papers p
        left join public.questions qu on qu.paper_id = p.id
    group by p.id
    order by p.subject_name, p.year desc, p.session desc, p.paper, p.variant;
$$;

create or replace function public.public_topic_counts()
returns table (code text, question_count bigint)
language sql
stable
security definer
set search_path = ''
as $$
    select c.code, pg_catalog.count(*) as question_count
    from public.questions qu
        cross join lateral pg_catalog.unnest(qu.topic_codes) as c(code)
    group by c.code;
$$;

create or replace function public.public_paper_questions(fname text)
returns table (
    question_number integer, question_text text, answer_text text, marks integer,
    is_mcq boolean, topic_codes text[], difficulty smallint
)
language sql
stable
security definer
set search_path = ''
as $$
    select qu.question_number, qu.question_text, qu.answer_text, qu.marks, qu.is_mcq,
           qu.topic_codes, qu.difficulty
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
    where p.filename = fname
    order by qu.question_number;
$$;

create or replace function public.public_topic_questions(
    code text,
    max_results integer default 50,
    skip integer default 0
)
returns table (
    filename text, year integer, session text, paper integer, variant integer,
    question_number integer, question_text text, answer_text text, marks integer,
    is_mcq boolean, difficulty smallint, total_count bigint
)
language sql
stable
security definer
set search_path = ''
as $$
    select p.filename, p.year, p.session, p.paper, p.variant, qu.question_number,
           qu.question_text, qu.answer_text, qu.marks, qu.is_mcq, qu.difficulty,
           pg_catalog.count(*) over () as total_count
    from public.questions qu
        join public.papers p on p.id = qu.paper_id
    where qu.topic_codes @> array[code]
    order by p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 50), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

revoke all on function public.public_papers() from public;
revoke all on function public.public_topic_counts() from public;
revoke all on function public.public_paper_questions(text) from public;
revoke all on function public.public_topic_questions(text, integer, integer) from public;
grant execute on function public.public_papers() to anon, authenticated;
grant execute on function public.public_topic_counts() to anon, authenticated;
grant execute on function public.public_paper_questions(text) to anon, authenticated;
grant execute on function public.public_topic_questions(text, integer, integer)
    to anon, authenticated;

notify pgrst, 'reload schema';
