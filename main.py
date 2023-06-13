import json
from typing import List

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import flask_site
import mindlib
import redcap_helpers

################################
############ CONFIG ############

URL_PREFIX = "c2c-retention-dce"

VIDEOS = mindlib.json_to_dict("./content/videos.json")


################################
############ CONFIG ############


def transform_logs(log_list: list[dict]) -> str:
    # TODO: trim logs further: don't present as list of JSON objects, maybe lines instead
    print("Formatting these logs:")
    print(log_list)
    return json.dumps(log_list)  # temp


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


# class VideosOut(BaseModel):
#     """Data about 2 videos to send to participants."""

#     vidA_id: str
#     vidA_url: str
#     vidB_id: str
#     vidB_url: str


@app.post(f"/{URL_PREFIX}/video_selected")
async def get_video_choice(video_page_data: VideoPageIn, key: str | None = None) -> None:
    if key:
        # print(f"User '{key}' ({video_page_data.user_agent}) finished a survey page")
        # print(
        #     f"\tSelected video with ID '{video_page_data.selected_vid_id}' @ pos {video_page_data.selected_vid_position} (screen {video_page_data.screen})"
        # )
        # print(
        #     f"\tPage duration: from {video_page_data.screen_time_start} to {video_page_data.screen_time_end}"
        # )
        # print(f"\tVideo A:")
        # print(
        #     f"\t\tWatched from {video_page_data.vidA_playback_time_start} - {video_page_data.vidA_playback_time_end}"
        # )
        # print(f"\t\t{video_page_data.vidA_watch_count} play(s)")
        # print(f"\t\tLogs: {video_page_data.vidA_logs}")
        # print(f"\tVideo B:")
        # print(
        #     f"\t\tWatched from {video_page_data.vidB_playback_time_start} - {video_page_data.vidB_playback_time_end}"
        # )
        # print(f"\t\t{video_page_data.vidB_watch_count} play(s)")
        # print(f"\t\tLogs: {video_page_data.vidB_logs}")

        # TODO: create records for event "start_arm_1" (might handle this in Flask, not here)
        # TODO: handle separate API calls for these REDCap vars in "start_arm_1":
        # - survey_start_tm
        #   - when user gets disclaimer page?
        #   - when user starts screen 1?
        # - survey_end_tm
        #   - when screen 3 ends?
        #   - when the bonus text questions are done?
        redcap_video_page_record = {
            "access_key": key,
            "redcap_event_name": f"screen{video_page_data.screen}_arm_1",
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
        # record_as_str = json.dumps(redcap_video_page_record)
        # print(record_as_str)
        import_result = redcap_helpers.import_record(
            secrets["C2C_DCV_API_TOKEN"], secrets["REDCAP_API_URL"], [redcap_video_page_record]
        )
        print(f"Uploaded {import_result} record(s) to REDCap")
    else:
        print("No access key detected")


# @app.get(f"/{URL_PREFIX}/get_videos")
# async def send_video(key: str | None = None) -> VideosOut | dict:
#     if key:
#         # video_A_id, video_B_id = random.sample(list(VIDEOS.keys()), 2)
#         screens = redcap_helpers.export_video_ids(
#             secrets["C2C_DCV_API_TOKEN"], secrets["REDCAP_API_URL"], recordid=key
#         )
#         if len(screens) == 0:
#             # REDCap API returns an empty list if the record ID (access key) isn't in the project
#             print(f"Access key {key} not found in REDCap")
#             return {"detail": "Not Found"}

#         # Get the next 2 video IDs based on REDCap event completion
#         video_A_id = ""
#         video_B_id = ""
#         for screen in screens:
#             this_screen_complete = screen["video_complete"] == "2"
#             if not this_screen_complete:
#                 video_A_id = screen["video_a"]
#                 video_B_id = screen["video_b"]
#                 break

#         print(f"Sending videos '{video_A_id}' and '{video_B_id}' to user '{key}'")
#         return VideosOut(
#             vidA_id=video_A_id,
#             vidA_url=VIDEOS[video_A_id],
#             vidB_id=video_B_id,
#             vidB_url=VIDEOS[video_B_id],
#         )
#     return {"detail": "Not Found"}


@app.get("/")
@app.get(f"/{URL_PREFIX}")
@app.get(f"/{URL_PREFIX}/video_selected")
async def redirect_to_flask():
    return RedirectResponse(f"/{URL_PREFIX}/survey", status_code=302)


if __name__ == "__main__":
    uvicorn.run(app)
