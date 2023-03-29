from flask import Flask, request
import requests
import json
import subprocess

app = Flask(__name__)

@app.route('/align', methods=['POST'])
def login():
    if request.method == 'POST':
        data = json.loads(request.data)
        media = data.get('media')
        subtitle = data.get('subtitle')

        
        
