-- Video-type label for the influence model's F_type factor
-- (classified at registration time by llm_classifier / classify_video_types).
alter table videos add column if not exists video_type text
    check (video_type in ('build', 'rental', 'counter', 'battle'));

-- For true counter videos: the pokemon being countered. Its contribution
-- from this video is zeroed in the forecaster.
alter table videos add column if not exists counter_target text;
