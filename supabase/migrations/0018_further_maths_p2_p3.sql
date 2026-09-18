-- 0018 -- Further Mathematics 9231 Papers 2 and 3 (the A Level half of 9231)
--
-- papers.subject_name now takes fourteen values. New this migration:
--   fp21..fp26  Further Pure Mathematics 2  (9231 Paper 2)
--   fm1..fm6    Further Mechanics           (9231 Paper 3)
-- Each is its own single-paper taxonomy, same disjoint-content shape as the
-- existing Further Pure Mathematics (9231 P1) / Further Probability &
-- Statistics (9231 P4) split -- not one taxonomy spanning several papers.
-- These two are A Level rather than AS Level, joining the three 9709 A Level
-- subjects added in 0014 (fp2x extends the existing fp family the same way
-- pm3x extends pm; fm is a new, previously-unclaimed prefix since Further
-- Mechanics has no existing 9231 family to extend).
--
-- The only schema change is widening the topic-code CHECK to the union of all
-- fourteen taxonomies. Everything else already exists:
--   * questions.is_mcq (0008) -- both new papers are structured, so every
--     question published from them has is_mcq = false, same as 9231 P1/P4.
--   * topics.subject (0008) -- public.topics rows are (re)seeded by
--     `paper-finder publish` from paper_finder.topics.ALL_TOPICS, not here.
--   * search_questions / browse_questions / topic_counts already take the
--     generic `subjects text[]` filter (0008) and the trailing `papers
--     integer[]` filter (0016) -- no signature change, so no function
--     rewrite. Each new subject is its own single-paper taxonomy (like 9709
--     P3/P4/P6 in 0014), not a Computer-Science-style Topic.papers split, so
--     the browser's Paper(s) filter stays hidden for them.

alter table public.questions drop constraint if exists questions_topic_codes_valid;
alter table public.questions add constraint questions_topic_codes_valid check (
    topic_codes <@ array[
        's01','s02','s03','s04','s05','s06','s07','s08','s09','s10','s11',
        'fp1','fp2','fp3','fp4','fp5','fp6','fp7',
        'fs1','fs2','fs3','fs4','fs5',
        'fp21','fp22','fp23','fp24','fp25','fp26',
        'fm1','fm2','fm3','fm4','fm5','fm6',
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
        'ec01','ec02','ec03','ec04','ec05','ec06',
        'cs01','cs02','cs03','cs04','cs05','cs06','cs07','cs08','cs09','cs10',
        'cs11','cs12'
    ]::text[]
);

notify pgrst, 'reload schema';
