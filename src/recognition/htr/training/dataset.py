import csv

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

from .. import config


class WordDataset(Dataset):
    def __init__(self, csv_path, processor, train: bool = False):
        with open(csv_path, newline="", encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        self.processor, self.train = processor, train
        self.aug = T.Compose([
            T.RandomAffine(degrees=3, translate=(0.02, 0.05), scale=(0.9, 1.05), shear=(-8, 8), fill=255),
            T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
        ])

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(config.CROPS_DIR / r["crop_file"]).convert("RGB")
        if self.train:
            img = self.aug(img)
        pv = self.processor(images=img, return_tensors="pt").pixel_values.squeeze(0)
        tok = self.processor.tokenizer
        ids = tok(r["text"], padding="max_length", max_length=config.MAX_LABEL_LEN, truncation=True).input_ids
        return {"pixel_values": pv,
                "labels": torch.tensor([t if t != tok.pad_token_id else -100 for t in ids])}
