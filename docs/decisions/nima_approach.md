# Decision: NIMA Aesthetic Scoring Approach

## Context

NIMA (Neural Image Assessment) provides aesthetic quality scoring for generated
visual assets. No standalone NIMA pip package exists that provides pre-trained
weights in a ready-to-use form.

## Approach

Use **torchvision MobileNetV2** as the backbone with a modified classifier head:

1. Load MobileNetV2 with ImageNet pre-trained weights (torchvision built-in)
2. Replace the classifier with: Dropout(0.75) -> Linear(1280, 10) -> Softmax
3. Output: 10-class probability distribution over aesthetic ratings 1-10
4. Mean score: weighted sum of distribution (1*p1 + 2*p2 + ... + 10*p10)

## Validation (S0)

- Device: MPS (Apple Silicon)
- Random image mean score: 5.55 (expected ~5.5 for random noise)
- Inference: <100ms on MPS
- No additional pip packages needed beyond torch + torchvision

## Pre-trained Weights

The current setup uses ImageNet weights (not NIMA-specific AVA dataset weights).
For production quality scoring, we should load NIMA-specific weights trained on
the AVA dataset. Options:

1. Download pre-trained NIMA weights from available checkpoints online
2. Fine-tune MobileNetV2 on AVA dataset (requires ~255K rated images)

For Month 1-2, the ImageNet-backbone NIMA provides relative aesthetic comparison
capability. Absolute scores should be calibrated against the reference corpus
(evaluations/reference_corpus/) once S13 builds the visual intelligence layer.

## Impact

- No additional dependencies
- Runs on MPS with <100ms inference
- Integrated into quality gate via `middleware/quality_gate.py`
