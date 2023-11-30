import json

import requests


class REDCapError(Exception):
    pass


def export_redcap_report(token: str, url: str, report_id: str | int) -> list[dict]:
    """Makes a REDCap API call for exporting a single report from a project.
    Returns a list of dicts, each containing a single record's fields as specified in the report.
    """
    request_params = {
        "token": token,
        "content": "report",
        "format": "json",
        "report_id": str(report_id),
        "csvDelimiter": "",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "returnFormat": "json",
    }
    r = requests.post(url, data=request_params)
    # print('>>> HTTP Status: ' + str(r.status_code))
    result = json.loads(r.text)
    if type(result) == dict and "error" in result:
        raise REDCapError(
            f"REDCap API returned an error while exporting report '{report_id}':\n{result['error']}"
        )
    return result


def import_record(token: str, url: str, records: list[dict]) -> int:
    """Makes a REDCap API call to import a single record into a project."""
    request_params = {
        "token": token,
        "content": "record",
        "action": "import",
        "format": "json",
        "type": "flat",
        "overwriteBehavior": "normal",
        "forceAutoNumber": "false",
        "data": json.dumps(records),
        "returnContent": "count",
        "returnFormat": "json",
    }
    r = requests.post(url, data=request_params)
    # print(">>> HTTP Status: " + str(r.status_code))
    result = json.loads(r.text)
    if type(result) == dict:
        if "error" in result:
            raise REDCapError(
                f"REDCap API returned an error while importing record(s) '{records}':\n{result['error']}"
            )
        if "count" in result:
            return int(result["count"])
    return 1


def export_video_ids(token: str, url: str, recordid: str, maxScreens: int) -> list[dict]:
    """Makes a REDCap API call to retrieve the video IDs."""
    request_params = {
        "token": token,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "csvDelimiter": "",
        "records[0]": recordid,
        "fields[0]": "access_key",
        "fields[1]": "video_a",
        "fields[2]": "video_b",
        "fields[3]": "video_complete",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }

    for screen in range(maxScreens):
        request_params[f"events[{screen}]"] = f"screen{screen+1}_arm_1"

    r = requests.post(url, data=request_params)
    result = json.loads(r.text)
    if type(result) == dict:
        if "error" in result:
            raise REDCapError(
                f"REDCap API returned an error while exporting video IDs for the record: '{recordid}':\n{result['error']}"
            )

    return result


def export_dcv_video_data(token: str, url: str, recordid: str, maxScreens: int) -> list[dict]:
    """Makes a REDCap API call to retrieve information about all of a survey participant's videos."""
    request_params = {
        "token": token,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "csvDelimiter": "",
        "records[0]": recordid,
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }
    for screen in range(maxScreens):
        request_params[f"events[{screen}]"] = f"screen{screen+1}_arm_1"

    r = requests.post(url, data=request_params)
    result = json.loads(r.text)
    if type(result) == dict:
        if "error" in result:
            raise REDCapError(
                f"REDCap API returned an error while exporting video data for the record: '{recordid}':\n{result['error']}"
            )

    return result


# def get_first_two_selected_videos(token: str, url: str, recordid: str) -> list[str]:
#     request_params = {
#         "token": token,
#         "content": "record",
#         "action": "export",
#         "format": "json",
#         "type": "flat",
#         "csvDelimiter": "",
#         "records[0]": recordid,
#         "fields[0]": "access_key",
#         "fields[1]": "video_selection",
#         "events[0]": "screen1_arm_1",
#         "events[1]": "screen2_arm_1",
#         "rawOrLabel": "raw",
#         "rawOrLabelHeaders": "raw",
#         "exportCheckboxLabel": "false",
#         "exportSurveyFields": "false",
#         "exportDataAccessGroups": "false",
#         "returnFormat": "json",
#     }
#     r = requests.post(url, data=request_params)
#     result = json.loads(r.text)
#     if type(result) == dict:
#         if "error" in result:
#             raise REDCapError(
#                 f"REDCap API returned an error while exporting video data for the record: '{recordid}':\n{result['error']}"
#             )
#     if type(result) == list and len(result) == 2:
#         if (
#             "video_selection" in result[0]
#             and len(result[0]["video_selection"]) > 0
#             and "video_selection" in result[1]
#             and len(result[1]["video_selection"]) > 0
#         ):
#             return [result[0]["video_selection"], result[1]["video_selection"]]
#         else:
#             print(f"[{recordid}] - missing video selections in REDCap")
#     return ["", ""]


def _get_screen_number(redcap_event_name: str, expected_event_name_prefix: str = "screen") -> int:
    """Parses a REDCap event name like 'screen2_arm_1' and returns the number that
    immediately follows the word 'screen' and precedes '_arm_'.
    """
    if not redcap_event_name.startswith(expected_event_name_prefix):
        return 0
    stop_index = redcap_event_name.find("_arm_")
    start_index = len(expected_event_name_prefix)
    screen_number = redcap_event_name[start_index:stop_index]
    if len(screen_number) > 0 and screen_number.isdecimal():
        return int(screen_number)
    return 0


def get_most_recent_screen(token: str, url: str, recordid: str, maxScreens: int) -> str:
    request_params = {
        "token": token,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "csvDelimiter": "",
        "records[0]": recordid,
        "fields[0]": "access_key",
        "fields[1]": "video_complete",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }

    for screen in range(maxScreens):
        request_params[f"events[{screen}]"] = f"screen{screen+1}_arm_1"

    r = requests.post(url, data=request_params)
    result = json.loads(r.text)
    expected_number_of_screens = maxScreens  # 3
    if type(result) == dict:
        if "error" in result:
            raise REDCapError(
                f"REDCap API returned an error while exporting most recent completed screen for the record: '{recordid}':\n{result['error']}"
            )
    most_recent_screen = 0
    if type(result) == list and len(result) == expected_number_of_screens:
        for screen_form in result:
            if "video_complete" in screen_form and "redcap_event_name" in screen_form:
                this_screen = _get_screen_number(screen_form["redcap_event_name"])
                if screen_form["video_complete"] == "2" and this_screen > most_recent_screen:
                    most_recent_screen = this_screen
                    # print(f"[{recordid}] Updated most recent screen from REDCap: {most_recent_screen}")
    return str(most_recent_screen)


def user_completed_survey(token: str, url: str, recordid: str) -> bool:
    """Makes a REDCap API call to check if a participant completed the survey.
    The survey is completed if any of these are true:
      * They completed the final "outro" questionnaire
      * They elected to skip the survey
    Returns True if the user completed the survey and False if the survey is incomplete.
    """
    request_params = {
        "token": token,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "csvDelimiter": "",
        "records[0]": recordid,
        "fields[0]": "skipped",
        "fields[1]": "outro_complete",
        "forms[0]": "basic_information",
        "forms[1]": "outro",
        "events[0]": "start_arm_1",
        "events[1]": "outroscreen_arm_1",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }
    r = requests.post(url, data=request_params)
    # print('>>> HTTP Status: ' + str(r.status_code))
    result = json.loads(r.text)
    if type(result) == dict and "error" in result:
        raise REDCapError(
            f"REDCap API returned an error while checking '{recordid}' for outro completion:\n{result['error']}"
        )

    # print(result)

    if len(result) > 0:
        skipped_survey = result[0]["skipped"] == "1"
        completed_questionnaire = len(result) > 1 and result[1]["outro_complete"] == "2"
        print(
            f"[{recordid}] skipped survey? {skipped_survey} / completed survey? {completed_questionnaire}"
        )

        return skipped_survey or completed_questionnaire
    return False
