import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Flask, request

from utils import subprocess_call, sub_call, cleanup_files

app = Flask(__name__)

timeout = os.environ.get('TIMEOUT', 1000)

if os.environ.get('REDIS_HOST') and os.environ.get('REDIS_PORT'):
    from rq import Queue
    from redis import Redis

    redis_host = os.environ.get('REDIS_HOST')
    redis_port = os.environ.get('REDIS_PORT')
    q = Queue('subtitles', connection=Redis(host=redis_host, port=redis_port), default_timeout=timeout)
else:
    q = None


@app.route('/align', methods=['POST'])
def login():
    if request.method == 'POST':
        data = json.loads(request.data)
        media_path = data.get('media')
        subtitle_path = data.get('subtitle')
        lang = data.get('language')

        if (media_path.endswith('.mp4') or media_path.endswith('.mkv')) \
                and subtitle_path is not None \
                and media_path is not None:
            media_posix = Path(media_path)
            subtitle_posix = Path(subtitle_path)
            temp_media_path = media_posix.parents[0] / Path('temp' + media_posix.suffix)
            temp_subtitle_path = subtitle_posix.parents[0] / Path('temp' + subtitle_posix.suffix)

            lang = "." + lang.split(".")[0] if lang is not None else "." + "en"
            sub_format = str(subtitle_posix.suffix)

            single_aligned_path = f"""{subtitle_path.replace(lang + sub_format, lang + ".aligned" + sub_format)}"""
            dual_aligned_path = f"""{subtitle_path.replace(lang + sub_format, lang + ".aligned_dual" + sub_format)}"""

            shutil.copy(subtitle_path, temp_subtitle_path)
            data = subprocess.run(['ffprobe', '-loglevel', 'error', '-show_streams', '-of', 'json', media_path],
                                  capture_output=True).stdout
            d = json.loads(data)['streams']
            audio_inds = [i for i, x in enumerate(d) if x['codec_type'] == 'audio']
            sub_inds = ",".join([str(i) for i, x in enumerate(d) if x['codec_type'] == 'subtitle'])

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

            if len(sub_inds) > 0:
                sub = ["mkvmerge",
                       "-o",
                       temp_media_path,
                       "-s",
                       "!" + sub_inds,
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
                job1 = q.enqueue(subprocess_call, kwargs={"command": single})
                job2 = q.enqueue(subprocess_call, kwargs={"command": dual}, depends_on=job1)
                job3 = q.enqueue(sub_call,
                                 kwargs={"command": sub,
                                         "single_path": single_aligned_path,
                                         "dual_path": dual_aligned_path},
                                 depends_on=job2)

                q.enqueue(cleanup_files,
                          kwargs={"temp_media_path": temp_media_path,
                                  "media_path": media_path,
                                  "single_aligned_path": single_aligned_path,
                                  "dual_aligned_path": dual_aligned_path,
                                  "temp_subtitle_path": temp_subtitle_path},
                          depends_on=job3)
            else:
                drop_index = []
                try:
                    subprocess_call(single)
                except subprocess.CalledProcessError:
                    drop_index += [-6, -7, -8, -9, -10]
                try:
                    subprocess_call(dual)
                except subprocess.CalledProcessError:
                    drop_index += [-1, -2, -3, -4, -5]

                for ind in drop_index:
                    del sub[ind]

                try:
                    subprocess_call(sub)
                except subprocess.CalledProcessError:
                    pass

                cleanup_files(temp_media_path, media_path, single_aligned_path, dual_aligned_path, temp_subtitle_path)

            return 'Success', 200
