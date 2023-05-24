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

VIDEOS = mindlib.json_to_dict("videos.json")


################################
################################

app = FastAPI(openapi_url=None)
# app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount(f"/{URL_PREFIX}/survey", WSGIMiddleware(flask_site.flask_app))
secrets = mindlib.json_to_dict("secrets.json")


class VideoPageIn(BaseModel):
    """Data about a video page after the participant selected a video"""

    screen_time_start: str
    user_agent: str

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


class VideoOut(BaseModel):
    """Data about a video that this server will send to the client"""

    vid_id: str
    url: str


class VideoOutPack(BaseModel):
    """2 VideoOuts to send to clients as JSON objects"""

    videoA: VideoOut
    videoB: VideoOut


@app.post(f"/{URL_PREFIX}/video_selected")
async def get_video_choice(video_page_data: VideoPageIn, key: str | None = None) -> None:
    if key:
        print(f"User '{key}' ({video_page_data.user_agent}) finished a survey page")
        print(
            f"\tSelected video with ID '{video_page_data.selected_vid_id}' @ pos {video_page_data.selected_vid_position}"
        )
        print(
            f"\tPage duration: from {video_page_data.screen_time_start} to {video_page_data.screen_time_end}"
        )
        print(f"\tVideo A:")
        print(
            f"\t\tWatched from {video_page_data.vidA_playback_time_start} - {video_page_data.vidA_playback_time_end}"
        )
        print(f"\t\t{video_page_data.vidA_watch_count} play(s)")
        print(f"\t\tLogs: {video_page_data.vidA_logs}")
        print(f"\tVideo B:")
        print(
            f"\t\tWatched from {video_page_data.vidB_playback_time_start} - {video_page_data.vidB_playback_time_end}"
        )
        print(f"\t\t{video_page_data.vidB_watch_count} play(s)")
        print(f"\t\tLogs: {video_page_data.vidB_logs}")
        # TODO: send data to REDCap
        # + set this screen event's "video_complete" to "2"
        # + set the 3rd screen's video A or B to this screen's selection - randomly? or pre-set?
    else:
        print("No access key detected")


@app.get(f"/{URL_PREFIX}/get_videos")
async def send_video(key: str | None = None) -> VideoOutPack | dict:
    if key:
        # video_A_id, video_B_id = random.sample(list(VIDEOS.keys()), 2)
        screens = redcap_helpers.export_video_ids(
            secrets["C2C_DCV_API_TOKEN"], secrets["REDCAP_API_URL"], recordid=key
        )
        if len(screens) == 0:
            # REDCap API returns an empty list if the record ID (access key) isn't in the project
            print(f"Access key {key} not found in REDCap")
            return {"detail": "Not Found"}

        # Get the next 2 video IDs based on REDCap event completion
        video_A_id = ""
        video_B_id = ""
        for screen in screens:
            this_screen_complete = screen["video_complete"] == "2"
            if not this_screen_complete:
                video_A_id = screen["video_a"]
                video_B_id = screen["video_b"]
                break

        print(f"Sending videos '{video_A_id}' and '{video_B_id}' to user '{key}'")
        vidA = VideoOut(vid_id=video_A_id, url=VIDEOS[video_A_id])
        vidB = VideoOut(vid_id=video_B_id, url=VIDEOS[video_B_id])
        return VideoOutPack(videoA=vidA, videoB=vidB)
    return {"detail": "Not Found"}


@app.get("/")
@app.get(f"/{URL_PREFIX}")
async def redirect_to_flask():
    return RedirectResponse(f"/{URL_PREFIX}/survey", status_code=302)


if __name__ == "__main__":
    uvicorn.run(app)
