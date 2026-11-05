"""Fine-tuning do TrOCR."""
import argparse
import shutil
from datetime import datetime

import torch
from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments, TrOCRProcessor,
                          VisionEncoderDecoderModel, default_data_collator)

from .. import config
from .dataset import WordDataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--from-base", action="store_true", help="ignora o modelo atual e parte do pre-treinado")
    a = ap.parse_args()

    train_csv, val_csv = config.DATASETS_DIR / "train.csv", config.DATASETS_DIR / "val.csv"
    if not train_csv.exists():
        raise SystemExit("Rode antes: python -m recognition.htr.training.prepare_dataset")

    if (config.CURRENT_MODEL / "config.json").exists() and not a.from_base:
        src, kw = str(config.CURRENT_MODEL), {}
        print("Continuando do modelo atual:", src)
    else:
        src, kw = config.BASE_MODEL, {"cache_dir": str(config.BASE_CACHE)}
        print("Partindo do modelo base:", src)
    processor = TrOCRProcessor.from_pretrained(src, **kw)
    model = VisionEncoderDecoderModel.from_pretrained(src, **kw)

    tok = processor.tokenizer
    for cfg in (model.config, model.generation_config):
        cfg.decoder_start_token_id = tok.cls_token_id
        cfg.pad_token_id = tok.pad_token_id
        cfg.eos_token_id = tok.sep_token_id
    model.config.vocab_size = model.config.decoder.vocab_size

    train_ds = WordDataset(train_csv, processor, train=True)
    val_ds = WordDataset(val_csv, processor) if val_csv.exists() else None
    if len(train_ds) < 2:
        raise SystemExit("Poucos exemplos para treinar.")
    has_val = val_ds is not None and len(val_ds) > 0

    run_dir = config.FINETUNED_DIR / f"run-{datetime.now():%Y%m%d-%H%M}"
    args = Seq2SeqTrainingArguments(
        output_dir=str(run_dir),
        per_device_train_batch_size=a.batch_size, per_device_eval_batch_size=a.batch_size,
        num_train_epochs=a.epochs, learning_rate=a.lr, weight_decay=0.01,
        eval_strategy="epoch" if has_val else "no",
        save_strategy="epoch" if has_val else "no",
        save_total_limit=2, load_best_model_at_end=has_val,
        metric_for_best_model="eval_loss", greater_is_better=False,
        fp16=torch.cuda.is_available(), remove_unused_columns=False,
        logging_steps=20, report_to="none",
    )
    trainer = Seq2SeqTrainer(model=model, args=args, train_dataset=train_ds,
                             eval_dataset=val_ds if has_val else None,
                             data_collator=default_data_collator)
    trainer.train()

    final = run_dir / "final"
    model.save_pretrained(final); processor.save_pretrained(final)
    shutil.copytree(final, config.CURRENT_MODEL, dirs_exist_ok=True)
    print(f"Modelo salvo em {final} e copiado para {config.CURRENT_MODEL}")
    print("Reinicie o servidor para usar o novo modelo.")


if __name__ == "__main__":
    main()
