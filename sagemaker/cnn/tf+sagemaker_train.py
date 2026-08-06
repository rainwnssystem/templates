import argparse
import base64
import io
import json
import logging
import os
import zipfile

import numpy as np
import tensorflow as tf
from PIL import Image
from tensorflow import keras
from tensorflow.keras import layers

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

device = "/GPU:0" if tf.config.list_physical_devices("GPU") else "/CPU:0"
logger.info(f"Device: {device}")


MEAN = tf.constant([0.4913, 0.4821, 0.4465])
STD = tf.constant([0.2470, 0.2434, 0.2615])


def compression(args):
    with zipfile.ZipFile(f'{args.train}/dataset.zip', 'r') as zip_ref:
        zip_ref.extractall(f'{args.train}/')
    print('============= Files =============', os.listdir(f'{args.train}/'))

    logger.info("====== Dataset loaded ======")


def _train_transform(image, label):
    image = tf.cast(image, tf.float32) / 255.0
    image = tf.image.resize_with_crop_or_pad(image, 32 + 8, 32 + 8)
    image = tf.image.random_crop(image, [32, 32, 3])
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_brightness(image, 0.2)
    image = tf.image.random_contrast(image, 0.8, 1.2)
    image = (image - MEAN) / STD
    return image, label


def _test_transform(image, label):
    image = tf.cast(image, tf.float32) / 255.0
    image = (image - MEAN) / STD
    return image, label


def train(args):
    train_dataset = keras.utils.image_dataset_from_directory(
        f'{args.train}/train',
        image_size=(32, 32),
        batch_size=args.batch_size,
        shuffle=True,
    )
    test_dataset = keras.utils.image_dataset_from_directory(
        f'{args.train}/test',
        image_size=(32, 32),
        batch_size=args.batch_size,
        shuffle=False,
    )

    steps_per_epoch = tf.data.experimental.cardinality(train_dataset).numpy()

    train_dataset = (train_dataset
        .unbatch()
        .map(_train_transform, num_parallel_calls=tf.data.AUTOTUNE)
        .batch(args.batch_size)
        .prefetch(tf.data.AUTOTUNE))
    test_dataset  = test_dataset.map(_test_transform, num_parallel_calls=tf.data.AUTOTUNE).prefetch(tf.data.AUTOTUNE)

    logger.info("====== Model loaded ======")
    model = keras.Sequential([
        layers.Input(shape=(32, 32, 3)),

        layers.Conv2D(32, 3, padding="same", use_bias=False),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(2),

        layers.Conv2D(64, 3, padding="same", use_bias=False),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(2),

        layers.Conv2D(128, 3, padding="same", use_bias=False),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(2),

        layers.Conv2D(256, 3, padding="same", use_bias=False),
        layers.BatchNormalization(),
        layers.ReLU(),
        layers.MaxPooling2D(2),

        layers.GlobalAveragePooling2D(),
        layers.Dense(256),
        layers.ReLU(),
        layers.Dropout(0.3),
        layers.Dense(num_classes),
    ])

    schedule  = keras.optimizers.schedules.CosineDecay(args.lr, decay_steps=steps_per_epoch * args.epochs)
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
    image = image.resize((32, 32))
    arr = np.array(image, dtype=np.float32) / 255.0
    arr = (arr - MEAN.numpy()) / STD.numpy()
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

    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
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
