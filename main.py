import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from tqdm import tqdm

from config import CRON_SCHEDULE, RUN_ONCE, VIDEO_COUNT, require_gemini_api_key
from logging_setup import configure_logging
from utils.audio import generate_voiceover
from utils.cartoon import generate_scene_images
from utils.llm import (
    get_description,
    get_most_engaging_titles,
    get_script,
    get_titles,
    get_topic,
    get_visual_prompts,
)
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

    visual_prompts = get_visual_prompts(title, script, topic)
    logger.info("[Generated Visual Prompts]")
    logger.info(visual_prompts)

    scene_images = generate_scene_images(visual_prompts)
    logger.info("[Generated Cartoon Scenes]")

    voiceover = generate_voiceover(script)
    logger.info("[Generated Voiceover]")

    return title, description, script, visual_prompts, scene_images, voiceover


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
                    visual_prompts,
                    scene_images,
                    voiceover,
                ) = generate_video_data(title, topic)

                logging.debug(f"Title: {title}")
                logging.debug(f"Description: {description}")
                logging.debug(f"Script: {script}")
                logging.debug(f"Visual prompts: {visual_prompts}")
                logging.debug(f"Scene images: {scene_images}")
                logging.debug(f"Voiceover: {voiceover}")

                video, credits = generate_video(scene_images, voiceover, script, visual_prompts)
                logger.info("[Generated Video]")

                if credits:
                    description = description + "\n\n" + "\n".join(credits)

                new_video_file = save_metadata(
                    title, description, None, script, visual_prompts, video
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
