import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Flask, request

app = Flask(__name__)


@app.route('/align', methods=['POST'])
def login():
    if request.method == 'POST':
        data = json.loads(request.data)
        media = data.get('media')
        subtitle = data.get('subtitle')
        media_posix = Path(media)

        temp_path = media_posix.parents[0] / Path('temp' + media_posix.suffix)
        media_path = f"{media}"
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

        if subprocess.run(["subaligner",
                           "-m",
                           "single",
                           "-v",
                           media_path,
                           "-s",
                           temp_subtitle_path,
                           "-c",
                           channel,
                           "-o",
                           single_aligned_path]):

            if subprocess.run(["subaligner",
                               "-m",
                               "dual",
                               "-v",
                               media_path,
                               "-s",
                               temp_subtitle_path,
                               "-c",
                               channel,
                               "-o",
                               dual_aligned_path]):

                if len(sub_inds) > 0:
                    subprocess.run(["mkvmerge",
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
                                    ])
                else: 
                    subprocess.run(["mkvmerge",
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
                                    ])
                shutil.move(temp_path, media_path)
                os.remove(single_aligned_path)
                os.remove(dual_aligned_path)
                os.remove(temp_subtitle_path)

        return 'Success', 200
