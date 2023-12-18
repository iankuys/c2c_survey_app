//////// Constants/options ////////

const server = "https://studies.mind.uci.edu/retention";

const INTRO_VID_HTML_ID = "introVideo";
const INTRO_VID_URL = "https://player.vimeo.com/video/653428289?h=c155f1e87b";

// Number of seconds from the beginning of a video that a user can seek to
// that counts as "from the beginning" (in case they skipped ahead and need to restart the video)
const SEEK_BEGINNING_THRESHOLD = 2;

//// Startup ////

let videoPageStartTime = "";
let videoPageEndTime = "";
let introVid;

const _params = new Proxy(new URLSearchParams(window.location.search), {
    get: (searchParams, prop) => searchParams.get(prop),
});
const access_key = _params.key;
const thisScreenFromURL = parseInt(_params.screen);

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

function createLogEntry(vimeo_data, data_label) {
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
    // console.log(logEntry);
    return logEntry;
}

class VideoChoice {
    constructor(videoUrl) {
        this.url = videoUrl;
        this.vid_id = "intro"

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
        return `VideoChoice(position=${this.position}, url=${this.url}, startTimestamp=${this.startTimestamp}, endTimestamp=${this.endTimestamp}, skipped=${this.skipped}, pauseCount=${this.pauseCount}, watchCount=${this.watchCount}, finished=${this.finished})`;
    }
}

async function setupVideoPlayer() {

    var iframe = document.querySelector('iframe');
    introVid = new VideoChoice(INTRO_VID_URL);

    // Initialize Vimeo player inside their respective VideoChoice objects
    introVid.player = new Vimeo.Player(iframe);
    // console.log(`Loaded intro video: ${introVid.getLog()}`);
    videoPageStartTime = getUTCTimestampNow(includeMilliseconds = false);

    function setupPlayerEvents(videoObj) {

        videoObj.player.on('play', function (data) {
            if (videoObj.startTimestamp == "") {
                videoObj.startTimestamp = getUTCTimestampNow(includeMilliseconds = false);
            }
            videoObj.logs.push(createLogEntry(data, "PLAYED AT"));
            videoObj.playbackPosition = parseVimeoResponse(data, "seconds");
        })
        videoObj.player.on('pause', function (data) {
            videoObj.pauseCount = videoObj.pauseCount + 1;
            videoObj.logs.push(createLogEntry(data, "PAUSED AT"));
        })
        videoObj.player.on('volumechange', function (data) {
            // NOTE: Some devices don't support the ability to set the volume of the video independently of
            // the system volume, so this event never fires on those devices.
            // glitch with Vimeo API: toggling mute (clicking the volume icon) always returns "1" (the maximum)
            // instead of "0" when mute is activated
            videoObj.logs.push(createLogEntry(data, "VOLUME CHANGED TO"));
        })
        videoObj.player.on('playbackratechange', function (data) {
            // NOTE: If the creator of the video has disabled the ability of the viewer to change the playback
            // rate, this event doesn't fire.
            videoObj.logs.push(createLogEntry(data, "VIDEO SPEED CHANGED TO"));
        })
        videoObj.player.on('seeked', function (data) {
            // Important playback positions in seconds
            let positionBeforeSeek = videoObj.playbackPosition;
            let positionAfterSeek = parseVimeoResponse(data, "seconds");
            // console.log(`Video ${videoObj.position} (ID ${videoObj.vid_id}): playback position BEFORE seek: ${positionBeforeSeek}`)
            if (positionBeforeSeek < positionAfterSeek) {
                // Don't allow this view to count as "watched" if the user skips ahead
                videoObj.logs.push(createLogEntry(data, "SEEKED AHEAD TO"));
                videoObj.skipped = true;
            } else if (positionBeforeSeek >= positionAfterSeek) {
                // Don't penalize the user for skipping behind
                videoObj.logs.push(createLogEntry(data, "SEEKED BEHIND TO"));
            }
            videoObj.playbackPosition = positionAfterSeek;

            if (positionAfterSeek <= SEEK_BEGINNING_THRESHOLD) {
                // If a user skips to the beginning, reset skips flag and re-allow this viewing
                videoObj.logs.push(createLogEntry(data, "SEEKED TO START"));
                videoObj.skipped = false;
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

            }

        })

    }
    setupPlayerEvents(introVid);
}

async function uploadVideoSelection() {

    const requestOptions = {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            user_agent: navigator.userAgent,
            vid_playback_time_start: introVid.startTimestamp,
            vid_playback_time_end: introVid.endTimestamp,
            vid_watch_count: introVid.watchCount,
            vid_logs: introVid.logs,
            vid_id: introVid.vid_id,
        })
    }
    // console.log(introVid.logs);
    const url = `${server}/intro_vid_info?key=${access_key}`;
    await fetch(url, requestOptions);
    window.location.href = `${server}/survey/videos?key=${access_key}&screen=1`;
}

function activateSelectionButton() {
    if (finalSelectionButton.hasAttribute("disabled")) {
        finalSelectionButton.disabled = false;
    }
}

////////

setupVideoPlayer();
