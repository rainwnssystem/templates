import argparse
import base64
import io
import json
import logging
import os
import zipfile

import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f'Device: {device}')

MEAN = [0.4302, 0.4575, 0.4538]
STD = [0.2694, 0.2679, 0.2983]


class CNN(nn.Module):
    def __init__(self, num_classes=6):
        super().__init__()
        self.features = nn.Sequential(
            # (channel count, output_features, kernel)
            # e.g. (3, 32, 3)  -> 3 channel(RGB), 32 -> 64 -> ..., 3 kernel
            nn.Conv2d(3, 32, 3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # (prev layer output_features, output_features * 2, kernel)
            # e.g. (32, 64, 3) -> 32 prev output_features, output_features(32)*2=64, 3 kernel 
            nn.Conv2d(32, 64, 3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            nn.Conv2d(128, 256, 3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(256, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        return self.classifier(self.features(x))


def compression(args):
    with zipfile.ZipFile(f'{args.train}/dataset.zip', 'r') as zip_ref:
        zip_ref.extractall(f'{args.train}/')

    logger.info("====== Dataset loaded ======")


def train(args):
    train_transform = transforms.Compose([
        transforms.Resize((150, 150)),
        transforms.RandomCrop(150, padding=20),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD)
    ])

    test_transform = transforms.Compose([
        transforms.Resize((150, 150)),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD)
    ])

    train_dataset = datasets.ImageFolder(root=f'{args.train}/train', transform=train_transform)
    test_dataset  = datasets.ImageFolder(root=f'{args.train}/test',  transform=test_transform)


    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=args.workers)
    test_loader  = DataLoader(test_dataset,  batch_size=args.batch_size, shuffle=False, num_workers=args.workers)

    logger.info("====== Model loaded ======")
    model = CNN().to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    train_losses, test_losses         = [], []
    train_accuracies, test_accuracies = [], []

    best_acc = 0.0
    best_state = None

    for epoch in range(args.epochs):

        # ── Train ──
        model.train()
        running_loss, correct, total = 0, 0, 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total   += labels.size(0)
            correct += (predicted == labels).sum().item()

        train_loss = running_loss / len(train_loader)
        train_acc  = 100 * correct / total

        train_losses.append(train_loss)
        train_accuracies.append(train_acc)

        # ── Test ──
        model.eval()
        correct_test, total_test, test_loss = 0, 0, 0

        with torch.no_grad():
            for images, labels in test_loader:
                images, labels = images.to(device), labels.to(device)

                outputs = model(images)
                loss = criterion(outputs, labels)
                test_loss += loss.item()

                _, predicted = torch.max(outputs, 1)
                total_test   += labels.size(0)
                correct_test += (predicted == labels).sum().item()

        test_loss = test_loss / len(test_loader)
        test_acc  = 100 * correct_test / total_test

        test_losses.append(test_loss)
        test_accuracies.append(test_acc)

        if test_acc > best_acc:
            best_acc = test_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        scheduler.step()

        print(f"Epoch [{epoch+1}/{args.epochs}] "
            f"Train Loss: {train_loss:.4f} | "
            f"Test Loss: {test_loss:.4f} | "
            f"Train Acc: {train_acc:.2f}% | "
            f"Test Acc: {test_acc:.2f}% | "
            f"Best: {best_acc:.2f}%")

    logger.info(f"Finished Training. Best Test Acc: {best_acc:.2f}%")
    if best_state is not None:
        model.load_state_dict(best_state)
    return save_model(model, args.model_dir)


def save_model(model, model_dir):
    logger.info("Saving the model...")

    path = os.path.join(model_dir, "model.pth")
    torch.save(model.cpu().state_dict(), path)


# required for inference

def predict_fn(input_data, model):
    device = next(model.parameters()).device
    input_data = input_data.to(device)
    with torch.inference_mode():
        return model(input_data)


def model_fn(model_dir):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CNN()
    model.load_state_dict(
        torch.load(os.path.join(model_dir, "model.pth"), map_location=device)
    )
    model.to(device)
    model.eval()
    return model


_inference_transform = transforms.Compose([
    transforms.Resize((150, 150)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])


def input_fn(request_body, content_type):
    # base64 + JSON  → Body: {"image": "<base64 string>"}
    if content_type == "application/json":
        data = json.loads(request_body)
        img_bytes = base64.b64decode(data["image"])
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return _inference_transform(image).unsqueeze(0)

    # base64 string (no JSON wrap)  → Body: "<base64 string>"
    if content_type == "text/plain":
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        img_bytes = base64.b64decode(request_body)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return _inference_transform(image).unsqueeze(0)

    # raw bytes  → Body: raw image bytes
    if content_type in ("image/png", "image/jpeg"):
        image = Image.open(io.BytesIO(request_body)).convert("RGB")
        return _inference_transform(image).unsqueeze(0)

    raise ValueError(f"Unsupported content type: {content_type}")


def output_fn(prediction, accept):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")

    probs = torch.softmax(prediction, dim=1)[0]
    top_idx = int(torch.argmax(probs).item())
    body = {
        "class_idx": top_idx,
        "confidence": float(probs[top_idx].item()),
        # "probs": probs.cpu().tolist(),
    }
    return json.dumps(body), accept


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
    parser.add_argument("--hosts", type=json.loads, default=os.environ["SM_HOSTS"])
    parser.add_argument("--train", type=str, default=os.environ["SM_CHANNEL_TRAIN"])
    parser.add_argument("--model-dir", type=str, default=os.environ["SM_MODEL_DIR"])

    compression(parser.parse_args())
    train(parser.parse_args())