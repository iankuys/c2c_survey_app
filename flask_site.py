import csv
import json
import random
import urllib.parse
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

# import emails
import logs
import mindlib
import redcap_helpers

FLASK_APP_URL_PATH = "/retention/survey"

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
    "v01": "Failed to load videos. Please try starting the survey again.",  # unused
    "v02": "Failed to load videos. Please try starting the survey again.",  # missing "screen" URL param
    "s01": "An error occured with loading the next page. Please contact UCI MIND IT and provide your access key.",  # Couldn't generate screen 3 due to missing video IDs
    "survey_completed": "This survey has been completed. Thank you for your participation!",
    "unknown": "Unknown error.",
    "incomplete_outro": "Please answer every question to proceed.",
    "no_start": "Please begin the survey by providing your access key.",
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
flask_app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


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
            logs.write_log(
                "access key not found",
                hashed_id,
                "index",
            )
            return render_template("index.html", error_message=BUBBLE_MESSAGES["bad_key"])

        already_finished_survey = redcap_helpers.user_completed_survey(
            flask_app.config["C2C_DCV_API_TOKEN"],
            flask_app.config["REDCAP_API_URL"],
            hashed_id,
        )

        if "skip" in request.args and request.args["skip"] == "1" and not already_finished_survey:
            # First time user has skipped the survey:
            skip_time = mindlib.timestamp_now()
            skipped_record = [
                {
                    HASHED_ID_EXPERIMENT_REDCAP_VAR: hashed_id,
                    "c2c_id": ACCESS_KEYS_TO_C2C_IDS[hashed_id],
                    "user_agent": get_user_agent(),
                    "survey_tm_end": skip_time,
                    "skipped": "1",
                    "basic_information_complete": "2",
                }
            ]
            redcap_helpers.import_record(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                skipped_record,
            )
            logs.write_log("elected to skip the survey; imported REDCap data", hashed_id, "index")
            return redirect(url_for("thankyou"), code=301)

        if already_finished_survey:
            logs.write_log("already finished survey", hashed_id, "index")
            return redirect(url_for("thankyou"), code=301)

        existing_dcv_video_data = redcap_helpers.export_dcv_video_data(
            flask_app.config["C2C_DCV_API_TOKEN"],
            flask_app.config["REDCAP_API_URL"],
            hashed_id,
            MAX_SCREENS,
        )

        # print(survey_record)

        already_started_survey = len(existing_dcv_video_data) > 0
        logs.write_log(
            f"already started survey? {already_started_survey} (have {len(existing_dcv_video_data)} existing video instruments)",
            hashed_id,
            "index",
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
                max_screens=MAX_SCREENS,
            )
            logs.write_log(
                f"Experiment record (C2C ID {ACCESS_KEYS_TO_C2C_IDS[hashed_id]}) already created with videos {survey_videos} and completed screen {most_recent_completed_screen_from_redcap}",
                hashed_id,
                "index",
            )
            if most_recent_completed_screen_from_redcap == MAX_SCREENS:
                # If they completed the final screen, serve the completion message
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

            logs.write_log(
                f"Creating NEW record (C2C ID {ACCESS_KEYS_TO_C2C_IDS[hashed_id]}) with videos {survey_videos}",
                hashed_id,
                "index",
            )
            redcap_helpers.import_record(
                flask_app.config["C2C_DCV_API_TOKEN"],
                flask_app.config["REDCAP_API_URL"],
                new_record,
            )

            # return redirect(url_for("intro", key=hashed_id), code=301)

        # return redirect(
        #     url_for("videos", key=hashed_id, screen=most_recent_completed_screen_from_redcap + 1),
        #     code=301,
        # )
        return redirect(url_for("intro", key=hashed_id), code=301)
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
        logs.write_log("accessed, uploading initial intro data....", hashed_id, "intro")
        initial_intro_data = {
            "access_key": hashed_id,
            "redcap_event_name": "introscreen_arm_1",
            "page_served": mindlib.timestamp_now(),
        }
        redcap_helpers.import_record(
            flask_app.config["C2C_DCV_API_TOKEN"],
            flask_app.config["REDCAP_API_URL"],
            [initial_intro_data],
        )
        return render_template("intro.html", key=hashed_id)
    return redirect(url_for("index", error_code="bad_key"), code=301)


