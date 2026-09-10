-- 0010 -- Mathematics 9709 (Papers 1 & 5) as two more subjects
--
-- papers.subject_name now takes five values. New this migration:
--   pm1..pm8  Pure Mathematics 1          (9709 Paper 1)
--   ps1..ps5  Probability & Statistics 1  (9709 Paper 5)
--
-- The only schema change is widening the topic-code CHECK to the union of all
-- five taxonomies. Everything else already exists:
--   * questions.is_mcq (0008) -- 9709 P1 & P5 are structured, published false.
--   * topics.subject (0008) -- public.topics rows are (re)seeded by
--     `paper-finder publish` from paper_finder.topics.ALL_TOPICS, not here.
--   * search_questions / browse_questions / topic_counts already take the
--     generic `subjects text[]` filter (0008) and topic_counts the scalar
--     `topic_subject` (0009) -- no signature change, so no function rewrite.

alter table public.questions drop constraint if exists questions_topic_codes_valid;
alter table public.questions add constraint questions_topic_codes_valid check (
    topic_codes <@ array[
        's01','s02','s03','s04','s05','s06','s07','s08','s09','s10','s11',
        'fp1','fp2','fp3','fp4','fp5','fp6','fp7',
        'fs1','fs2','fs3','fs4','fs5',
        'pm1','pm2','pm3','pm4','pm5','pm6','pm7','pm8',
        'ps1','ps2','ps3','ps4','ps5'
    ]::text[]
);

notify pgrst, 'reload schema';
