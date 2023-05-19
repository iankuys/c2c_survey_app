from typing import Any, List

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, BaseSettings

import flask_site
import mindlib
import redcap_helpers

################################
############ CONFIG ############

URL_PREFIX = "/c2c-retention-dce"

VIDEOS = mindlib.json_to_dict("videos.json")


################################
################################

app = FastAPI(openapi_url=None)
# app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/survey", WSGIMiddleware(flask_site.flask_app))
secrets = mindlib.json_to_dict("secrets.json")


class VideoIn(BaseModel):
    """Data about a video that the client selected after finishing both videos"""

    vid_id: str
    position: int
    pause_count: int
    logs: List[dict]
    user_agent: str


class VideoOut(BaseModel):
    """Data about a video that this server will send to the client"""

    vid_id: str
    url: str


class VideoOutPack(BaseModel):
    """2 VideoOuts to send to clients as JSON objects"""

    videoA: VideoOut
    videoB: VideoOut


@app.post("/video_selected")
async def get_video_choice(video_choice: VideoIn, key: str | None = None) -> None:
    if key:
        print(
            f"User '{key}' selected this video:\n\tID '{video_choice.vid_id}'\n\tPosition '{video_choice.position}'\n\t'{video_choice.pause_count}' pauses\n\tUser Agent '{video_choice.user_agent}'\n\tLogs: {video_choice.logs}"
        )
        # TODO: set this screen event's "video_complete" to "2"
        # AND set the 3rd screen's video A or B to this screen's selection - randomly? or pre-set?
    else:
        print("No access key detected")


@app.get("/get_videos")
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
async def redirect_to_flask():
    return RedirectResponse("/survey", status_code=302)


if __name__ == "__main__":
    uvicorn.run(app)
