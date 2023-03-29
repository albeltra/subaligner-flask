from flask import Flask

app = Flask(__name__)

@app.route('/align', methods=['POST'])
def login():
    if request.method == 'POST':
        data = json.loads(request.data)
        print(data)
