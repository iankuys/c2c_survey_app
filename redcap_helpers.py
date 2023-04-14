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
