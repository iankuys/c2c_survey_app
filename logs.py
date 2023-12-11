import mindlib


def write_log(msg: str, key: str = "", src: str = "", include_timestamp: bool = True) -> None:
    log_str = f"[{key}] {src} - {msg}"
    if include_timestamp:
        log_str = f"[{mindlib.timestamp_now(utc=True)}] [{key}] {src} - {msg}"
    print(log_str)
    return
