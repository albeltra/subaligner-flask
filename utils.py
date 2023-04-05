import os
import shutil
import subprocess


def cleanup_files(temp_media_path: str,
                  media_path: str,
                  single_aligned_path: str,
                  dual_aligned_path: str,
                  temp_subtitle_path: str) -> None:
    """
    This function attempts to delete all temporary filese creating during subtitle alignment

    @param temp_media_path: Temporary media file to be deleted (.mp4 or .mkv)
    @param media_path: Original media path to be overwritten (.mp4 or .mkv)
    @param single_aligned_path: Path to single stage aligned subtitle
    @param dual_aligned_path: Path to dual stage aligned subtitle
    @param temp_subtitle_path: Temporary subtitle file to be deleted
    """
    try:
        shutil.move(temp_media_path, media_path)
    except:
        pass
    try:
        os.remove(single_aligned_path)
    except:
        pass
    try:
        os.remove(dual_aligned_path)
    except:
        pass
    try:
        os.remove(temp_subtitle_path)
    except:
        pass


def subprocess_call(command: list) -> None:
    """
    Wrapper function on subprocess.run for rq worker compatibility
    @param command: Subprocess compatible function call as a list. e.g. ["ls", "-a"]
    """
    subprocess.run(command, check=True)


def sub_call(command: list, single_path: str, dual_path: str) -> None:
    """
    This function determines which stages of subtitle alignment succeeded and embeds
    those that were successful into the original media file
    @param command: Command to embed aligned subtitles into media file
    @param single_path: Path to single stage aligned subtitle
    @param dual_path:  Path to dual stage aligned subtitle
    """
    drop_index = []
    if not os.path.exists(single_path):
        drop_index += [-6, -7, -8, -9, -10]
    if not os.path.exists(dual_path):
        drop_index += [-1, -2, -3, -4, -5]
    for ind in drop_index:
        del command[ind]
    subprocess_call(command)
