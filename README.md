# Project: DocStruct Engine (Adobe Hackathon - Round 1A)

**Participant:** [Your Name / Team Name]

## Overview

The DocStruct Engine is a robust, offline-first solution designed to meet the "Understand Your Document" challenge. It parses a wide variety of PDF files—from structured reports and RFPs to forms and flyers—and intelligently extracts their hierarchical structure (Title, H1, H2, H3).

## Our Approach: Feature-Based Heuristics

Our solution moves beyond simple font-size checks, which are notoriously brittle. Instead, we employ a multi-stage pipeline based on sophisticated feature engineering and heuristic scoring.

1.  **Document Pre-processing:** The engine first performs a full-document analysis to identify and filter out repeating elements like headers and footers. It also cleans text artifacts from tables of contents.

2.  **Feature-Based Scoring:** Every line of text is scored based on a weighted combination of positive and negative signals:
    *   **Positive Signals:** High scores are given for large font sizes (relative to the document's body text), bold weighting, and strong structural markers like numbering (`1.1`, `Appendix A`).
    *   **Negative Signals:** The score is heavily penalized or zeroed out for patterns that indicate non-heading text, such as lines ending in a period, bullet points, or extremely long sentences. This allows the engine to effectively ignore body paragraphs and reject non-standard documents like forms.

3.  **Hierarchical Grouping:** Instead of relying on complex clustering, we use a more stable method. We group potential headings by their style (font size and name) and rank these styles to determine the hierarchy (H1, H2, H3). This correctly maps the visual structure of the document to a logical one.

4.  **Logical Sorting:** The final extracted outline is critically sorted by page number and then by vertical position on the page, ensuring the output matches the natural reading order of the document.

This approach makes our engine resilient to diverse layouts and capable of discerning true structure from visual noise.

## Tech Stack

- **Language:** Python 3.9
- **Core Library:** `PyMuPDF` for high-performance, accurate PDF parsing.

## How to Build and Run

The entire solution is containerized using Docker for seamless and reproducible execution.

### 1. Build the Docker Image

From the root directory of this project, run the following command:

```bash
docker build --platform linux/amd64 -t adobe-hackathon-1a .
```

### 2. Run the docker container

```bash
docker run --rm \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/output:/app/output \
  --network none \
  adobe-hackathon-1a
```