//////// Constants/options ////////

const server = "http://127.0.0.1:8000/c2c-retention-dce";
//const server = "https://studies.mind.uci.edu/c2c-retention-dce";

// For any given video page: video A is on the left/top, video B is on the right/bottom
const VIDEO_A_HTML_ID = "videoA";
const VIDEO_A_SELECT_BUTTON_HTML_ID = "videoASelect";
const VIDEO_A_MESSAGE_BOX_HTML_ID = "videoAMessage";
const VIDEO_B_HTML_ID = "videoB";
const VIDEO_B_SELECT_BUTTON_HTML_ID = "videoBSelect";
const VIDEO_B_MESSAGE_BOX_HTML_ID = "videoBMessage";

const VIDEO_SUBMIT_BUTTON_HTML_ID = "submitVideoSelection";
const VIDEO_SUBMIT_LOADING_BUTTON_HTML_ID = "loading_button";

// Number of seconds from the beginning of a video that a user can seek to
// that counts as "from the beginning" (in case they skipped ahead and need to restart the video)
const SEEK_BEGINNING_THRESHOLD = 2;

//// Startup ////

let videoPageStartTime = "";
let videoPageEndTime = "";

let videoA;
let videoB;

const _params = new Proxy(new URLSearchParams(window.location.search), {
    get: (searchParams, prop) => searchParams.get(prop),
});
const access_key = _params.key;
const thisScreenFromURL = parseInt(_params.screen);
let mostCompletedScreen = 0;

const finalSelectionButton = document.getElementById(VIDEO_SUBMIT_BUTTON_HTML_ID);
const finalSelectionLoadingButton = document.getElementById(VIDEO_SUBMIT_LOADING_BUTTON_HTML_ID);

//// Helpers ////

function parseVimeoResponse(data, attr) {
    // Safely fetches data from a Vimeo player data object
    if (attr === "duration" && "duration" in data) {
        // The length of the video in seconds.
        return data.duration;
    }
    if (attr === "percent" && "percent" in data) {
        // The amount of the video that has played in comparison to the length of the video;
        // multiply by 100 to obtain the percentage.
        return data.percent;
    }
    if (attr === "seconds" && "seconds" in data) {
        // The amount of the video, in seconds, that has played.
        return data.seconds;
    }
    if (attr === "volume" && "volume" in data) {
        // The new volume level.
        return data.volume;
    }
    if (attr === "playbackRate" && "playbackRate" in data) {
        // The new playback rate.
        return data.playbackRate;
    }
};

function getDefaultVideoStringFromHTML(videoDivID) {
    videoElement = document.getElementById(videoDivID);
    if (videoElement) {
        let result = videoElement.innerHTML;
        videoElement.innerText = "";
        return result;
    }
    return "";
}

function getVideoInfoFromCookie(videoPos, vidsCookies, cookieSuffix) {
    let cookieName = `v${videoPos}_${cookieSuffix}`;
    return vidsCookies[cookieName];
}

function cookiesToJSON(cookieString) {
    let output = {};
    cookieString.split(/\s*;\s*/).forEach(function (pair) {
        pair = pair.split(/\s*=\s*/);
        output[pair[0]] = pair.splice(1).join('=');
    });
    return output;
}

// function jsonToCookieString(cookieJSON) {
//     let result = "";
//     for (const attr in cookieJSON) {
//         result = result.concat(`; ${attr}=${cookieJSON[attr]}`);
//     };
//     console.log(`Created cookie string: "${result}"`);
//     return result;
// }

function getVideos(cookiesJSON) {
    result = {};
    for (const c in cookiesJSON) {
        if (c.startsWith("v") && (c.endsWith("_id") || c.endsWith("_url"))) {
            result[c] = cookiesJSON[c];
        }
    }
    return result;
}

