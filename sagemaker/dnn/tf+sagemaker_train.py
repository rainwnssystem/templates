import argparse
import base64
import io
import json
import logging
import os
import zipfile
import struct

import numpy as np
import tensorflow as tf
from PIL import Image
from tensorflow import keras

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

device = "/GPU:0" if tf.config.list_physical_devices("GPU") else "/CPU:0"
logger.info(f"Device: {device}")


class CustomDataset:
    def __init__(self, images, labels=None, transform=None):
        self.images    = images
        self.labels    = labels
        self.transform = transform

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img = self.images[idx]

        if self.transform:
            img = self.transform(img)

        if self.labels is not None:
            return img, int(self.labels[idx])

        return img


def compression(args):
    with zipfile.ZipFile(f'{args.train}/dataset.zip', 'r') as zip_ref:
        zip_ref.extractall(f'{args.train}/')
    print('============= Files =============', os.listdir(f'{args.train}/'))

    logger.info("====== Dataset loaded ======")


def train(args):
    with open(f'{args.train}/train-images.idx3-ubyte', 'rb') as f:
        _, n, rows, cols = struct.unpack('>IIII', f.read(16))
        train_images = np.fromfile(f, dtype=np.uint8).reshape(n, rows, cols, 1)

    with open(f'{args.train}/train-labels.idx1-ubyte', 'rb') as f:
        struct.unpack('>II', f.read(8))
        train_labels = np.fromfile(f, dtype=np.uint8)

    with open(f'{args.train}/t10k-images.idx3-ubyte', 'rb') as f:
        _, n, rows, cols = struct.unpack('>IIII', f.read(16))
        test_images = np.fromfile(f, dtype=np.uint8).reshape(n, rows, cols, 1)

    with open(f'{args.train}/t10k-labels.idx1-ubyte', 'rb') as f:
        struct.unpack('>II', f.read(8))
        test_labels = np.fromfile(f, dtype=np.uint8)

    train_images = train_images.astype(np.float32) / 255.0
    test_images  = test_images.astype(np.float32)  / 255.0

    train_dataset = tf.data.Dataset.from_tensor_slices((train_images, train_labels))
    test_dataset  = tf.data.Dataset.from_tensor_slices((test_images, test_labels))

    train_dataset = train_dataset.shuffle(1000).batch(args.batch_size).prefetch(tf.data.AUTOTUNE)
    test_dataset  = test_dataset.batch(args.batch_size).prefetch(tf.data.AUTOTUNE)

    print("====== Model loaded ======")

    model = keras.Sequential([

        keras.layers.Flatten(input_shape=(28, 28, 1)),  # (( w * h * 1(or 3) ))

        keras.layers.Dense(512, activation='relu'),
        keras.layers.Dropout(0.3),

        keras.layers.Dense(256, activation='relu'),
        keras.layers.Dropout(0.3),

        keras.layers.Dense(128, activation='relu'),
        keras.layers.Dropout(0.3),

        keras.layers.Dense(10, activation='softmax')  # multi: softmax | binary: sigmoid
    ])

    steps_per_epoch = tf.data.experimental.cardinality(train_dataset).numpy()

    schedule = keras.optimizers.schedules.CosineDecay(args.lr, decay_steps=steps_per_epoch * args.epochs)
    optimizer = keras.optimizers.Adam(learning_rate=schedule)

    model.compile(
        optimizer=optimizer,
        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )

    path = '/opt/ml/model'
    best_path = os.path.join(path, "best.weights.h5")
    best_ckpt = keras.callbacks.ModelCheckpoint(
        filepath=best_path,
        save_weights_only=True,
        save_best_only=True,
        monitor="val_accuracy",
        mode="max",
    )

    history = model.fit(
        train_dataset,
        validation_data=test_dataset,
        epochs=args.epochs,
        callbacks=[best_ckpt],
        verbose=2
    )

    best_acc = max(history.history["val_accuracy"]) * 100
    logger.info(f"Finished Training. Best Test Acc: {best_acc:.2f}%")
    if os.path.exists(best_path):
        model.load_weights(best_path)
        os.remove(best_path)
    return save_model(model, args.model_dir)


def save_model(model, model_dir):
    logger.info("Saving the model...")

    path = "/opt/ml/model"
    model.export(os.path.join(path, "0001"))


def _inference_transform(image):
    image = image.resize((28, 28))
    arr = np.array(image, dtype=np.float32) / 255.0
    return arr.astype(np.float32).tolist()


def input_handler(data, context):
    request_body  = data.read()
    content_type  = context.request_content_type or "application/json"

    # base64 + JSON  → Body: {"image": "<base64 string>"}
    if content_type == "application/json":
        body = json.loads(request_body)
        img_bytes = base64.b64decode(body["image"])

    # base64 string (no JSON wrap)  → Body: "<base64 string>"
    elif content_type == "text/plain":
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        img_bytes = base64.b64decode(request_body)

    # raw bytes  → Body: raw image bytes
    elif content_type in ("image/png", "image/jpeg"):
        img_bytes = request_body

    else:
        raise ValueError(f"Unsupported content type: {content_type}")

    image = Image.open(io.BytesIO(img_bytes)).convert("L")  # L==grayscale | RGB
    return json.dumps({"instances": [_inference_transform(image)]})


def output_handler(response, context):
    if response.status_code != 200:
        raise ValueError(response.content.decode("utf-8"))

    preds   = np.array(json.loads(response.content)["predictions"][0])
    probs   = tf.nn.softmax(preds).numpy()
    top_idx = int(np.argmax(probs))
    body = {
        "class_idx": top_idx,
        "confidence": float(probs[top_idx]),
        # "probs": probs.tolist(),
    }
    return json.dumps(body), "application/json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        metavar="W"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
        metavar="E"
    )
    parser.add_argument(
        "--batch_size", type=int, default=64, metavar="BS"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.001,
        metavar="LR"
    )
    parser.add_argument("--model_dir", type=str)
    parser.add_argument("--hosts", type=json.loads, default=os.environ["SM_HOSTS"])
    parser.add_argument("--momentum", type=float, default=0.9, metavar="M")
    parser.add_argument("--train", type=str, default=os.environ["SM_CHANNEL_TRAIN"])

    compression(parser.parse_args())
    train(parser.parse_args())