from typing import List

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import flask_site
import logs
import mindlib
import redcap_helpers

################################
############ CONFIG ############

URL_PREFIX = "c2c-retention-dce"

VIDEOS = mindlib.json_to_dict("./content/videos.json")


def transform_logs(log_list: list[dict]) -> str:
    """Transforms a list of log events from our survey pages' JavaScript into something that looks
    more presentable and uses less data than raw JSON. The string returned from this function will
    be uploaded directly to REDCap in plain text.
    """
    # return json.dumps(log_list)  # temp, lots of wasted space and kinda ugly
    result = []
    for log_line in log_list:
        if "tm" in log_line and "type" in log_line:
            formatted_log_line = f"[{log_line['tm']}] {log_line['type']}"
            if "data" in log_line and len(log_line["data"]) > 0:
                formatted_log_line += f": {log_line['data']}"
            result.append(formatted_log_line)
    return "\n".join(result)


################################
################################

app = FastAPI(openapi_url=None)
app.mount(f"/{URL_PREFIX}/survey", WSGIMiddleware(flask_site.flask_app))
secrets = mindlib.json_to_dict("secrets.json")


class VideoPageIn(BaseModel):
    """Data about a video page after the participant selected a video."""

    screen_time_start: str
    user_agent: str
    screen: int

    vidA_playback_time_start: str
    vidA_playback_time_end: str
    vidA_watch_count: int
    vidA_logs: List[dict]

    vidB_playback_time_start: str
    vidB_playback_time_end: str
    vidB_watch_count: int
    vidB_logs: List[dict]

    selected_vid_id: str
    selected_vid_position: int
    screen_time_end: str


class IntroPageIn(BaseModel):
    """Data about a video page after the participant selected a video."""

    user_agent: str

    vid_playback_time_start: str
    vid_playback_time_end: str
    vid_watch_count: int
    vid_logs: List[dict]

    vid_id: str


def debug_print_video_data_in(key: str, v: VideoPageIn) -> None:
    print(f"User '{key}' ({v.user_agent}) finished a survey page")
    print(
        f"\tSelected video with ID '{v.selected_vid_id}' @ pos {v.selected_vid_position} (screen {v.screen})"
    )
    print(f"\tPage duration: from {v.screen_time_start} to {v.screen_time_end}")
    print(f"\tVideo A (left):")
    print(f"\t\tWatched from {v.vidA_playback_time_start} - {v.vidA_playback_time_end}")
    print(f"\t\t{v.vidA_watch_count} play(s)")
    print(f"\t\tLogs: {v.vidA_logs}")
    print(f"\tVideo B (right):")
    print(f"\t\tWatched from {v.vidB_playback_time_start} - {v.vidB_playback_time_end}")
    print(f"\t\t{v.vidB_watch_count} play(s)")
    print(f"\t\tLogs: {v.vidB_logs}")


@app.post(f"/{URL_PREFIX}/video_selected")
async def get_video_choice(video_page_data: VideoPageIn, key: str | None = None) -> None:
    if key:
        if len(video_page_data.selected_vid_id) > 1 and (
            video_page_data.selected_vid_id[0] == video_page_data.selected_vid_id[-1] == '"'
            or video_page_data.selected_vid_id[0] == video_page_data.selected_vid_id[-1] == "'"
        ):
            # Remove bounding single- or double-quotes from the selected video ID string
            video_page_data.selected_vid_id = video_page_data.selected_vid_id[1:-1]

        logs.write_log(f"Uploading data for screen {video_page_data.screen}....", key, "api")
        this_redcap_event = f"screen{video_page_data.screen}_arm_1"

        if redcap_helpers.check_event_for_prefilled_data(
            secrets["C2C_DCV_API_TOKEN"],
            secrets["REDCAP_API_URL"],
            key,
            this_redcap_event,
            "video_complete",
        ):
            logs.write_log(
                f'Already had data for screen {video_page_data.screen}; REDCap event "{this_redcap_event}"',
                key,
                "api",
            )
            return
        # If a user clicks the "Back" button in their browser, then they can re-watch a screen
        # Don't count the data from this duplicate screen if there's already data for this screen in REDCap
        # The Flask middleware should automatically serve the correct screen

        redcap_video_page_record = {
            "access_key": key,
            "redcap_event_name": this_redcap_event,
            "screen_tm_start": video_page_data.screen_time_start,
            "video_a_tm_start": video_page_data.vidA_playback_time_start,
            "video_a_tm_end": video_page_data.vidA_playback_time_end,
            "video_a_playcount": video_page_data.vidA_watch_count,
            "video_a_logs": transform_logs(video_page_data.vidA_logs),
            "video_b_tm_start": video_page_data.vidB_playback_time_start,
            "video_b_tm_end": video_page_data.vidB_playback_time_end,
            "video_b_playcount": video_page_data.vidB_watch_count,
            "video_b_logs": transform_logs(video_page_data.vidB_logs),
            "video_selection": video_page_data.selected_vid_id,
            "screen_tm_end": video_page_data.screen_time_end,
            "video_complete": "2",
        }

        # debug_print_video_data_in(key, video_page_data)
        # from json import dumps
        # json_sent_to_redcap = dumps(redcap_video_page_record)
        # print(json_sent_to_redcap)

        import_result = redcap_helpers.import_record(
            secrets["C2C_DCV_API_TOKEN"], secrets["REDCAP_API_URL"], [redcap_video_page_record]
        )
        logs.write_log(f"Uploaded {import_result} record(s) to REDCap", key, "api")
    else:
        print("No access key detected")


@app.post(f"/{URL_PREFIX}/intro_vid_info")
async def get_intro_info(video_page_data: IntroPageIn, key: str | None = None) -> None:
    if key:
        logs.write_log("Uploading data for intro video....", key, "api")

        intro_redcap_event = "introscreen_arm_1"
        if redcap_helpers.check_event_for_prefilled_data(
            secrets["C2C_DCV_API_TOKEN"],
            secrets["REDCAP_API_URL"],
            key,
            intro_redcap_event,
            "single_video_complete",
        ):
            logs.write_log(
                f'Already had data for intro video event "{intro_redcap_event}"', key, "api"
            )
            return

        redcap_intro_page_record = {
            "access_key": key,
            "redcap_event_name": intro_redcap_event,
            "single_video_id": video_page_data.vid_id,
            "single_video_playcount": video_page_data.vid_watch_count,
            "single_video_tm_start": video_page_data.vid_playback_time_start,
            "single_video_tm_end": video_page_data.vid_playback_time_end,
            "single_video_logs": transform_logs(video_page_data.vid_logs),
            "single_video_complete": "2",
        }

        import_result = redcap_helpers.import_record(
            secrets["C2C_DCV_API_TOKEN"], secrets["REDCAP_API_URL"], [redcap_intro_page_record]
        )
        logs.write_log(f"Uploaded {import_result} record(s) to REDCap", key, "api")
    else:
        print("No access key detected")


@app.get("/")
@app.get(f"/{URL_PREFIX}")
@app.get(f"/{URL_PREFIX}/video_selected")
async def redirect_to_flask():
    return RedirectResponse(f"/{URL_PREFIX}/survey", status_code=302)


if __name__ == "__main__":
    uvicorn.run(app)
