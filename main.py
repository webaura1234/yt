import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from tqdm import tqdm

from config import CRON_SCHEDULE, RUN_ONCE, VIDEO_COUNT, require_gemini_api_key
from logging_setup import configure_logging
from utils.audio import generate_voiceover
from utils.llm import (
    _generate,
    get_description,
    get_most_engaging_titles,
    get_script,
    get_titles,
    get_topic,
)
from utils.storyboard import brief_rows, build_storyboard, storyboard_table
from utils.visual_director import direct_scenes, framing_report, unresolved_scenes
from utils.metadata import save_metadata
from utils.notifications import send_error_notification, send_success_notification
from utils.video import generate_video
from utils.yt import auto_upload

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_video_data(title, topic=""):
    logger.info("[Generated Title]")
    logger.info(title)

    script = get_script(title, topic)
    logger.info("[Generated Script]")
    logger.info(script)

    description = get_description(title, script)
    logger.info("[Generated Description]")
    logger.info(description)

    # Read every narration line before searching for anything: subject, action,
    # location, mood, and several competing queries per line.
    briefs = build_storyboard(title, script, generate=_generate)
    logger.info("[Storyboard]")
    for brief in briefs:
        logger.info(f"  {brief.index + 1}. {brief.summary()} | queries: {brief.queries[:3]}")

    # Search, score, frame and review each scene until it earns its place.
    selections = direct_scenes(briefs)

    # The storyboard table goes out BEFORE rendering, while the shot choices are
    # still cheap to change.
    logger.info("[Storyboard Review]")
    logger.info(
        "\n" + storyboard_table(brief_rows(briefs, [s.table_row() for s in selections]))
    )
    logger.info("\n" + framing_report(selections))

    weak = unresolved_scenes(selections)
    if weak:
        # Loud, and named. The old pipeline quietly dropped generic B-roll into
        # these slots, which is the failure this whole stage exists to remove.
        logger.error(
            f"{len(weak)}/{len(selections)} scenes found no footage that "
            "represents their narration:"
        )
        for scene in weak:
            logger.error(f"  - {scene.brief.sentence[:70]}")

    queries = [q for brief in briefs for q in brief.queries[:1]]

    voiceover = generate_voiceover(script)
    logger.info("[Generated Voiceover]")

    return title, description, script, queries, selections, voiceover


def generate_videos(n: int = 4) -> None:
    try:
        topic = get_topic()

        logger.info("[Generated Topic]")
        logger.info(topic)

        possible_titles = get_titles(topic)
        logger.info("[Generated Possible Titles]")
        logger.info(possible_titles)

        titles = get_most_engaging_titles(possible_titles, n)

        videos_generated = 0
        for title in tqdm(titles, desc="Generating videos"):
            try:
                (
                    title,
                    description,
                    script,
                    queries,
                    selections,
                    voiceover,
                ) = generate_video_data(title, topic)

                logging.debug(f"Title: {title}")
                logging.debug(f"Description: {description}")
                logging.debug(f"Script: {script}")
                logging.debug(f"Search queries: {queries}")
                logging.debug(f"Scene selections: {selections}")
                logging.debug(f"Voiceover: {voiceover}")

                video, credits = generate_video(selections, voiceover, script, queries)
                logger.info("[Generated Video]")

                if credits:
                    description = description + "\n\n" + "\n".join(credits)

                new_video_file = save_metadata(
                    title, description, None, script, queries, video
                )
                logger.info("[Saved Video]")

                auto_upload(new_video_file, title, description)
                logger.info("[Uploaded Video]")
                videos_generated += 1

            except Exception as e:
                error_msg = f"Failed to generate/upload video '{title}'"
                logger.error(f"{error_msg}: {e}")
                send_error_notification(error_msg, e, "Video Generation")

        if videos_generated > 0:
            success_msg = (
                f"Successfully generated and uploaded {videos_generated} video(s)"
            )
            logger.info(success_msg)
            send_success_notification(success_msg, "Video Generation")
        else:
            error_msg = "No videos were successfully generated"
            logger.error(error_msg)
            send_error_notification(error_msg, context="Video Generation")

    except Exception as e:
        error_msg = "Failed to start video generation process"
        logger.error(f"{error_msg}: {e}")
        send_error_notification(error_msg, e, "Video Generation")


def main():
    # The generator can't do anything without this, so fail immediately and say
    # how to fix it rather than dying mid-pipeline on the first API call.
    require_gemini_api_key()

    cron_schedule = CRON_SCHEDULE
    run_once = RUN_ONCE
    video_count = VIDEO_COUNT

    if run_once:
        logger.info("RUN_ONCE is enabled, generating videos immediately...")
        generate_videos(video_count)
        logger.info("Video generation completed. Exiting.")
        return

    logger.info(f"Starting scheduler with cron schedule: {cron_schedule}")
    scheduler = BlockingScheduler()

    trigger = CronTrigger.from_crontab(cron_schedule)
    scheduler.add_job(
        func=generate_videos, trigger=trigger, args=[video_count], id="video_generation"
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        scheduler.shutdown()
    except Exception as e:
        error_msg = "Scheduler failed unexpectedly"
        logger.error(f"{error_msg}: {e}")
        send_error_notification(error_msg, e, "Scheduler")


if __name__ == "__main__":
    main()
