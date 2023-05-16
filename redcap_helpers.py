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
    # print('>>> HTTP Status: ' + str(r.status_code))
    result = json.loads(r.text)
    if type(result) == dict:
        if "error" in result:
            raise REDCapError(
                f"REDCap API returned an error while importing record(s) '{records}':\n{result['error']}"
            )
        if "count" in result:
            return int(result["count"])
    return 1


def export_video_ids(token: str, url: str, recordid: str) -> list[dict]:
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
        "events[0]": "screen1_arm_1",
        "events[1]": "screen2_arm_1",
        "events[2]": "screen3_arm_1",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }
    r = requests.post(url, data=request_params)
    result = json.loads(r.text)
    if type(result) == dict:
        if "error" in result:
            raise REDCapError(
                f"REDCap API returned an error while exporting video IDs for the record: '{recordid}':\n{result['error']}"
            )

    return result
