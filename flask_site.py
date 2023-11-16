import csv
import json
import random
import urllib.parse
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

# import emails
import mindlib
import redcap_helpers

FLASK_APP_URL_PATH = "/c2c-retention-dce/survey"

# The REDCap variable in this experiment's REDCap project that contains
# participants' access keys: C2C IDs that have been salted + hashed from an external Python script (c2c-id-hash)
HASHED_ID_EXPERIMENT_REDCAP_VAR = "access_key"

# The REDCap variable in the C2Cv3 REDCap project that contains the same hashed IDs
# HASHED_ID_C2C_REDCAP_VAR = "proj_pid_813"

# Configure this in tandem with c2c-id-hash.HASHED_ID_LENGTH (confirm w/ the REDCap projects)
EXPECTED_HASHED_ID_LENGTH = 12

PATH_TO_THIS_FOLDER = Path(__file__).resolve().parent

BUBBLE_MESSAGES = {
    "bad_key": "Invalid key.",
    "missing_key": "Missing access key.",
    "v01": "Failed to load videos. Please try starting the survey again.",  # missing cookies
    "v02": "Failed to load videos. Please try starting the survey again.",  # missing "screen" URL param
    "s01": "An error occured with loading the next page. Please contact UCI MIND IT and provide your access key.",  # Couldn't generate screen 3 due to missing video IDs
    "survey_completed": "This survey has been completed. Thank you for your participation!",
    "unknown": "Unknown error.",
    "incomplete_outro": "Please answer every question to proceed.",
}

# Total amount of screens in the survey
MAX_SCREENS = 7  # PROD VALUE: 7
MAX_VIDEOS = 2 * MAX_SCREENS

VIDEOS_FILE_PATH = Path(PATH_TO_THIS_FOLDER, "content", "videos.json")
VIDEOS = mindlib.json_to_dict(VIDEOS_FILE_PATH)
UNDEFINED_VID_ID_PLACEHOLDER = "UNDEFINED"

if MAX_VIDEOS > len(VIDEOS):
    # Total number of videos to allocate should be <= the amount of videos in videos.json
    raise Exception(
        f"Number of videos to allocate ({MAX_VIDEOS}) is greater than the number of videos that exist ({len(VIDEOS)}) in '{VIDEOS_FILE_PATH}'"
    )

# CSV file containing 2 columns:
#   (1) "record_id"  = C2Cv3 ID (record_id in the C2Cv3 REDCap project - PID 696)
#   (2) "access_key" = hashed ID unique to this experiment
#                      (record_id in the C2C - Retention - Discrete Choice Video (DCV) project - PID 813)
ID_FILE = Path(PATH_TO_THIS_FOLDER, "content", "c2cv3-ids-access-keys.csv")

# Used to sanitize ID input
SUSPICIOUS_CHARS = [";", ":", "&", '"', "'", "`", ">", "<", "{", "}", "|", ".", "%"]

flask_app = Flask(__name__)
# flask_app.config["APPLICATION_ROOT"] = URL_PREFIX
flask_app.config.from_file("secrets.json", load=json.load)  # JSON keys must be in ALL CAPS


################################
############ HELPERS ###########


def create_id_mapping(id_file: Path = ID_FILE, reversed: bool = False) -> dict[str:str]:
    """Returns a dict that maps access keys (hashed C2C IDs) to their corresponding original C2C IDs.
    If `reversed` == True, original C2C IDs will be mapped to their access keys.
    IDs and access keys are stored in a local CSV file (`id_file`).
    """
    mapping = dict()

    with open(id_file) as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            # print(row["record_id"], row["access_key"])
            try:
                if reversed:
                    mapping[row["record_id"]] = row["access_key"]
                else:
                    mapping[row["access_key"]] = row["record_id"]
            except KeyError as k:
                print(
                    f"***** Configure the IDs CSV '{id_file}' to contain columns 'record_id' and 'access_key'."
                )
                raise k
    # print(mapping)
    return mapping


