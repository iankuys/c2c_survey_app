const server = "http://127.0.0.1:8000/c2c-retention-dce";
//const server = "https://studies.mind.uci.edu/c2c-retention-dce";

let videoPageStartTime = "";
let videoPageEndTime = "";

let videoA;
let videoB;

const VIDEO_A_HTML_ID = "videoA";
const VIDEO_A_SELECT_BUTTON_HTML_ID = "selectVideoA";
const VIDEO_A_MESSAGE_BOX_HTML_ID = "videoAMessage";
const VIDEO_B_HTML_ID = "videoB";
const VIDEO_B_SELECT_BUTTON_HTML_ID = "selectVideoB";
const VIDEO_B_MESSAGE_BOX_HTML_ID = "videoBMessage";

// Number of seconds from the beginning of a video that a user can seek to
// that counts as "from the beginning" (in case they skipped ahead and need to restart the video)
const SEEK_BEGINNING_THRESHOLD = 2;

const _params = new Proxy(new URLSearchParams(window.location.search), {
    get: (searchParams, prop) => searchParams.get(prop),
});
const access_key = _params.key;

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

function getVideoPositionFromHTML(videoDivID) {
    videoElement = document.getElementById(videoDivID);
    let vidPosition = videoElement.innerHTML;
    videoElement.innerText = "";
    return vidPosition;
}

async function getVideos() {
    const url = `${server}/get_videos?key=${access_key}`;
    const response = await fetch(url);
    const vids = await response.json(); // is await necessary here?
    vA = { vid_id: vids.vidA_id, url: vids.vidA_url };
    vB = { vid_id: vids.vidB_id, url: vids.vidB_url };
    return ([vA, vB]);
}

