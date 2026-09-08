-- Paper Finder — carry the "this question leans on a diagram" flag to the cloud.
--
-- `questions.has_figure` is set locally during `segment` (a text heuristic:
-- "Fig. 1.1", "the diagram shows", "the graph shows the variation", "Table 7.1"
-- …). The deployed UI shows a "◧ Has a diagram, graph or table — see the
-- original paper" note on those results. `paper-finder publish` now writes the
-- column; add it here and return it from `search_questions`.

alter table public.questions
    add column if not exists has_figure boolean not null default false;

-- adding an OUT column changes the return type, which CREATE OR REPLACE forbids
drop function if exists public.search_questions(text, integer, text);

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
        marks           integer,
        has_figure      boolean
    )
    language sql
    stable
    security invoker
    set search_path = ''
as $$
    with tsq as (select public.or_tsquery(query) as tq)
    select p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
           qu.question_number, qu.question_text, qu.answer_text, qu.marks,
           qu.has_figure
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