ACCESS_KEYS_TO_C2C_IDS = create_id_mapping()
C2C_IDS_TO_ACCESS_KEYS = create_id_mapping(reversed=True)
print(f"* Loaded {len(ACCESS_KEYS_TO_C2C_IDS)} access keys from {ID_FILE}")
print(f"* Loaded {len(C2C_IDS_TO_ACCESS_KEYS)} C2C IDs from {ID_FILE}")
if len(C2C_IDS_TO_ACCESS_KEYS) == 0:
    raise Exception("***** Mapping of C2C IDs to access keys has 0 entries.")
if len(ACCESS_KEYS_TO_C2C_IDS) == 0:
    raise Exception("***** Mapping of access keys to C2C IDs has 0 entries.")


def sanitize_key(key_from_html_string: str) -> str:
    """URL-decodes and sanitizes user-provided 'access keys' (intended to be hashed C2C IDs).
    Returns an empty string if a string fails sanitization.
    """
    result = urllib.parse.unquote_plus(key_from_html_string).strip()
    # Hashed IDs MUST be of a pre-specified length - anything else is suspicious.
    if len(result) == EXPECTED_HASHED_ID_LENGTH and not any(
        [s in result for s in SUSPICIOUS_CHARS]
    ):
        return result
    return ""


# def check_email_addr_and_send_email(
#     user_submitted_email_address: str,
#     our_email_server_address: str,
#     our_from_email_address: str,
#     our_from_email_display_name: str,
#     our_from_email_password: str,
# ) -> None:
#     """If applicable, sends a reminder email to a user containing their access key for this experiment.
#     Unused because functionality related to sending emails has been removed from the requirements.
#     """
#     print(f"[{user_submitted_email_address}] - checking email to send access key")
#     active_c2cv3_emails = redcap_helpers.export_redcap_report(
#         flask_app.config["C2CV3_API_TOKEN"],
#         flask_app.config["REDCAP_API_URL"],
#         flask_app.config["C2CV3_EMAILS_REPORT_ID"],
#     )
#     for record in active_c2cv3_emails:
#         if (
#             "start_email" in record
#             and "record_id" in record
#             and user_submitted_email_address.lower() == record["start_email"].lower()
#         ):
#             # User's email matches one found in the report
#             c2c_id = record["record_id"]
#             if c2c_id not in C2C_IDS_TO_ACCESS_KEYS:
#                 print(f"[{user_submitted_email_address}] C2C ID {c2c_id} is not active")
#                 return
#             access_key_to_send = C2C_IDS_TO_ACCESS_KEYS[c2c_id]
#             if len(access_key_to_send) == 0:
#                 print(
#                     f"[{user_submitted_email_address}] C2C ID {c2c_id} is active, but doesn't have an access key for this experiment"
#                 )
#                 return
#             emails.send_mail(
#                 record["start_email"],
#                 access_key_to_send,
#                 our_email_server_address,
#                 our_from_email_address,
#                 our_from_email_display_name,
#                 our_from_email_password,
#             )
#             return
#     print(f"[{user_submitted_email_address}] not found in the list of active C2C participants")
#     return


def get_user_agent() -> str:
    """Get the user-agent information (browser and device type) of the site's visitors"""
    return request.headers.get("User-Agent")


################################
########### ENDPOINTS ##########


