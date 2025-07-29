import fitz  # PyMuPDF
import json
import os
import re
from collections import Counter, defaultdict

# --- Utility Functions ---

def clean_text(text):
    """Cleans text by removing excessive whitespace and common TOC artifacts."""
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove page number artifacts like '........... 12'
    text = re.sub(r'\s*\.{3,}\s*\d+\s*$', '', text)
    return text

def is_likely_footer_or_header(line, page, all_lines_by_page):
    """
    Heuristic to detect if a line is a repeating header or footer.
    Checks if similar text appears in a similar vertical position on other pages.
    """
    y_pos = line['bbox'].y0
    text = line['text']
    
    # Headers are at the top, footers at the bottom of a page
    page_height = page.rect.height
    if y_pos < page_height * 0.1 or y_pos > page_height * 0.9:
        # Check for repetition across other pages
        match_count = 0
        for p_num, p_lines in all_lines_by_page.items():
            if p_num == page.number:
                continue
            for other_line in p_lines:
                # If text is similar and y-position is close, it's a repeater
                if text == other_line['text'] and abs(y_pos - other_line['bbox'].y0) < 10:
                    match_count += 1
                    break # Move to next page
        # If it appears on at least one other page, it's likely a header/footer
        if match_count > 0:
            return True
    return False

# --- Stage 1: Logical Line and Document Structure Extraction ---

def get_document_lines_and_features(pdf_path):
    """
    Extracts all lines from a PDF, detects headers/footers, and pre-computes
    document-wide features like body text style.
    """
    doc = fitz.open(pdf_path)
    all_lines = []
    raw_lines_by_page = defaultdict(list)
    
    # First pass: Extract raw lines and group by page
    for page_num, page in enumerate(doc):
        page_dict = page.get_text("dict", sort=True)
        for block in page_dict.get("blocks", []):
            if block['type'] == 0:  # Text block
                for line in block.get("lines", []):
                    line_text = " ".join(span['text'] for span in line['spans'])
                    if not line_text.strip():
                        continue
                    
                    styles = [(round(span['size']), span['font']) for span in line['spans']]
                    if not styles: continue
                    dominant_style = Counter(styles).most_common(1)[0][0]
                    
                    raw_lines_by_page[page_num].append({
                        "text": line_text, "style": dominant_style,
                        "page_num": page_num, "bbox": fitz.Rect(line['bbox'])
                    })

    # Second pass: Clean, filter headers/footers, and create final line list
    for page_num, page in enumerate(doc):
        lines_on_page = raw_lines_by_page[page_num]
        for line_data in lines_on_page:
            if not is_likely_footer_or_header(line_data, page, raw_lines_by_page):
                line_data['text'] = clean_text(line_data['text'])
                if line_data['text']:
                    all_lines.append(line_data)

    # Determine document-wide features
    doc_features = {
        'body_size': 10.0,
        'body_font': 'default'
    }
    # A more robust way to find body text: not all caps, has several words.
    body_styles = [
        l['style'] for l in all_lines 
        if 5 < len(l['text'].split()) < 20 and not l['text'].isupper()
    ]
    if body_styles:
        doc_features['body_size'], doc_features['body_font'] = Counter(body_styles).most_common(1)[0][0]

    return all_lines, doc_features


# --- Stage 2: Feature-Based Scoring and Hierarchy Analysis ---

def analyze_document_structure(lines, doc_features):
    """
    Analyzes all lines to find the title and build a hierarchical outline
    using a more robust, feature-based scoring model.
    """
    if not lines:
        return "", []

    # --- Score every line as a potential heading ---
    scored_lines = []
    for i, line in enumerate(lines):
        score, is_title_candidate = score_line_as_heading(line, doc_features, lines, i)
        if score > 3.0:  # Increased threshold to be more selective
            scored_lines.append({'line': line, 'score': score, 'is_title_candidate': is_title_candidate})

    if not scored_lines:
        return find_fallback_title(lines), []

    # --- Identify the Title ---
    # The best title candidate is one with a high score that is marked as a title candidate
    title_candidates = [sl for sl in scored_lines if sl['is_title_candidate']]
    if not title_candidates:
        # If no explicit title candidates, use the highest scored item on the first page
        title_candidates = [sl for sl in scored_lines if sl['line']['page_num'] == 0]

    if title_candidates:
        title_sl = max(title_candidates, key=lambda x: x['score'])
        title_text = title_sl['line']['text']
        # Remove the identified title from the list of outline candidates
        outline_candidates = [sl for sl in scored_lines if sl['line'] != title_sl['line']]
    else: # Fallback if no suitable candidates found
        title_text = find_fallback_title(lines)
        outline_candidates = scored_lines

    if not outline_candidates:
        return title_text, []
        
    # --- Assign Hierarchy Levels (H1, H2, H3) ---
    # We group candidates by their style (font size and name) and rank these styles.
    # This is more stable than clustering on a single score value.
    style_groups = defaultdict(list)
    for sl in outline_candidates:
        style_groups[sl['line']['style']].append(sl)

    # Rank styles by size, then boldness. This defines the hierarchy.
    # e.g., (16, 'Bold') > (14, 'Bold') > (14, 'Normal')
    sorted_styles = sorted(style_groups.keys(), key=lambda s: (s[0], 'bold' in s[1].lower()), reverse=True)
    
    level_map = {style: f"H{i+1}" for i, style in enumerate(sorted_styles[:3])}

    outline = []
    for sl in outline_candidates:
        style = sl['line']['style']
        if style in level_map:
            outline.append({
                "level": level_map[style],
                "text": sl['line']['text'],
                "page": sl['line']['page_num'] + 1,
                # Store position for final sorting
                "y_pos": sl['line']['bbox'].y0
            })
            
    # --- Final Sort and Logical Refinement ---
    # Sort by page, then by vertical position on the page. THIS IS CRITICAL.
    outline.sort(key=lambda x: (x['page'], x['y_pos']))
    
    # Remove the temporary y_pos key before final output
    for item in outline:
        del item['y_pos']
        
    # Optional but good: Post-process to enforce hierarchy (e.g., no H3 without an H2)
    # This can be complex, so we'll leave it out for this submission to keep it robust,
    # as the style-based grouping already provides good logical structure.
    
    return title_text, outline

