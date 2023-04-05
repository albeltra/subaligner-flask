import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Flask, request

from utils import subprocess_call, sub_call, cleanup_files

app = Flask(__name__)

# Check if alignment jobs will be queued or not
if os.environ.get('REDIS_HOST') and os.environ.get('REDIS_PORT'):
    from rq import Queue
    from redis import Redis

    # Fetch redis host and port
    redis_host = os.environ.get('REDIS_HOST')
    redis_port = os.environ.get('REDIS_PORT')

    # Set default timeout for rq alignment jobs
    timeout = os.environ.get('TIMEOUT', 1000)
    # Subscribe to the "subtitles" queue
    q = Queue('subtitles', connection=Redis(host=redis_host, port=redis_port), default_timeout=timeout)
else:
    q = None


@app.route('/align', methods=['POST'])
def login():
    """
    This endpoint attempts both single and dual stage alignment. Jobs are queued or not depending on whether
    a redis host and port were specified.

    Only works for mp4 and mkv formats. Untested on others.
    @return:
    """
    if request.method == 'POST':
        data = json.loads(request.data)
        media_path = data.get('media')
        subtitle_path = data.get('subtitle')

        if (media_path.endswith('.mp4') or media_path.endswith('.mkv')) \
                and subtitle_path is not None \
                and media_path is not None:
            media_posix = Path(media_path)
            subtitle_posix = Path(subtitle_path)
            temp_media_path = str(media_posix.parents[0] / Path('temp' + media_posix.suffix))
            temp_subtitle_path = str(subtitle_posix.parents[0] / Path('temp' + subtitle_posix.suffix))

            sub_format = str(subtitle_posix.suffix)

            single_aligned_path = f"""{subtitle_path.replace(sub_format, ".aligned" + sub_format)}"""
            dual_aligned_path = f"""{subtitle_path.replace(sub_format, ".aligned_dual" + sub_format)}"""

            # Create temp subtitle file
            shutil.copy(subtitle_path, temp_subtitle_path)
            # Call ffprobe to determin audio/video/subtitle track IDs
            data = subprocess.run(['ffprobe', '-loglevel', 'error', '-show_streams', '-of', 'json', media_path],
                                  capture_output=True).stdout
            d = json.loads(data)['streams']
            # Identify audio channel IDs
            audio_inds = [i for i, x in enumerate(d) if x['codec_type'] == 'audio']

            # Identify existing subtitle tracks to be cleaved when embedding newly aligned subtitles
            # It is assumed that existing subtitle tracks are from a previous call of this endpoint.
            # If they exist then the subtitle file must have been upgraded in/by bazarr
            sub_inds = ",".join([str(i) for i, x in enumerate(d) if x['codec_type'] == 'subtitle'])

            # Identify what is presumed to be the only english audio track. (other langs may exist)
            langs = [None] * len(audio_inds)
            channel = '0'
            if len(audio_inds) > 1:
                for ind in audio_inds:
                    tags = d[ind].get('tags')
                    if tags is not None:
                        lang = tags.get('language')
                        if lang is not None:
                            langs[ind] = lang
                for ind, lang in enumerate(langs):
                    if lang == 'eng':
                        channel = str(ind)

            # Define single alignment command
            single = ["subaligner",
                      "-m",
                      "single",
                      "-v",
                      media_path,
                      "-s",
                      temp_subtitle_path,
                      "-c",
                      channel,
                      "-o",
                      single_aligned_path]

            # Define dual alignment command
            dual = ["subaligner",
                    "-m",
                    "dual",
                    "-v",
                    media_path,
                    "-s",
                    temp_subtitle_path,
                    "-c",
                    channel,
                    "-o",
                    dual_aligned_path]

            # If existing subtitle tracks are detected, remove them
            if len(sub_inds) > 0:
                sub = ["mkvmerge",
                       "-o",
                       temp_media_path,
                       "-s",  # The -s option allows us to handle existing subtitles
                       "!" + sub_inds,  # The ! operator lets us specify which to exclude
                       media_path,
                       "--language",
                       "0:eng",
                       "--track-name",
                       "0:Aligned-Single",
                       single_aligned_path,
                       "--language",
                       "0:eng",
                       "--track-name",
                       "0:Aligned-Dual",
                       dual_aligned_path
                       ]
            # Else only add the newly aligned subtitles
            else:
                sub = ["mkvmerge",
                       "-o",
                       temp_media_path,
                       media_path,
                       "--language",
                       "0:eng",
                       "--track-name",
                       "0:Aligned-Single",
                       single_aligned_path,
                       "--language",
                       "0:eng",
                       "--track-name",
                       "0:Aligned-Dual",
                       dual_aligned_path
                       ]
            if q:
                # Chain alignment jobs together
                job1 = q.enqueue(subprocess_call, kwargs={"command": single})
                job2 = q.enqueue(subprocess_call, kwargs={"command": dual}, depends_on=job1, at_front=True)
                # Embed successfully aligned subtitles
                job3 = q.enqueue(sub_call,
                                 kwargs={"command": sub,
                                         "single_path": single_aligned_path,
                                         "dual_path": dual_aligned_path},
                                 depends_on=job2,
                                 at_front=True)

                # Cleanup all temporary files
                q.enqueue(cleanup_files,
                          kwargs={"temp_media_path": temp_media_path,
                                  "media_path": media_path,
                                  "single_aligned_path": single_aligned_path,
                                  "dual_aligned_path": dual_aligned_path,
                                  "temp_subtitle_path": temp_subtitle_path},
                          depends_on=job3,
                          at_front=True)
            else:
                # Keep a list of subtitle embed arguments to remove
                drop_index = []
                try:
                    subprocess_call(single)
                except subprocess.CalledProcessError:
                    # If single stage alignment fails, remove corresponding args in function call
                    drop_index += [-6, -7, -8, -9, -10]
                try:
                    subprocess_call(dual)
                except subprocess.CalledProcessError:
                    # If dual stage alignment fails, remove corresponding args in function call
                    drop_index += [-1, -2, -3, -4, -5]
                # Delete bad args
                for ind in drop_index:
                    del sub[ind]

                # Call the modified subtitle embed command
                try:
                    subprocess_call(sub)
                except subprocess.CalledProcessError:
                    pass
                # Cleanup al temporary files
                cleanup_files(temp_media_path, media_path, single_aligned_path, dual_aligned_path, temp_subtitle_path)

            return 'Success', 200