@flask_app.route("/", methods=["GET"])
def index():
    if "error_code" in request.args and len(request.args["error_code"]) > 0:
        error_code = request.args["error_code"]
        if error_code not in BUBBLE_MESSAGES:
            error_code = "unknown"
        return render_template("index.html", error_message=BUBBLE_MESSAGES[error_code])

    if "msg" in request.args and len(request.args["msg"]) > 0:
        message_code = request.args["msg"]
        if message_code not in BUBBLE_MESSAGES:
            return render_template("index.html", error_message=BUBBLE_MESSAGES["unknown"])
        return render_template("index.html", info_message=BUBBLE_MESSAGES[message_code])

    # if "sent_email" in request.args and len(request.args["sent_email"]) > 0:
    #     return render_template("email_sent.html")

    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            print("This key failed sanitization:", request.args["key"])
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        if hashed_id not in ACCESS_KEYS_TO_C2C_IDS:
            print(f"[{hashed_id}] access key not found.")
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        existing_dcv_video_data = redcap_helpers.export_dcv_video_data(
            flask_app.config["C2C_DCV_API_TOKEN"],
            flask_app.config["REDCAP_API_URL"],
            hashed_id,
            MAX_SCREENS,
        )

        # print(survey_record)

        already_started_survey = len(existing_dcv_video_data) > 0
        print(
            f"[{hashed_id}] already started survey? {already_started_survey} (have {len(existing_dcv_video_data)} existing video instruments)"
        )
        if already_started_survey:
            # The user has generated a set of videos already - they may have finished the survey already
            # Got video data but the user hasn't finished the survey yet - don't assign any more videos
            # print(existing_dcv_video_data)
            survey_videos = []  # will be 2 x MAX_SCREENS number of videos
            for r in existing_dcv_video_data:
                existing_vid_a_id = r["video_a"]
                existing_vid_b_id = r["video_b"]
                if (
                    len(existing_vid_a_id) > 0
                    and existing_vid_a_id != UNDEFINED_VID_ID_PLACEHOLDER
                    and len(existing_vid_b_id) > 0
                    and existing_vid_b_id != UNDEFINED_VID_ID_PLACEHOLDER
                    and len(survey_videos) < (MAX_VIDEOS)
                ):
                    survey_videos.append(r["video_a"])
                    survey_videos.append(r["video_b"])
            most_recent_completed_screen_from_redcap = redcap_helpers.get_most_recent_screen(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                hashed_id,
                maxScreens=MAX_SCREENS,
            )
            print(
                f"[{hashed_id}] Experiment record (C2C ID {ACCESS_KEYS_TO_C2C_IDS[hashed_id]}) already created with videos {survey_videos} and completed screen {most_recent_completed_screen_from_redcap}"
            )
            if int(most_recent_completed_screen_from_redcap) == MAX_SCREENS:
                # If they completed the final screen, serve the completion message
                # return redirect(url_for("index", msg="survey_completed"), code=301)
                return redirect(url_for("outro", key=hashed_id), code=301)
        else:
            # New survey participant
            # Shuffle all video keys, and save the first survey from the shuffled list
            video_ids = list(VIDEOS.keys())
            random.shuffle(video_ids)
            survey_videos = video_ids[0:MAX_VIDEOS]

            start_time = mindlib.timestamp_now()

            # Add the record to the experiment's REDCap project and start the experiment
            new_record = [
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "c2c_id": ACCESS_KEYS_TO_C2C_IDS[hashed_id],
                    "survey_tm_start": start_time,
                    "user_agent": get_user_agent(),
                },
            ]
            survey_videos_index = 0
            for screen in range(MAX_SCREENS):
                screen_record = {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": f"screen{screen + 1}_arm_1",
                    "video_a": survey_videos[survey_videos_index],
                    "video_b": survey_videos[survey_videos_index + 1],
                }
                new_record.append(screen_record)
                survey_videos_index += 2

            print(
                f"[{hashed_id}] Creating NEW record (C2C ID {ACCESS_KEYS_TO_C2C_IDS[hashed_id]}) with videos {survey_videos}"
            )
            redcap_helpers.import_record(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                new_record,
            )

            resp = redirect(url_for("intro", key=hashed_id), code=301)

        if already_started_survey:
            resp = redirect(
                url_for("videos", key=hashed_id, screen=most_recent_completed_screen_from_redcap),
                code=301,
            )

        for i in range(len(survey_videos)):
            resp.set_cookie(key=f"v{i + 1}_id", value=survey_videos[i])
            resp.set_cookie(key=f"v{i + 1}_url", value=VIDEOS[survey_videos[i]])

        # Set completed_screen cookie: the most recent screen the user completed
        # Needs to be served in a path because the JS script has limited scope to where it can place the cookie
        if not already_started_survey:
            # Fresh start: user has no REDCap data
            resp.set_cookie(key="completed_screen", value="0", path=FLASK_APP_URL_PATH)
            print(f'[{hashed_id}] fresh start: set "completed_screen" to 0')
        elif "completed_screen" not in request.cookies:
            # User started the survey (they have REDCap data) and they cleared their cookies
            # Allows users to resume taking the survey
            resp.set_cookie(
                key="completed_screen",
                value=most_recent_completed_screen_from_redcap,
                path=FLASK_APP_URL_PATH,
            )
            print(
                f'[{hashed_id}] cleared cookies but is resuming survey - set "completed_screen" to {most_recent_completed_screen_from_redcap}'
            )
        return resp
    return render_template("index.html")


