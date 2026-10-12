-- 0020 -- sort the browse deck by difficulty
--
-- browse_questions gains a trailing `sort text default 'newest'`:
--   'newest'  -> newest paper first (the existing order, unchanged default)
--   'easiest' -> difficulty ascending, then newest paper first
--   'hardest' -> difficulty descending, then newest paper first
-- Unrated questions (difficulty null) sort last either way. Any other value
-- behaves like 'newest'. Body is otherwise verbatim from 0019. A new parameter
-- would leave an ambiguous overload, so the old signature is dropped first;
-- grants are explicit since 0015 removed the default EXECUTE grants.

drop function if exists
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[], integer[]);

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
    difficulties integer[] default null,
    sort text default 'newest'
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
    order by case when sort = 'easiest' then qu.difficulty end asc nulls last,
             case when sort = 'hardest' then qu.difficulty end desc nulls last,
             p.year desc, p.session desc, p.paper, p.variant, qu.question_number
    limit least(greatest(coalesce(max_results, 20), 1), 50)
    offset greatest(coalesce(skip, 0), 0);
$$;

revoke all on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[], integer[], text)
    from public, anon;
grant execute on function
    public.browse_questions(text[], text, integer[], text[], integer[], text[], integer, integer,
                            integer[], integer[], text)
    to authenticated;

notify pgrst, 'reload schema';
