# app/pipelines/file_utils.py

import os
import uuid

LOCAL_STORAGE = "/app/storage"  # local storage path


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def save_image_for_user(user_id: int, image_bytes: bytes, ext: str = ".png") -> str:
    """
    Αποθηκεύει εικόνα (PNG/JPG etc.) και επιστρέφει URL.
    """
    folder = f"{LOCAL_STORAGE}/{user_id}/images"
    ensure_dir(folder)

    filename = f"{uuid.uuid4().hex}{ext}"
    full_path = f"{folder}/{filename}"

    with open(full_path, "wb") as f:
        f.write(image_bytes)

    return f"/storage/{user_id}/images/{filename}"


def save_equation_image_for_user(user_id: int, image_bytes: bytes) -> str:
    folder = f"{LOCAL_STORAGE}/{user_id}/equations"
    ensure_dir(folder)

    filename = f"{uuid.uuid4().hex}.png"
    full_path = f"{folder}/{filename}"

    with open(full_path, "wb") as f:
        f.write(image_bytes)

    return f"/storage/{user_id}/equations/{filename}"


def save_table_image_for_user(user_id: int, image_bytes: bytes) -> str:
    folder = f"{LOCAL_STORAGE}/{user_id}/tables"
    ensure_dir(folder)

    filename = f"{uuid.uuid4().hex}.png"
    full_path = f"{folder}/{filename}"

    with open(full_path, "wb") as f:
        f.write(image_bytes)

    return f"/storage/{user_id}/tables/{filename}"