@flask_app.route("/check", methods=["GET", "POST"])
def check():
    """Originally used to check if a user input their access key or their C2C email address.
    No longer needed because functionality related to the email address has been removed from the requirements.
    """
    # "GET" request is needed so users can be redirected properly instead of seeing a "request not allowed" error
    # Endpoint that receives data from a user that manually input their access key (hashed ID) to an HTML form on "/"
    # Redirect to "/" with that key to check
    if "key" in request.form and len(request.form["key"]) > 0:
        user_provided_key = request.form["key"].strip()
        # if mindlib.is_valid_email_address(user_provided_key):
        #     check_email_addr_and_send_email(
        #         user_provided_key,
        #         flask_app.config["MAIL_SMTP_SERVER_ADDR"],
        #         flask_app.config["MAIL_C2C_NOREPLY_ADDR"],
        #         flask_app.config["MAIL_C2C_NOREPLY_DISPLAY_NAME"],
        #         flask_app.config["MAIL_C2C_NOREPLY_PASS"],
        #     )
        #     return redirect(url_for("index", sent_email="1"), code=301)

        # Not a valid email, so try interpreting this as a literal access key
        # Don't have to do any intensive sanitizing or checking here; index() will do that
        return redirect(url_for("index", key=user_provided_key), code=301)

    # Don't allow users to visit this endpoint directly
    return redirect(url_for("index"), code=301)


@flask_app.route("/intro", methods=["GET"])
def intro():
    # User visits this endpoint if they are a new survey participant
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
    return render_template("intro.html", key=hashed_id)


@flask_app.route("/videos", methods=["GET"])
def videos():
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            print(f"This key failed sanitization: {request.args['key']}")
            return redirect(url_for("index", error_code="bad_key"), code=301)

        if hashed_id not in ACCESS_KEYS_TO_C2C_IDS:
            print(f"[{hashed_id}] access key not found.")
            return redirect(url_for("index", error_code="bad_key"))

        if (
            "screen" in request.args
            and len(request.args["screen"]) > 0
            and "completed_screen" in request.cookies
        ):
            try:
                scr = int(request.args["screen"])
            except ValueError:
                return render_template("videos.html")

            # Check for previous screen completion
            try:
                most_recent_completed_screen = int(request.cookies["completed_screen"])
                print(
                    f"[{hashed_id}] Most recent completed screen (via cookie): {most_recent_completed_screen}"
                )
                screen_to_serve = most_recent_completed_screen + 1
            except ValueError:
                return render_template("videos.html")

            if scr != screen_to_serve:
                # From the user's perspective: the URL will contain an incorrect screen number but
                # the correct screen will be served
                print(
                    f"[{hashed_id}] Incorrect screen accessed ({scr})!! Serving screen {screen_to_serve}"
                )
                scr = screen_to_serve

            if scr > MAX_SCREENS:
                # could consult cookie here too
                most_recent_completed_screen_from_redcap = redcap_helpers.get_most_recent_screen(
                    flask_app.config["C2C_DCV_API_TOKEN"],
                    flask_app.config["REDCAP_API_URL"],
                    hashed_id,
                    maxScreens=MAX_SCREENS,
                )
                if int(most_recent_completed_screen_from_redcap) == MAX_SCREENS:
                    # If they completed the final screen, serve the completion message
                    return redirect(url_for("outro", key=hashed_id), code=301)
                return render_template("videos.html")

            # Get the correct video positions for the current screen:
            # screen 1 = videos 1 and 2,
            # screen 2 = videos 3 and 4,
            # screen 3 = videos 5 and 6, etc...
            vid_a_pos = (scr * 2) - 1
            vid_b_pos = scr * 2
            print(f"[{hashed_id}] Starting screen {scr} (videos {vid_a_pos} & {vid_b_pos})")

            if most_recent_completed_screen < MAX_SCREENS:
                # Continue the video survey
                return render_template(
                    "videos.html", screen=scr, vid_a_position=vid_a_pos, vid_b_position=vid_b_pos
                )
            # After the videos are completed, go to the outro questionnaire
            return redirect(url_for("outro", key=hashed_id), code=301)

        else:
            # No "screen" URL parameter or "completed_screen" cookie is missing
            return redirect(url_for("index", error_code="v02"), code=301)
    return redirect(url_for("index", error_code="missing_key"), code=301)


