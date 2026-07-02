from flask import Flask

app = Flask(__name__)

@app.route('/product', methods=['GET'])
def product():
    return 'hello, product!', 200

@app.route('/healthz', methods=['GET'])
def healthz():
    return 'ok', 200

if __name__ == '__main__':
    app.run()
