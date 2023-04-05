import hashlib

import requests

import mindlib


def export_original_c2c_ids(api_token: str, api_url: str) -> list[str]:
    data = {
        "token": api_token,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "csvDelimiter": "",
        "fields[0]": "record_id",
        "events[0]": "enroll_arm_1",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }
    r = requests.post(api_url, data=data)
    # print("HTTP Status: " + str(r.status_code))
    response_dict = r.json()
    return [r["record_id"] for r in response_dict if "record_id" in r]


def hash_one_string(input_string: str, salt_suffix: str = "") -> str:
    h = hashlib.new("sha256")

    to_hash = f"{input_string}{salt_suffix}"
    h.update(to_hash.encode())

    return h.hexdigest()


def create_hashed_ids(ids: list[str]) -> dict[str:str]:
    hashes_to_original_ids = dict()
    for record_id in ids:
        the_hash = hash_one_string(record_id)
        # print(f"Hashed {id} to {the_hash}")

        # Check for duplicates and retry, updating the salt for the newest ID along the way
        retry_count = 0
        while the_hash in hashes_to_original_ids:
            retry_count += 1
            print(
                f"   Collision found: {record_id} and {hashes_to_original_ids[the_hash]}, retrying (attempt {retry_count})"
            )
            the_hash = hash_one_string(record_id, salt_suffix=str(retry_count))

        hashes_to_original_ids[the_hash] = record_id

    return hashes_to_original_ids


if __name__ == "__main__":
    secrets = mindlib.json_to_dict(
        "secrets.json", required_fields={"c2cv3_api_token", "api_url"}
    )
    print("Getting IDs from the C2C REDCap project....")
    ids = export_original_c2c_ids(secrets["c2cv3_api_token"], secrets["api_url"])
    print(f"Got {len(ids)} IDs.")

    print("\nHashing IDs....")
    hashed_ids = create_hashed_ids(ids)
    print(f"Hashed {len(hashed_ids)} IDs.")
    # print(hashed_ids)
    # print(hash_one_string("1"))

    # Build a CSV of "record_id" and "hashed_id" that can be imported to the new REDCap project for this experiment
    # TODO