function getUTCTimestampNow() {
    // YYYY-MM-DD hh:mm:ss.mis
    const d = new Date();
    let year = String(d.getUTCFullYear()).padStart(4, "0");
    let month = String(d.getUTCMonth() + 1).padStart(2, "0");
    let day = String(d.getUTCDate()).padStart(2, "0");
    let hours = String(d.getUTCHours()).padStart(2, "0");
    let minutes = String(d.getUTCMinutes()).padStart(2, "0");
    let seconds = String(d.getUTCSeconds()).padStart(2, "0");
    let milliseconds = String(d.getUTCMilliseconds()).padStart(3, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${milliseconds}`;
}

function createLogEntry(vimeo_data, data_label, video_position, video_id) {
    const UTCTimestamp = getUTCTimestampNow();

    // Base log entry - modify or add to this depending on event type and event data
    let logEntry = {
        position: video_position,
        vid_id: video_id,
        timestamp: UTCTimestamp,
        event_type: data_label
    }

    if (data_label.includes("VOLUME")) {
        let _vimeo_volume = parseVimeoResponse(vimeo_data, "volume");
        let _vimeo_volume_percent = Number(_vimeo_volume * 100).toFixed(1);
        logEntry.event_data = `${_vimeo_volume_percent}%`;
    }
    else if (data_label.includes("SPEED")) {
        let _vimeo_playback_rate = parseVimeoResponse(vimeo_data, "playbackRate");
        logEntry.event_data = `${_vimeo_playback_rate}x`;
    } else {
        // Default event type that includes time data (seconds, duration, percent)
        let _vimeo_seconds = parseVimeoResponse(vimeo_data, "seconds");
        let _vimeo_duration = parseVimeoResponse(vimeo_data, "duration");
        let _vimeo_percent = parseVimeoResponse(vimeo_data, "percent");
        let _vimeo_percent_percent = Number(_vimeo_percent * 100).toFixed(1);

        if (data_label.includes("PLAYED") && _vimeo_seconds === 0 && _vimeo_percent === 0) {
            logEntry.event_type = "STARTED";
        }
        if (data_label.includes("PAUSED") && _vimeo_seconds === _vimeo_duration && _vimeo_percent === 1) {
            // Finishing a video creates a "pause" event
            logEntry.event_type = "FINISHED";
        }

        logEntry.event_data = `${_vimeo_seconds}sec/${_vimeo_percent_percent}%`;
    }
    console.log(logEntry);
    return logEntry;
}

async function setupVideoPlayer() {
    let videos = await getVideos();
    // Videos are initialized with attributes 'vid_id' and 'url' in getVideos()

    videoA = videos[0];
    videoA.position = getVideoPositionFromHTML(VIDEO_A_HTML_ID);
    videoA.logs = [];
    videoA.startTimestamp = "";
    videoA.endTimestamp = "";
    videoA.skipped = false;
    videoA.pauseCount = 0;
    videoA.watchCount = 0;
    videoA.finished = false;
    videoA.playbackPosition = 0;
    let vid01_vimeo_params = { url: videoA.url };
    const videoAPlayer = new Vimeo.Player(VIDEO_A_HTML_ID, vid01_vimeo_params);

    videoB = videos[1];
    videoB.position = getVideoPositionFromHTML(VIDEO_B_HTML_ID);
    videoB.logs = [];
    videoB.startTimestamp = "";
    videoB.endTimestamp = "";
    videoB.skipped = false;
    videoB.pauseCount = 0;
    videoB.watchCount = 0;
    videoB.finished = false;
    videoB.playbackPosition = 0;
    let vid02_vimeo_params = { url: videoB.url };
    const videoBPlayer = new Vimeo.Player(VIDEO_B_HTML_ID, vid02_vimeo_params);

    videoPageStartTime = getUTCTimestampNow();
    console.log(`Survey page started at ${videoPageStartTime}`);
    console.log(`Loaded videos: ${JSON.stringify(videoA)} ${JSON.stringify(videoB)}`);

    function setupEvents(vimeoPlayer, otherVimeoPlayer, videoObj, selectionButtonID, messageBoxID) {
        // https://developer.vimeo.com/player/sdk/reference#events-for-playback-controls
        var videoMessageBoxElement = document.getElementById(messageBoxID);
        // console.log(videoMessageBoxElement.innerText);
        vimeoPlayer.on('play', function (data) {
            // Automatically pause when the other video is already playing:
            otherVimeoPlayer.getPaused().then(function (paused) {
                if (paused == false) {
                    otherVimeoPlayer.pause().then(function () {
                        // console.log("Paused the other Vimeo player.");
                        videoObj.logs.push(createLogEntry(data, "SWITCHED TO THIS VIDEO", videoObj.position, videoObj.vid_id));
                    });
                }
            });
            videoObj.logs.push(createLogEntry(data, "PLAYED AT", videoObj.position, videoObj.vid_id));
            videoObj.playbackPosition = parseVimeoResponse(data, "seconds");
        })
        vimeoPlayer.on('pause', function (data) {
            videoObj.pauseCount = videoObj.pauseCount + 1;
            videoObj.logs.push(createLogEntry(data, "PAUSED AT", videoObj.position, videoObj.vid_id));
        })
        vimeoPlayer.on('volumechange', function (data) {
            // NOTE: Some devices don't support the ability to set the volume of the video independently of
            // the system volume, so this event never fires on those devices.
            // glitch with Vimeo API: toggling mute (clicking the volume icon) always returns "1" (the maximum)
            // instead of "0" when mute is activated
            videoObj.logs.push(createLogEntry(data, "VOLUME CHANGED TO", videoObj.position, videoObj.vid_id));
        })
        vimeoPlayer.on('playbackratechange', function (data) {
            // NOTE: If the creator of the video has disabled the ability of the viewer to change the playback
            // rate, this event doesn't fire.
            videoObj.logs.push(createLogEntry(data, "VIDEO SPEED CHANGED TO", videoObj.position, videoObj.vid_id));
        })
        vimeoPlayer.on('seeked', function (data) {
            let positionBeforeSeek = videoObj.playbackPosition;
            let positionAfterSeek = parseVimeoResponse(data, "seconds");
            // console.log(`Video ${videoObj.position} (ID ${videoObj.vid_id}): playback position BEFORE seek: ${positionBeforeSeek}`)
            if (positionBeforeSeek < positionAfterSeek) {
                // Don't allow this view to count as "watched" if the user skips ahead
                videoObj.logs.push(createLogEntry(data, "SEEKED AHEAD TO", videoObj.position, videoObj.vid_id));
                // console.log(`Video ${videoObj.position} seeked AHEAD`)
                if (!videoObj.finished) {
                    console.log(`Video ${videoObj.position} - not counting this view`)
                    videoMessageBoxElement.innerText = "❌ Video not yet finished ❌\nPlease do not skip ahead in the video.";
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
                    videoMessageBoxElement.innerText = "❌ Video not yet finished ❌";
                }
            }
        })
        vimeoPlayer.on('timeupdate', function (data) {
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
        vimeoPlayer.on('ended', async function () {
            // console.log("Video 01 ENDED");
            // When a video finishes, another pause event is fired, so manually decrement pause count
            videoObj.pauseCount = videoObj.pauseCount - 1;
            if (!videoObj.skipped) {
                // There were no skips: enable the selection button
                document.getElementById(selectionButtonID).disabled = false;
                videoObj.finished = true;
                videoObj.watchCount = videoObj.watchCount + 1;
                videoMessageBoxElement.innerText = "✅ Video finished ✅";
            } else {
                // There were skips
                if (!videoObj.finished) {
                    videoMessageBoxElement.innerText = "❌ Video not yet finished ❌\nPlease watch the entire video before making a selection.";
                }
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
    setupEvents(videoAPlayer, videoBPlayer, videoA, VIDEO_A_SELECT_BUTTON_HTML_ID, VIDEO_A_MESSAGE_BOX_HTML_ID);
    setupEvents(videoBPlayer, videoAPlayer, videoB, VIDEO_B_SELECT_BUTTON_HTML_ID, VIDEO_B_MESSAGE_BOX_HTML_ID);
}

async function uploadVideoSelection(selectButtonElement) {
    let value = selectButtonElement.value;
    let selectedVideo;

    if (videoA.finished && videoB.finished) {
        if (value == videoA.position) {
            selectedVideo = videoA;
        } else {
            selectedVideo = videoB;
        }
        console.log(`User selected video ${selectedVideo.position} - ID ${selectedVideo.vid_id} - ${selectedVideo.pauseCount} pause(s)`);

        videoPageEndTime = getUTCTimestampNow();

        const requestOptions = {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                user_agent: navigator.userAgent,
                screen_time_start: videoPageStartTime,
                vidA_playback_time_start: "(temp A start time)",
                vidA_playback_time_end: "(temp A end time)",
                vidA_watch_count: videoA.watchCount,
                vidA_logs: videoA.logs,
                vidB_playback_time_start: "(temp B start time)",
                vidB_playback_time_end: "(temp B end time)",
                vidB_watch_count: videoB.watchCount,
                vidB_logs: videoB.logs,
                selected_vid_id: selectedVideo.vid_id,
                selected_vid_position: selectedVideo.position,
                screen_time_end: videoPageEndTime
            })
        }
        const url = `${server}/video_selected?key=${access_key}`;
        await fetch(url, requestOptions);

    } else {
        alert("Please finish watching all videos before making a selection.");
    }
}

setupVideoPlayer();