def find_fallback_title(lines):
    """If scoring fails, find the most prominent text on the first page."""
    first_page_lines = [l for l in lines if l['page_num'] == 0]
    if not first_page_lines: return "Untitled Document"
    # The title is likely the line with the largest font on the first page.
    return max(first_page_lines, key=lambda l: l['style'][0])['text']

def score_line_as_heading(line, features, all_lines, index):
    """
    A much more robust scoring function with heavy penalties for non-heading patterns.
    Returns (score, is_title_candidate_flag).
    """
    text, style, bbox = line['text'], line['style'], line['bbox']
    size, font = style
    
    # --- Initial Feature Checks (Strong Rejections) ---
    words = text.split()
    word_count = len(words)
    if word_count > 15: return 0.0, False # Too long for a heading
    if word_count == 0: return 0.0, False
    if text.endswith('.') and word_count > 3: return 0.0, False # It's a full sentence
    if re.match(r'^[•-]', text): return 0.0, False # It's a bullet point
    if not any(char.isalpha() for char in text): return 0.0, False # No letters (e.g., '---')
    if word_count == 1 and len(text) > 25: return 0.0, False # Likely a URL or garbage
    
    score = 0.0
    is_title_candidate = False

    # --- Positive Scoring ---
    # 1. Font Size relative to body text is a strong signal
    if size > features['body_size'] + 1:
        score += (size - features['body_size']) * 2.0

    # 2. Font Weight
    if 'bold' in font.lower():
        score += 4.0

    # 3. All Caps (less important than size/weight)
    if text.isupper() and word_count > 1:
        score += 1.5

    # 4. Numbering (VERY strong signal for outline headings)
    if re.match(r'^((\d{1,2}(\.\d{1,2})*)|(Appendix|Chapter)\s+[A-Z0-9\s:]|([IVXLCDM]+\.))', text):
        score += 8.0
    else:
        # If no numbering, it has a higher chance of being a title
        is_title_candidate = True

    # 5. Position on Page (Top of page is good)
    prev_line = all_lines[index - 1] if index > 0 else None
    if prev_line and line['page_num'] != prev_line['page_num']:
        # This is the first line on a new page
        score += 2.0

    # --- Contextual Penalties ---
    # Penalize if it looks like part of a paragraph (same style as lines around it)
    next_line = all_lines[index + 1] if index < len(all_lines) - 1 else None
    if prev_line and next_line and prev_line['style'] == style == next_line['style']:
        score *= 0.3 # Less likely to be a heading if surrounded by same-style text
        
    # Title-specific Boost
    if is_title_candidate and line['page_num'] == 0:
        score *= 1.5 # Boost title candidates on first page
        
    return score, is_title_candidate


# --- Main Orchestration ---

def process_pdf(pdf_path):
    """Main orchestrator."""
    print(f"Processing {os.path.basename(pdf_path)}...")
    try:
        lines, doc_features = get_document_lines_and_features(pdf_path)
        title, outline = analyze_document_structure(lines, doc_features)
        
        # Final cleanup for titles from forms/flyers
        if len(outline) == 0 and len(title.split()) > 15:
            # If we found no outline, the 'title' might just be the largest block of text.
            # Let's be more conservative for documents that look like forms.
            # A simple heuristic: if no outline, shorten the title.
            title_words = title.split()
            title = ' '.join(title_words[:8]) + ('...' if len(title_words) > 8 else '')


        return {"title": title.strip(), "outline": outline}
    except Exception as e:
        print(f" - CRITICAL FAILURE processing {os.path.basename(pdf_path)}: {e}")
        import traceback
        traceback.print_exc()
        return {"title": "Error processing file", "outline": []}


if __name__ == "__main__":
    input_dir = "/app/input"
    output_dir = "/app/output"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in sorted(os.listdir(input_dir)):
        if filename.lower().endswith(".pdf"):
            input_path = os.path.join(input_dir, filename)
            output_filename = os.path.splitext(filename)[0] + ".json"
            output_path = os.path.join(output_dir, output_filename)
            
            result = process_pdf(input_path)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
            print(f" - Saved final output to {output_path}")