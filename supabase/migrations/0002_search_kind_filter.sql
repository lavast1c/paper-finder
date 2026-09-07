-- Paper Finder — add an MCQ / Theory filter to the deployed search.
--
-- `search_questions` gains a third argument, `kind`:
--   'all'    — every question type (default; unchanged behaviour)
--   'mcq'    — multiple-choice papers only  (CIE 9702 Paper 1)
--   'theory' — structured papers only       (Paper 2 and any other non-1 paper)
--
-- The cloud `questions` table has no per-question `is_mcq` flag (dropped on
-- publish), so the split is by paper number: Paper 1 is the multiple-choice
-- paper, everything else is structured.

-- The signature changes (2 args -> 3), so drop the old overload first rather
-- than leaving PostgREST two functions of the same name to disambiguate.
drop function if exists public.search_questions(text, integer);

create or replace function public.search_questions(
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
      and (
            coalesce(kind, 'all') = 'all'
         or (kind = 'mcq'    and p.paper = 1)
         or (kind = 'theory' and p.paper is not null and p.paper <> 1)
      )
    order by pg_catalog.ts_rank_cd(qu.question_search, tsq.tq, 33) desc,
             p.filename, qu.question_number
    limit least(greatest(coalesce(max_results, 5), 1), 50);
$$;

revoke all on function public.search_questions(text, integer, text) from public, anon;
grant execute on function public.search_questions(text, integer, text) to authenticated;

notify pgrst, 'reload schema';