@flask_app.route("/videos", methods=["GET"])
def videos():
    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])
        if len(hashed_id) < 1:
            print(f"This key failed sanitization: {request.args['key']}")
            return redirect(url_for("index", error_code="bad_key"), code=301)

        if hashed_id not in ACCESS_KEYS_TO_C2C_IDS:
            logs.write_log("access key not found.", hashed_id, "videos")
            return redirect(url_for("index", error_code="bad_key"))

        (
            most_recent_completed_screen_number,
            this_screens_ids,
        ) = redcap_helpers.get_most_recent_screen(
            flask_app.config["C2C_DCV_API_TOKEN"],
            flask_app.config["REDCAP_API_URL"],
            hashed_id,
            max_screens=MAX_SCREENS,
            include_video_ids=True,
        )
        if most_recent_completed_screen_number < MAX_SCREENS and this_screens_ids != []:
            this_screen = most_recent_completed_screen_number + 1

            # Get the correct video positions for the current screen:
            # screen 1 = videos 1 and 2,
            # screen 2 = videos 3 and 4,
            # screen 3 = videos 5 and 6, etc...
            vid_a_pos = (this_screen * 2) - 1
            vid_b_pos = this_screen * 2
            logs.write_log(
                f"Starting screen {this_screen} (videos {vid_a_pos} & {vid_b_pos}) {this_screens_ids}",
                hashed_id,
                "videos",
            )
            vid_a_url = VIDEOS[this_screens_ids[0]]
            vid_b_url = VIDEOS[this_screens_ids[1]]
            return render_template(
                "videos.html",
                screen=this_screen,
                max_screens=MAX_SCREENS,
                vid_a_position=vid_a_pos,
                vid_a_id=this_screens_ids[0],
                vid_a_url=vid_a_url,
                vid_b_position=vid_b_pos,
                vid_b_id=this_screens_ids[1],
                vid_b_url=vid_b_url,
            )
        # Failsafe to redirect to the outro questionnaire
        return redirect(url_for("outro", key=hashed_id), code=301)
    return redirect(url_for("index", error_code="missing_key"), code=301)


@flask_app.route("/outro", methods=["GET", "POST"])
def outro():
    # error_code = "key" for redirect, error_message = BUBBLE_MESSAGES["key"] for render

    if "key" in request.args and len(request.args["key"]) > 0:
        hashed_id = sanitize_key(request.args["key"])

        if not redcap_helpers.user_completed_survey(
            flask_app.config["C2C_DCV_API_TOKEN"], flask_app.config["REDCAP_API_URL"], hashed_id
        ):
            # if the user did NOT complete the outro, upload their responses from html
            if request.method == "POST":
                # POST request = page form has been completed and data will be uploaded
                # print(request.form)
                end_time = mindlib.timestamp_now()
                logs.write_log("finished final questionnaire", hashed_id, "outro")

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
                redcap_helpers.import_record(
                    flask_app.config["C2C_DCV_API_TOKEN"],
                    flask_app.config["REDCAP_API_URL"],
                    [redcap_outro_page_record],
                )

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
                logs.write_log("survey complete", hashed_id, "outro")

                return redirect(url_for("thankyou"), code=301)
            else:
                # GET request = visiting this page in the web browser
                logs.write_log("rendering questionnaire", hashed_id, "outro")
                questions_path = Path(PATH_TO_THIS_FOLDER, "content", "q_questions.txt")
                agree_choices_path = Path(PATH_TO_THIS_FOLDER, "content", "q_agree_choices.txt")
                final_question_choices_path = Path(
                    PATH_TO_THIS_FOLDER, "content", "q_final_question_choices.txt"
                )

                with open(questions_path, "r") as questions_infile:
                    questions = [line.strip() for line in questions_infile.readlines()]

                with open(agree_choices_path, "r") as agree_choices_infile:
                    agree_choices = [line.strip() for line in agree_choices_infile.readlines()]

                with open(final_question_choices_path, "r") as final_choices_infile:
                    final_question_choices = [
                        line.strip() for line in final_choices_infile.readlines()
                    ]

                return render_template(
                    "outro.html",
                    max_screens=MAX_SCREENS,
                    questions=questions,
                    agree_choices=agree_choices,
                    final_question_choices=final_question_choices,
                )
        else:
            logs.write_log("Already completed outro questionnaire", hashed_id, "outro")
            return redirect(url_for("thankyou"), code=301)

    return redirect(url_for("index", msg="missing_key"), code=301)


@flask_app.route("/thankyou", methods=["GET"])
def thankyou():
    """Static page to notify users of survey completion"""
    return render_template("thankyou.html")


@flask_app.errorhandler(404)
def page_not_found(err):
    return render_template("404.html"), 404


@flask_app.after_request
def after_request(response):
    # Prevents the web browser from caching server responses
    # Thank you Feraru Silviu Marian and Mohamed Diaby! https://stackoverflow.com/a/50173687
    # And extra opinions from https://stackoverflow.com/a/34067710
    # Extra options for "Cache-Control" (might be unnecessary): "no-cache, must-revalidate, public"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    # response.headers["Expires"] = 0
    # response.headers["Pragma"] = "no-cache"
    return response
