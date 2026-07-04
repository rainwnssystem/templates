import argparse
import base64
import io
import json
import logging
import os
import zipfile

import torch
import torch.distributed as dist
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler
from torchvision import datasets, transforms

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

MEAN = [0.4302, 0.4575, 0.4538]
STD = [0.2694, 0.2679, 0.2983]


class CNN(nn.Module):
    def __init__(self, num_classes=6):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

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


def train(args):
    # ── [DDP 1] 프로세스 그룹 초기화 ──────────────────────────────
    # torchrun이 GPU 하나당 이 스크립트를 1개씩 실행하고,
    # RANK / LOCAL_RANK / WORLD_SIZE 환경변수를 넣어준다.
    dist.init_process_group(backend="nccl" if torch.cuda.is_available() else "gloo")
    rank       = dist.get_rank()                     # 전체에서 내 번호 (0, 1, 2, ...)
    local_rank = int(os.environ["LOCAL_RANK"])       # 이 서버 안에서 내 GPU 번호
    device     = torch.device(f"cuda:{local_rank}" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        torch.cuda.set_device(local_rank)

    # ── [DDP 2] 압축 해제는 대표(rank 0) 한 명만 ─────────────────
    if local_rank == 0:
        with zipfile.ZipFile(f'{args.train}/dataset.zip', 'r') as zip_ref:
            zip_ref.extractall(f'{args.train}/')
    dist.barrier()  # 나머지는 끝날 때까지 대기

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

    # ── [DDP 3] 데이터를 GPU 수만큼 나눠 갖는 sampler ────────────
    # GPU가 4개면 각 프로세스는 데이터의 1/4씩만 학습한다.
    train_sampler = DistributedSampler(train_dataset)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size,
                              sampler=train_sampler, num_workers=args.workers)
    test_loader  = DataLoader(test_dataset, batch_size=args.batch_size,
                              shuffle=False, num_workers=args.workers)

    # ── [DDP 4] 모델을 DDP로 감싸기 ──────────────────────────────
    # 이후 loss.backward()마다 gradient가 GPU들끼리 자동으로 평균된다.
    model = CNN().to(device)
    model = DDP(model, device_ids=[local_rank] if torch.cuda.is_available() else None)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_acc = 0.0
    best_state = None

    for epoch in range(args.epochs):
        # ── [DDP 5] 에폭마다 셔플을 새로 섞어주기 (잊기 쉬움!) ──
        train_sampler.set_epoch(epoch)

        # ── Train ──
        model.train()
        running_loss, correct, total = 0, 0, 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()   # <- 여기서 DDP가 알아서 GPU 간 gradient 동기화
            optimizer.step()

            running_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total   += labels.size(0)
            correct += (predicted == labels).sum().item()

        train_loss = running_loss / len(train_loader)
        train_acc  = 100 * correct / total

        # ── Test (전체 test셋을 각자 평가; 모델이 동일하므로 결과도 동일) ──
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

        if test_acc > best_acc:
            best_acc = test_acc
            # DDP 래퍼 안의 원본 모델은 model.module
            best_state = {k: v.detach().cpu().clone() for k, v in model.module.state_dict().items()}

        scheduler.step()

        # ── [DDP 6] 출력/저장은 대표(rank 0)만 ─────────────────────
        if rank == 0:
            print(f"Epoch [{epoch+1}/{args.epochs}] "
                f"Train Loss: {train_loss:.4f} | "
                f"Test Loss: {test_loss:.4f} | "
                f"Train Acc: {train_acc:.2f}% | "
                f"Test Acc: {test_acc:.2f}% | "
                f"Best: {best_acc:.2f}%")

    if rank == 0:
        logger.info(f"Finished Training. Best Test Acc: {best_acc:.2f}%")
        save_model(best_state, args.model_dir)

    dist.barrier()               # 저장이 끝날 때까지 전원 대기
    dist.destroy_process_group() # 뒷정리


def save_model(state_dict, model_dir):
    path = os.path.join(model_dir, "model.pth")
    torch.save(state_dict, path)


# required for inference (서빙은 GPU 1개로 하므로 기존과 완전히 동일)

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
    if content_type == "application/json":
        data = json.loads(request_body)
        img_bytes = base64.b64decode(data["image"])
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return _inference_transform(image).unsqueeze(0)

    if content_type == "text/plain":
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        img_bytes = base64.b64decode(request_body)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return _inference_transform(image).unsqueeze(0)

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
    }
    return json.dumps(body), accept


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--workers", type=int, default=2, metavar="W")
    parser.add_argument("--epochs", type=int, default=20, metavar="E")
    parser.add_argument("--batch_size", type=int, default=64, metavar="BS")
    parser.add_argument("--lr", type=float, default=0.001, metavar="LR")
    parser.add_argument("--train", type=str, default=os.environ["SM_CHANNEL_TRAIN"])
    parser.add_argument("--model-dir", type=str, default=os.environ["SM_MODEL_DIR"])

    train(parser.parse_args())
