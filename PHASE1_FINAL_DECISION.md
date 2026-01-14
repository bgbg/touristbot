# Phase 1 Final Decision: Proceed with Phase 2B (Hybrid Approach)

**Date:** 2026-01-14
**Issue:** #17 - Add multimodal search support to display images in bot responses
**Decision:** **Proceed with Phase 2B - Hybrid Approach**

## Technical Findings

### 1. SDK Blocker Confirmed

**Error:** `400 INVALID_ARGUMENT - tools[0].tool_type: required one_of 'tool_type' must have one initialized field`

**Root Cause (from web research):**
- Known issue in google-genai SDK (versions 1.19.0+, currently at 1.57.0)
- Affects standalone scripts but not always Streamlit/application contexts
- Multiple open GitHub issues across googleapis/python-genai and related projects
- Related to how Tool types are serialized in the API request

**Sources:**
- [url_context tool not working · Issue #940 · googleapis/python-genai](https://github.com/googleapis/python-genai/issues/940)
- [Python tool calling fails with `400 INVALID_ARGUMENT` · Issue #907 · googleapis/python-genai](https://github.com/googleapis/python-genai/issues/907)
- [GeminiModel failure when using Vertex AI mode · Issue #1039 · strands-agents/sdk-python](https://github.com/strands-agents/sdk-python/issues/1039)

### 2. File Search Image Support Research

**Key Finding:** File Search API documentation **does not mention image extraction from DOCX files**.

**What File Search Does:**
- Imports documents (DOCX, PDF, TXT, JSON, code files)
- **Chunks and indexes TEXT content**
- Creates embeddings for semantic search
- Returns text snippets with citations

**What's NOT Documented:**
- Image extraction from documents
- Image indexing or embedding
- Image URIs in grounding metadata
- OCR or visual content processing

**Sources:**
- [File Search | Gemini API Documentation](https://ai.google.dev/gemini-api/docs/file-search)
- [Introducing the File Search Tool in Gemini API](https://blog.google/technology/developers/file-search-gemini-api/)
- [Gemini API File Search Tutorial | DataCamp](https://www.datacamp.com/tutorial/google-file-search-tool)

**Conclusion:** File Search is designed for **text-based semantic retrieval**. Images embedded in documents are **not extracted or indexed** for search.

### 3. DOCX Upload Success

✅ **Confirmed Working:**
- DOCX files upload successfully to File Search Store
- MIME type correctly identified
- Metadata (area/site/doc) preserved
- File recognized and processed

## Decision Rationale

### Why Phase 2B (Hybrid Approach)?

1. **File Search Limitation:** No evidence that File Search extracts or indexes images from DOCX files. Documentation focuses exclusively on text content.

2. **SDK Issue Secondary:** Even if we fix the SDK query issue, Phase 2B would likely still be needed because File Search doesn't handle images.

3. **Maximum Control:** Phase 2B gives us full control over:
   - Image extraction timing and quality
   - Image-caption relationship preservation
   - Image metadata (keywords, descriptions, context)
   - Image storage and delivery (GCS + File API)
   - Model-based image relevance decisions

4. **Future-Proof:** Independent of File Search black-box behavior changes

5. **Time Efficiency:** Avoiding further SDK debugging saves time for actual implementation

## Phase 2B Implementation Plan

### Core Strategy

**Upload Flow:**
1. Upload DOCX to File Search for text indexing (already working)
2. Extract images from DOCX with `python-docx`
3. Extract captions (paragraph immediately after image in Hebrew)
4. Extract context paragraphs (before/after image)
5. Store images in GCS: `images/{area}/{site}/{doc}/image_001.jpg`
6. Upload images to File API to get URIs
7. Create `image_registry.json` mapping images to metadata

**Query Flow:**
1. File Search retrieves relevant text chunks (existing)
2. Check image registry for images at chunk location (area/site/doc)
3. If images exist, include in multimodal context
4. Let Gemini model decide if images enhance the response
5. Display images in Streamlit UI with captions

### Image-Caption Extraction

```python
from docx import Document

def extract_images_with_captions(docx_path):
    doc = Document(docx_path)
    images = []

    for i, paragraph in enumerate(doc.paragraphs):
        # Check if paragraph contains an image (inline shape)
        for run in paragraph.runs:
            if run._element.xpath('.//w:drawing'):
                # Get the actual image data
                for rel in doc.part.rels.values():
                    if "image" in rel.target_ref:
                        # Extract image
                        # Get caption from next paragraph
                        caption = doc.paragraphs[i+1].text if i+1 < len(doc.paragraphs) else ""
                        images.append({
                            "image_data": rel.target_part.blob,
                            "caption": caption,
                            "context_before": doc.paragraphs[i-1].text if i > 0 else "",
                            "context_after": doc.paragraphs[i+2].text if i+2 < len(doc.paragraphs) else ""
                        })
    return images
```

### Storage Schema

**GCS Structure:**
```
images/
  hefer_valley/
    agamon_hefer/
      אגמון_חפר/
        image_001.jpg
        image_002.jpg
        ...
```

**Image Registry (`image_registry.json`):**
```json
{
  "hefer_valley/agamon_hefer/אגמון_חפר/image_001": {
    "caption": "שקנאי – צייפור נודדת ושוכנת לתינות באגמון",
    "context_before": "paragraph before image",
    "context_after": "paragraph after image",
    "gcs_path": "images/hefer_valley/agamon_hefer/אגמון_חפר/image_001.jpg",
    "file_api_uri": "files/xxx",
    "area": "hefer_valley",
    "site": "agamon_hefer",
    "doc": "אגמון_חפר"
  }
}
```

## Next Steps

1. **Start Phase 2B Implementation:**
   - Create `gemini/image_extractor.py` for DOCX image extraction
   - Implement image-caption extraction logic
   - Test with Hebrew captions and RTL text

2. **GCS Image Storage:**
   - Create GCS directory structure
   - Upload extracted images
   - Generate publicly accessible URLs

3. **File API Integration:**
   - Upload images to File API
   - Store URIs in registry

4. **Image Registry:**
   - Create `gemini/image_registry.py`
   - Implement query methods

5. **Upload Pipeline Integration:**
   - Modify `main_upload.py` to call image extraction
   - Track image uploads

6. **QA Flow Updates:**
   - Modify `get_response()` to query image registry
   - Include images in multimodal context

7. **Streamlit UI:**
   - Add image display components
   - Show captions and metadata

## Estimated Complexity

**Phase 2B Components:**
- Image extraction module: Medium complexity (Hebrew caption extraction)
- GCS storage: Low complexity (existing infrastructure)
- File API integration: Low complexity (similar to current uploads)
- Image registry: Medium complexity (query logic, metadata management)
- Upload pipeline: Low complexity (add image processing step)
- QA flow: Medium complexity (multimodal context construction)
- Streamlit UI: Low complexity (st.image() with captions)

**Total Estimate:** 6-8 hours of focused implementation + testing

## Conclusion

**Decision: Proceed with Phase 2B (Hybrid Approach)**

**Rationale:**
- File Search does not extract/index images (per documentation research)
- SDK issue is secondary to this fundamental limitation
- Phase 2B provides maximum control and flexibility
- Implementation is well-scoped and achievable

**Status:** Phase 1 validation complete ✅
**Next:** Begin Phase 2B implementation

---

**Research Sources:**
- [File Search API Documentation](https://ai.google.dev/gemini-api/docs/file-search)
- [Gemini API Blog Post](https://blog.google/technology/developers/file-search-gemini-api/)
- [google-genai SDK Issues](https://github.com/googleapis/python-genai/issues)
