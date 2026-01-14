# Phase 1 Validation Results: File Search Image Support

**Date:** 2026-01-14
**Issue:** #17 - Add multimodal search support to display images in bot responses
**Branch:** `feature/17-add-multimodal-search-support-to-display-images`

## Objective

Test whether Gemini File Search API extracts and indexes images from DOCX files when uploaded.

## Test Performed

1. **Sample File:** `data/locations/hefer_valley/agamon_hefer/אגמון חפר.docx` (28KB)
   - Contains Hebrew text with embedded images
   - Images have captions below them (e.g., "שקנאי – צייפור נודדת ושוכנת לתינות באגמון")

2. **Upload Result:** ✅ **SUCCESS**
   - File uploaded successfully to File Search Store
   - MIME Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
   - File Search recognized it as DOCX format
   - Metadata preserved (area, site, doc)

3. **Query Test:** ⚠️ **BLOCKED - Technical Issue**
   - Encountered SDK API error when attempting to query: `400 INVALID_ARGUMENT - tools[0].tool_type: required one_of 'tool_type' must have one initialized field`
   - Same code structure that works in `main_qa.py` fails in standalone scripts
   - Possible google-genai SDK version issue or environment-specific problem

## Key Finding: DOCX Upload Works

**Important:** File Search **accepts DOCX files** and recognizes them correctly. The upload pipeline works.

## Unable to Confirm

Due to the technical query issue, we could **not confirm**:
- Whether File Search extracts images from DOCX files
- Whether image URIs appear in `grounding_metadata`
- Whether images are returned in query responses

## Recommendations

### Option 1: Manual UI Test (Quickest)
**Action:** Use the running Streamlit app to query the uploaded DOCX manually
- Navigate to localhost:8502 (already running)
- Select area="hefer_valley", site="agamon_hefer"
- Ask: "ספר לי על שקנאים" (Tell me about pelicans)
- Check the response and Sources section for images

**This will definitively answer:**
- Do images appear in bot responses?
- Are image URIs in grounding metadata/citations?

### Option 2: Fix SDK Issue (Time-consuming)
**Action:** Debug the `types.Tool()` construction issue
- Investigate google-genai SDK version compatibility
- Review API changes or breaking changes in recent versions
- May require SDK update or code refactoring

### Option 3: Proceed with Phase 2B Assumption (Safe Path)
**Action:** Assume File Search does **not** extract images, implement hybrid approach
- Upload DOCX for text indexing (already working)
- Extract images separately with python-docx
- Store images in GCS, upload to File API
- Create image registry for retrieval

**Rationale:**
- Most control over image handling
- Independent of File Search black-box behavior
- Future-proof if File Search limitations exist
- Aligns with documented File Search capabilities (text-focused)

## Decision Point

**Recommendation:** **Proceed with Option 1 (Manual UI Test)** first

**Why:**
1. Takes 2-3 minutes to test via Streamlit UI
2. Provides definitive answer without debugging SDK
3. If images appear → Simple Phase 2A path
4. If no images → Confirms Phase 2B hybrid approach needed

**Next Steps if Option 1:**
1. Open Streamlit UI (localhost:8502)
2. Test query on uploaded DOCX
3. Inspect response for images
4. Document findings
5. Proceed with Phase 2A or 2B based on result

## Technical Notes

- **Filename Encoding Issue:** Hebrew filenames cause ASCII encoding errors during upload. Workaround: copy to temp file with ASCII name before upload.
- **SDK Version:** google-genai==1.57.0
- **Model:** gemini-2.0-flash
- **Store:** `fileSearchStores/tarasatourismrag-yhh2ivs2lpq4`

## Files Created

- `gemini/validate_file_search_images.py` - Validation script (query part has SDK issue)
- `list_file_search_contents.py` - Lists uploaded documents (works)
- `test_file_search_simple.py` - Simplified query test (same SDK issue)
- `temp_validation_test.docx` - Temp file used for upload (deleted after upload)

## Conclusion

**Status:** Validation incomplete due to technical blocker
**Uploaded DOCX:** ✅ Successfully uploaded to File Search
**Image Extraction:** ❓ Unknown (query test blocked by SDK issue)

**Recommended Action:** Manual UI test via Streamlit to confirm image handling before proceeding with Phase 2A or 2B implementation.
