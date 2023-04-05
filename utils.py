import os
import shutil
import subprocess


def cleanup_files(temp_media_path, media_path, single_aligned_path, dual_aligned_path, temp_subtitle_path):
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

def subprocess_call(command):
    subprocess.run(command, check=True)


def sub_call(command, single_path, dual_path):
    drop_index = []
    if not os.path.exists(single_path):
        drop_index += [-6, -7, -8, -9, -10]
    if not os.path.exists(dual_path):
        drop_index += [-1, -2, -3, -4, -5]
    for ind in drop_index:
        del command[ind]
    subprocess_call(command)