function getUTCTimestampNow(includeMilliseconds = true) {
    // YYYY-MM-DD hh:mm:ss.mis
    const d = new Date();
    let year = String(d.getUTCFullYear()).padStart(4, "0");
    let month = String(d.getUTCMonth() + 1).padStart(2, "0");
    let day = String(d.getUTCDate()).padStart(2, "0");
    let hours = String(d.getUTCHours()).padStart(2, "0");
    let minutes = String(d.getUTCMinutes()).padStart(2, "0");
    let seconds = String(d.getUTCSeconds()).padStart(2, "0");
    if (!includeMilliseconds) {
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }
    let milliseconds = String(d.getUTCMilliseconds()).padStart(3, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${milliseconds}`;
}

function createLogEntry(vimeo_data, data_label, video_position, video_id) {
    const UTCTimestamp = getUTCTimestampNow();

    // Base log entry - modify or add to this depending on event type and event data
    let logEntry = {
        // position: video_position,
        // vid_id: video_id,
        tm: UTCTimestamp,
        type: data_label,
        data: ""
    }

    if (data_label.includes("VOLUME")) {
        let _vimeo_volume = parseVimeoResponse(vimeo_data, "volume");
        let _vimeo_volume_percent = Number(_vimeo_volume * 100).toFixed(1);
        logEntry.data = `${_vimeo_volume_percent}%`;
    }
    else if (data_label.includes("SPEED")) {
        let _vimeo_playback_rate = parseVimeoResponse(vimeo_data, "playbackRate");
        logEntry.data = `${_vimeo_playback_rate}x`;
    } else {
        // Default event type that includes time data (seconds, duration, percent)
        let _vimeo_seconds = parseVimeoResponse(vimeo_data, "seconds");
        // let _vimeo_duration = parseVimeoResponse(vimeo_data, "duration");
        let _vimeo_percent = parseVimeoResponse(vimeo_data, "percent");
        let _vimeo_percent_percent = Number(_vimeo_percent * 100).toFixed(1);

        // console.log(`${_vimeo_seconds}, ${_vimeo_duration}, ${_vimeo_percent}`);

        if (data_label.includes("PLAYED") && _vimeo_seconds === 0 && _vimeo_percent === 0) {
            logEntry.type = "STARTED";
        }
        if (data_label.includes("PAUSED") && _vimeo_percent >= 0.997) {
            // Finishing a video creates a "pause" event
            // Originally included a check for _vimeo_seconds === _vimeo_duration, BUT:
            // on some videos, _vimeo_seconds != _vimeo_duration when the video finishes
            // Could improve with a threshold, maybe if _vimeo_seconds was > 98% of _vimeo_duration?
            logEntry.type = "FINISHED";
        }

        logEntry.data = `${_vimeo_seconds}sec/${_vimeo_percent_percent}%`;
    }
    console.log(logEntry);
    return logEntry;
}

function getVideoInfoFromDefaultString(defaultString) {
    let parts = defaultString.split(" - ");
    let position = parseInt(parts[0]);
    if (!isNaN(position)) {
        parts[0] = position
    }
    return parts;
}

class VideoChoice {
    constructor(vidDefaultString, selectButtonHTMLID, messageBoxHTMLID) {
        let vid_info = getVideoInfoFromDefaultString(vidDefaultString);
        this.position = vid_info[0];
        this.vid_id = vid_info[1];
        this.url = vid_info[2];
        this.selectButtonID = selectButtonHTMLID;
        this.messageBoxID = messageBoxHTMLID;

        this.logs = [];
        this.startTimestamp = "";
        this.endTimestamp = "";
        this.skipped = false;
        this.pauseCount = 0;
        this.watchCount = 0;
        this.finished = false;
        this.playbackPosition = 0;
    }
    getLog() {
        // Returns a string containing essential data about this object
        return `VideoChoice(position=${this.position}, vid_id=${this.vid_id}, url=${this.url}, startTimestamp=${this.startTimestamp}, endTimestamp=${this.endTimestamp}, skipped=${this.skipped}, pauseCount=${this.pauseCount}, watchCount=${this.watchCount}, finished=${this.finished})`;
    }
}

async function setupVideoPlayer() {
    let allCookies = cookiesToJSON(document.cookie);

    mostCompletedScreen = parseInt(allCookies["completed_screen"]);
    if (thisScreenFromURL <= mostCompletedScreen) {
        // Protects survey flow from users clicking the "Back" button and moving to a previous screen
        // Skip loading these Vimeo players and direct the user to the screen they should be at
        window.location.href = `${server}/survey/videos?key=${access_key}&screen=${mostCompletedScreen + 1}`;
        return;
    }

    vidADefaultString = getDefaultVideoStringFromHTML(VIDEO_A_HTML_ID);
    vidBDefaultString = getDefaultVideoStringFromHTML(VIDEO_B_HTML_ID);
    videoA = new VideoChoice(vidADefaultString, VIDEO_A_SELECT_BUTTON_HTML_ID, VIDEO_A_MESSAGE_BOX_HTML_ID);
    videoB = new VideoChoice(vidBDefaultString, VIDEO_B_SELECT_BUTTON_HTML_ID, VIDEO_B_MESSAGE_BOX_HTML_ID);

    if (videoA.position <= 0 || videoB.position <= 0) {
        // Need both videos to load - if they load correctly, their positions will be >= 1
        console.log(`Did not load videos due to invalid positions (A: ${videoA.position}, B: ${videoB.position})`)
        return;
    }

    // Initialize Vimeo player inside their respective VideoChoice objects
    videoA.player = new Vimeo.Player(VIDEO_A_HTML_ID, { url: videoA.url });
    videoB.player = new Vimeo.Player(VIDEO_B_HTML_ID, { url: videoB.url });
    console.log(`Loaded Video A: ${videoA.getLog()}`);
    console.log(`Loaded Video B: ${videoB.getLog()}`);

    videoPageStartTime = getUTCTimestampNow(includeMilliseconds = false);
    console.log(`Most recently completed screen: ${mostCompletedScreen} (screen from URL: ${thisScreenFromURL}) started at ${videoPageStartTime}`);
    console.log(`Loaded videos ${videoA.vid_id} (pos ${videoA.position}) and ${videoB.vid_id} (pos ${videoB.position})`);

    function setupPlayerEvents(videoObj, otherVideoObj) {
        // https://developer.vimeo.com/player/sdk/reference#events-for-playback-controls
        var _videoMessageBoxElement = document.getElementById(videoObj.messageBoxID);
        var _selectionButtonElement = document.getElementById(videoObj.selectButtonID);
        var _otherSelectionButtonElement = document.getElementById(otherVideoObj.selectButtonID);
        // console.log(_videoMessageBoxElement.innerText);
        videoObj.player.on('play', function (data) {
            // Automatically pause when the other video is already playing:
            otherVideoObj.player.getPaused().then(function (paused) {
                if (paused == false) {
                    otherVideoObj.player.pause().then(function () {
                        // console.log("Paused the other Vimeo player.");
                        videoObj.logs.push(createLogEntry(data, "SWITCHED TO THIS VIDEO", videoObj.position, videoObj.vid_id));
                    });
                }
            });
            if (videoObj.startTimestamp == "") {
                videoObj.startTimestamp = getUTCTimestampNow(includeMilliseconds = false);
                console.log(`Set video @ pos ${videoObj.position} start time to ${videoObj.startTimestamp}`);
            }
            videoObj.logs.push(createLogEntry(data, "PLAYED AT", videoObj.position, videoObj.vid_id));
            videoObj.playbackPosition = parseVimeoResponse(data, "seconds");
        })
        videoObj.player.on('pause', function (data) {
            videoObj.pauseCount = videoObj.pauseCount + 1;
            videoObj.logs.push(createLogEntry(data, "PAUSED AT", videoObj.position, videoObj.vid_id));
        })
        videoObj.player.on('volumechange', function (data) {
            // NOTE: Some devices don't support the ability to set the volume of the video independently of
            // the system volume, so this event never fires on those devices.
            // glitch with Vimeo API: toggling mute (clicking the volume icon) always returns "1" (the maximum)
            // instead of "0" when mute is activated
            videoObj.logs.push(createLogEntry(data, "VOLUME CHANGED TO", videoObj.position, videoObj.vid_id));
        })
        videoObj.player.on('playbackratechange', function (data) {
            // NOTE: If the creator of the video has disabled the ability of the viewer to change the playback
            // rate, this event doesn't fire.
            videoObj.logs.push(createLogEntry(data, "VIDEO SPEED CHANGED TO", videoObj.position, videoObj.vid_id));
        })
        videoObj.player.on('seeked', function (data) {
            // Important playback positions in seconds
            let positionBeforeSeek = videoObj.playbackPosition;
            let positionAfterSeek = parseVimeoResponse(data, "seconds");
            // console.log(`Video ${videoObj.position} (ID ${videoObj.vid_id}): playback position BEFORE seek: ${positionBeforeSeek}`)
            if (positionBeforeSeek < positionAfterSeek) {
                // Don't allow this view to count as "watched" if the user skips ahead
                videoObj.logs.push(createLogEntry(data, "SEEKED AHEAD TO", videoObj.position, videoObj.vid_id));
                if (!videoObj.finished) {
                    console.log(`Video ${videoObj.position} - not counting this view`)
                    _videoMessageBoxElement.innerText = "❌ Video not yet finished ❌\nPlease do not skip ahead in the video.";
                }
                videoObj.skipped = true;
            } else if (positionBeforeSeek >= positionAfterSeek) {
                // Don't penalize the user for skipping behind
                videoObj.logs.push(createLogEntry(data, "SEEKED BEHIND TO", videoObj.position, videoObj.vid_id));
            }
            videoObj.playbackPosition = positionAfterSeek;

            if (positionAfterSeek <= SEEK_BEGINNING_THRESHOLD) {
                // If a user skips to the beginning, reset skips flag and re-allow this viewing
                videoObj.logs.push(createLogEntry(data, "SEEKED TO START", videoObj.position, videoObj.vid_id));
                console.log(`Video ${videoObj.position} (ID ${videoObj.vid_id}): skipped back to the beginning`);
                videoObj.skipped = false;
                if (!videoObj.finished) {
                    _videoMessageBoxElement.innerText = "❌ Video not yet finished ❌";
                }
            }
        })
        videoObj.player.on('timeupdate', function (data) {
            // Used to get the most recent playback position before a "seek" event is fired
            let currentTime = parseVimeoResponse(data, "seconds");
            if (currentTime - 1 < videoObj.playbackPosition && currentTime > videoObj.playbackPosition) {
                /*
                via Christian Tam from https://codepen.io/ctam8/pen/KrzRyg (edited to accomodate our variable names):
                - (currentTime - 1 < videoObj.playbackPosition) basically if you seek, this will return false and the current time wont get updated
                - (currentTime > videoObj.playbackPosition) if they seek backwards then dont update current time so they can seek back to where they were before
                */
                videoObj.playbackPosition = currentTime;
                // console.log(`Video ${videoObj.position} playback position: ${videoObj.playbackPosition}`)
            }
        })
        videoObj.player.on('ended', async function () {
            // console.log("Video 01 ENDED");
            // When a video finishes, a pause event is fired, so manually decrement pause count
            videoObj.pauseCount = videoObj.pauseCount - 1;
            if (!videoObj.skipped) {
                // There were no skips: enable the selection button
                videoObj.finished = true;
                videoObj.watchCount = videoObj.watchCount + 1;
                videoObj.endTimestamp = getUTCTimestampNow(includeMilliseconds = false);
                console.log(`Set video @ pos ${videoObj.position} end time to ${videoObj.endTimestamp}`);
                _videoMessageBoxElement.innerText = "✅ Video finished ✅";
            } else {
                // There were skips
                if (!videoObj.finished) {
                    _videoMessageBoxElement.innerText = "❌ Video not yet finished ❌\nPlease watch the entire video before making a selection.";
                }
            }

            // Enable buttons when both videos are finished and with no skips
            if (videoObj.finished && otherVideoObj.finished) {
                _selectionButtonElement.disabled = false;
                _otherSelectionButtonElement.disabled = false;
            }
            console.log(`Video ${videoObj.position} (ID ${videoObj.vid_id}): ended with ${videoObj.pauseCount} pause(s), watched ${videoObj.watchCount} time(s)`);
            console.log(`Video ${videoObj.position} (ID ${videoObj.vid_id}): any skips? ${videoObj.skipped}`);
        })
        // videoPlayer.on('progress', (data) => {
        // //If the player percent is over 0.95, updateProgress to 100% and remove all listeners
        //     if(data.percent > 0.95) {
        //         //Manually set the data to 100
        //         data.percent = 1;
        //         //Remove the listeners
        //         videoPlayer.off('pause');
        //         videoPlayer.off('seeked');
        //         videoPlayer.off('progress');
        //         //Update the progress to be 100
        //         updateProgress(data, 'seeked');
        //     }
        // })
    }
    setupPlayerEvents(videoA, otherVideoObj = videoB);
    setupPlayerEvents(videoB, otherVideoObj = videoA);
}

async function uploadVideoSelection() {
    let ele = document.getElementsByName('options');
    let selectedVideoPos;
    let selectedVideo;

    for (i = 0; i < ele.length; i++) {
        if (ele[i].checked) {
            selectedVideoPos = ele[i].value;
        }
    }

    if (videoA.finished && videoB.finished) {
        finalSelectionButton.setAttribute('hidden', '');
        finalSelectionLoadingButton.removeAttribute('hidden');
        if (selectedVideoPos == videoA.position) {
            selectedVideo = videoA;
        } else {
            selectedVideo = videoB;
        }
        console.log(`User selected this video: ${selectedVideo.getLog()}`);

        videoPageEndTime = getUTCTimestampNow(includeMilliseconds = false);

        // Add 1 to the most completed screen to get THIS screen
        let thisCompletedScreen = mostCompletedScreen + 1;
        document.cookie = `completed_screen=${thisCompletedScreen}`;

        const requestOptions = {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                user_agent: navigator.userAgent,
                screen: thisCompletedScreen,
                screen_time_start: videoPageStartTime,
                vidA_playback_time_start: videoA.startTimestamp,
                vidA_playback_time_end: videoA.endTimestamp,
                vidA_watch_count: videoA.watchCount,
                vidA_logs: videoA.logs,
                vidB_playback_time_start: videoB.startTimestamp,
                vidB_playback_time_end: videoB.endTimestamp,
                vidB_watch_count: videoB.watchCount,
                vidB_logs: videoB.logs,
                selected_vid_id: selectedVideo.vid_id,
                selected_vid_position: selectedVideo.position,
                screen_time_end: videoPageEndTime
            })
        }
        const url = `${server}/video_selected?key=${access_key}`;
        await fetch(url, requestOptions);
        window.location.href = `${server}/survey/videos?key=${access_key}&screen=${thisCompletedScreen + 1}`;
    } else {
        alert("Please finish watching all videos before making a selection.");
    }
}

function activateSelectionButton() {
    if (finalSelectionButton.hasAttribute("disabled")) {
        finalSelectionButton.disabled = false;
    }
}

////////

setupVideoPlayer();
