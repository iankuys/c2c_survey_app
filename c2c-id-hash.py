# Standalone script to generate "keys" (hashed IDs) of C2C participants.
# Outputs a CSV file that could be imported to a REDCap project for a given experiment.

import csv
import hashlib

import requests

import mindlib

CSV_FILENAME = "c2c_hashed_ids.csv"

HASH_SALT_PREFIX = "retention_dce"
HASHED_ID_LENGTH = 10
HASHED_ID_CSV_COLUMN = "retention_dce_access_key"


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


def hash_one_string(
    input_string: str, length=64, salt_prefix: str = "", salt_suffix: str = ""
) -> str:
    """Creates a SHA-256 hash digest for a given string (default length is the maximum of 64 digits).
    If length < 64, the resulting digest is truncated to that amount of digits.
    If length >= 64, the resulting digest will remain 64 digits long.
    Provide strings to salt_prefix and/or salt_suffix as necessary to produce different hashes."""
    h = hashlib.new("sha256")

    to_hash = f"{salt_prefix}{input_string}{salt_suffix}"
    h.update(to_hash.encode())

    result = h.hexdigest()
    # Each character adds to the total space of possible hashes by a factor of 16
    # 1 char = 16 possible hashes
    # 2 chars = 16*16 = 256 possible hashes
    # 3 chars = 16^3 = 4096 possible hashes, etc...
    return result[:length]


def create_hashed_ids(
    ids: list[str], hashed_id_length: int, pre_hash_prefix: str, max_retry_count=8
) -> dict[str:str]:
    """Returns a dictionary that maps SHA256-hashed IDs to their source C2C IDs."""
    hashes_to_original_ids = dict()
    for record_id in ids:
        the_hash = hash_one_string(record_id, length=hashed_id_length, salt_prefix=pre_hash_prefix)
        # print(f"Hashed {id} to {the_hash}")

        # Check for duplicates and retry, updating the salt for the newest ID along the way
        retry_count = 0
        while the_hash in hashes_to_original_ids and retry_count <= max_retry_count:
            retry_count += 1
            print(
                f"   Collision found: {the_hash} (IDs {record_id} and {hashes_to_original_ids[the_hash]}), retrying (attempt {retry_count})"
            )
            the_hash = hash_one_string(
                record_id,
                length=hashed_id_length,
                salt_prefix=pre_hash_prefix,
                salt_suffix=str(retry_count),
            )
        if retry_count >= max_retry_count:
            print(
                f"Failed to hash ID {record_id}, not adding to the CSV (tried {max_retry_count} times)"
            )
            continue

        hashes_to_original_ids[the_hash] = record_id

    return hashes_to_original_ids


def write_csv(csv_filename: str, hashes_to_real_ids: dict[str:str], hashed_id_column_name) -> None:
    """Write the CSV to contain the complete mapping of C2C ID to the new hashed IDs."""
    with open(csv_filename, "w+", newline="") as outfile:
        fieldnames = ["record_id", "redcap_event_name", "c2c_id", hashed_id_column_name]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)

        writer.writeheader()
        for i, hashed_id in enumerate(hashes_to_real_ids, start=1):
            writer.writerow(
                {
                    "record_id": i,
                    "redcap_event_name": "start_arm_1",
                    "c2c_id": hashed_ids[hashed_id],
                    hashed_id_column_name: hashed_id,
                }
            )
    return


if __name__ == "__main__":
    secrets = mindlib.json_to_dict("secrets.json", required_fields={"c2cv3_api_token", "api_url"})
    print("Getting IDs from the C2C REDCap project....")
    ids = export_original_c2c_ids(secrets["c2cv3_api_token"], secrets["api_url"])

    print("\nHashing IDs....")
    hashed_ids = create_hashed_ids(ids, HASHED_ID_LENGTH, HASH_SALT_PREFIX)
    print(f"Hashed {len(hashed_ids)}/{len(ids)} IDs ({len(hashed_ids)/len(ids)*100:.2f}%)")

    # Build a CSV of "record_id" and hashed IDs that can be imported to the new REDCap project for this experiment
    write_csv(CSV_FILENAME, hashed_ids, HASHED_ID_CSV_COLUMN)
    print(f"\nWrote '{CSV_FILENAME}'")
