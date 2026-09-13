-- 0014 -- Mathematics 9709 Papers 3, 4, 6 as three new A Level subjects
--
-- papers.subject_name now takes eleven values. New this migration:
--   pm31..pm39  Pure Mathematics 3   (9709 Paper 3)
--   mc1..mc5    Mechanics            (9709 Paper 4)
--   ps21..ps25  Probability & Statistics 2  (9709 Paper 6)
-- Each is its own single-paper taxonomy, same disjoint-content shape as the
-- existing Pure Mathematics 1 (9709 P1) / Probability & Statistics 1 (9709
-- P5) split -- not one taxonomy spanning several papers. These three are the
-- first subjects that are A Level rather than AS Level (the "Curriculum"
-- filter, previously inert decoration, becomes a real client-side grouping
-- for the first time on this release -- no schema change needed for that,
-- since it only decides which Subject <option>s are shown).
--
-- The only schema change is widening the topic-code CHECK to the union of all
-- eleven taxonomies. Everything else already exists:
--   * questions.is_mcq (0008) -- all three new papers are structured, so
--     every question published from them has is_mcq = false, same as 9709
--     P1/P5 already.
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
        'pm31','pm32','pm33','pm34','pm35','pm36','pm37','pm38','pm39',
        'mc1','mc2','mc3','mc4','mc5',
        'ps21','ps22','ps23','ps24','ps25',
        'ch01','ch02','ch03','ch04','ch05','ch06','ch07','ch08','ch09','ch10',
        'ch11','ch12','ch13','ch14','ch15','ch16','ch17','ch18','ch19','ch20',
        'ch21','ch22',
        'bi01','bi02','bi03','bi04','bi05','bi06','bi07','bi08','bi09','bi10',
        'bi11',
        'ec01','ec02','ec03','ec04','ec05','ec06'
    ]::text[]
);

notify pgrst, 'reload schema';
