-- 0011 -- Chemistry 9701 (Papers 1 & 2) as a sixth subject
--
-- papers.subject_name now takes six values. New this migration:
--   ch01..ch22  Chemistry  (9701 Papers 1 & 2 -- one taxonomy, like Physics,
--               since both papers examine the same full AS syllabus content)
--
-- The only schema change is widening the topic-code CHECK to the union of all
-- six taxonomies. Everything else already exists:
--   * questions.is_mcq (0008) -- 9701 P1 is MCQ, published true; P2 structured,
--     published false. Chemistry is the second subject (after Physics) where
--     this actually varies within a subject.
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
        'ps1','ps2','ps3','ps4','ps5',
        'ch01','ch02','ch03','ch04','ch05','ch06','ch07','ch08','ch09','ch10',
        'ch11','ch12','ch13','ch14','ch15','ch16','ch17','ch18','ch19','ch20',
        'ch21','ch22'
    ]::text[]
);

notify pgrst, 'reload schema';
