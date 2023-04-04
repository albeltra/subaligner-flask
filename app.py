import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Flask, request

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


def subprocess_call(command):
    import subprocess
    subprocess.run(command, check=True)
    # result = subprocess.run(command, stdout=subprocess.PIPE)
    # output = result.stdout.decode('utf-8')
    # return output


def sub_call(command, single_path, dual_path):
    drop_index = []
    if not os.path.exists(single_path):
        drop_index += [-6, -7, -8, -9, -10]
    if not os.path.exists(dual_path):
        drop_index += [-1, -2, -3, -4, -5]
    for ind in drop_index:
        del command[ind]
    subprocess_call(command)

@app.route('/align', methods=['POST'])
def login():
    if request.method == 'POST':
        data = json.loads(request.data)
        media = data.get('media')
        subtitle = data.get('subtitle')
        media_posix = Path(media)

        temp_path = media_posix.parents[0] / Path('temp' + media_posix.suffix)
        media_path = f"{media}"
        if media_path.endswith('.mp4') or media_path.endswith('.mkv'):
            subtitle_path = f"{subtitle}"
            single_aligned_path = f"""{subtitle.replace(".en.srt", ".en.aligned.srt")}"""
            dual_aligned_path = f"""{subtitle.replace(".en.srt", ".en.aligned_dual.srt")}"""

            temp_subtitle_path = subtitle_path.replace(".en.srt", ".srt")

            shutil.copy(subtitle_path, temp_subtitle_path)
            data = subprocess.run(['ffprobe', '-loglevel', 'error', '-show_streams', '-of', 'json', media_path],
                                  capture_output=True).stdout
            d = json.loads(data)['streams']
            inds = [i for i, x in enumerate(d) if x['codec_type'] == 'audio']
            sub_inds = ",".join([str(i) for i, x in enumerate(d) if x['codec_type'] == 'subtitle'])
            langs = [None] * len(inds)
            channel = '0'
            if len(inds) > 1:
                for ind in inds:
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
                       temp_path,
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
                       temp_path,
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
                q.enqueue(sub_call,
                          kwargs={"command": sub,
                                  "single_path": single_aligned_path,
                                  "dual_path": dual_aligned_path},
                          depends_on=job2)
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
                subprocess_call(sub)

            try:
                shutil.move(temp_path, media_path)
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
            return 'Success', 200