@flask_app.route("/outro", methods=["GET", "POST"])
def outro():
    # error_code = "key" for redirect, error_message = BUBBLE_MESSAGES["key"] for render

    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])

        if not redcap_helpers.user_completed_outro(
            flask_app.config["C2C_DCV_API_TOKEN"], flask_app.config["REDCAP_API_URL"], hashed_id
        ):
            # if the user did NOT complete the outro, upload their responses from html
            if request.method == "POST":
                # POST request = page form has been completed and data will be uploaded
                # print(request.form)
                redcap_outro_page_record = {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "outroscreen_arm_1",
                    "outro_q1": f"{request.form['outro_q1']}",
                    "outro_q2": f"{request.form['outro_q2']}",
                    "outro_q3": f"{request.form['outro_q3']}",
                    "outro_q4": f"{request.form['outro_q4']}",
                    "outro_q5": f"{request.form['outro_q5']}",
                    "outro_q6": f"{request.form['outro_q6']}",
                    "outro_q7": f"{request.form['outro_q7']}",
                    "outro_q8": f"{request.form['outro_q8']}",
                    "outro_q9": f"{request.form['outro_q9']}",
                    "outro_q10": f"{request.form['outro_q10']}",
                    "outro_complete": 2,
                }
                # print(f"[{hashed_id}] outro responses: {redcap_outro_page_record}")
                redcap_helpers.import_record(
                    flask_app.config["C2C_DCV_API_TOKEN"],
                    flask_app.config["REDCAP_API_URL"],
                    [redcap_outro_page_record],
                )

                end_time = mindlib.timestamp_now()
                outro_basic_information_record = {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "redcap_event_name": "start_arm_1",
                    "survey_tm_end": end_time,
                    "basic_information_complete": "2",
                }
                redcap_helpers.import_record(
                    flask_app.config["C2C_DCV_API_TOKEN"],
                    flask_app.config["REDCAP_API_URL"],
                    [outro_basic_information_record],
                )
                print(f"[{hashed_id}] finished survey at {end_time}")

                return redirect(url_for("thankyou"), code=301)
            else:
                # GET request = visiting this page in the web browser
                survey_questions_path = Path(
                    PATH_TO_THIS_FOLDER, "content", "survey_questions.txt"
                )
                survey_choices_path = Path(PATH_TO_THIS_FOLDER, "content", "survey_choices.txt")
                check_choices_path = Path(PATH_TO_THIS_FOLDER, "content", "check_choice.txt")

                with open(survey_questions_path, "r") as survey_questions_infile:
                    questions = [line.strip() for line in survey_questions_infile.readlines()]

                with open(survey_choices_path, "r") as survey_choices_infile:
                    choices = [line.strip() for line in survey_choices_infile.readlines()]

                with open(check_choices_path, "r") as check_choices_infile:
                    check_choices = [line.strip() for line in check_choices_infile.readlines()]

                return render_template(
                    "outro.html", questions=questions, choices=choices, check_choices=check_choices
                )
        else:
            print(f"[{hashed_id}] Already completed outro survey")
            return redirect(url_for("thankyou"), code=301)

    return redirect(url_for("index", msg="missing_key"), code=301)


@flask_app.route("/thankyou", methods=["GET"])
def thankyou():
    """Static page to notify users of survey completion"""
    return render_template("thankyou.html")


@flask_app.errorhandler(404)
def page_not_found(err):
    return render_template("404.html"), 404
