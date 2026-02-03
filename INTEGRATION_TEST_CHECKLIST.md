# Admin UI Integration Test Checklist

## Pre-Test Setup

- [ ] GCS credentials configured in `.streamlit/secrets.toml`
- [ ] Test data available in GCS bucket (conversations, content, images)
- [ ] Main app not running on port 8501 (to avoid conflicts)

## Test 1: Authentication and Home Page

**Steps:**
1. Run: `streamlit run admin_ui/app.py --server.port 8502`
2. Open: http://localhost:8502

**Expected Results:**
- [ ] Home page loads without errors
- [ ] Sidebar shows bucket name
- [ ] Quick stats display (Locations, Conversations, Images)
- [ ] No authentication errors

**Pass/Fail:** _____

---

## Test 2: Upload Content Page

**Steps:**
1. Navigate to "📤 Upload Content" page
2. Enter area: `test_area`
3. Enter site: `test_site`
4. Upload a sample DOCX file (< 50 MB)
5. Click "Upload" button

**Expected Results:**
- [ ] File uploader accepts DOCX file
- [ ] Progress bar displays during upload
- [ ] Upload completes successfully
- [ ] Metrics show: uploaded count, images, topics
- [ ] Existing locations list shows `test_area / test_site`

**Pass/Fail:** _____

**Notes:**
- If upload fails, check error messages in expandable section
- Verify GCS bucket permissions if access denied

---

## Test 3: View Content Page

**Steps:**
1. Navigate to "📁 View Content" page
2. Expand area section (e.g., `test_area`)

**Expected Results:**
- [ ] Content hierarchy displays all areas
- [ ] Each site shows metrics: Files, Images, Topics, Last Updated
- [ ] Images section shows sample images with captions
- [ ] No errors loading metadata

**Pass/Fail:** _____

**Notes:**
- If images section is empty, verify image extraction during upload
- Topics may be 0 if topic generation failed

---

## Test 4: Conversations Page - List and Filter

**Steps:**
1. Navigate to "💬 Conversations" page
2. Leave filters empty, click to load (default limit: 100)
3. Try filtering by area
4. Try filtering by site

**Expected Results:**
- [ ] Conversation table displays with columns: ID, Location, Messages, Updated
- [ ] Filters correctly reduce result set
- [ ] Pagination limit works (try changing to 50)
- [ ] No errors loading conversations

**Pass/Fail:** _____

---

## Test 5: Conversations Page - View Details

**Steps:**
1. In conversation list, click "View" for any conversation
2. Scroll down to see conversation details

**Expected Results:**
- [ ] Conversation metadata displays (ID, location, created, updated, messages)
- [ ] Full message history displays (user and assistant messages)
- [ ] Citations shown in expandable sections (if present)
- [ ] Images shown in expandable sections (if present)
- [ ] "Close" button returns to list view

**Pass/Fail:** _____

---

## Test 6: Conversations Page - Delete Single

**Steps:**
1. View a conversation (click "View")
2. Scroll to bottom, click "Delete This Conversation"
3. Click again to confirm

**Expected Results:**
- [ ] First click shows warning "Click again to confirm"
- [ ] Second click deletes conversation
- [ ] Success message displays
- [ ] Conversation removed from list (refresh page to verify)

**Pass/Fail:** _____

---

## Test 7: Conversations Page - Bulk Delete

**Steps:**
1. Return to conversation list
2. Check boxes for 2-3 conversations
3. Scroll to "Bulk Operations" section
4. Click "Delete X conversations" button
5. Click again to confirm

**Expected Results:**
- [ ] Selected count displays correctly
- [ ] First click shows warning "Click again to confirm"
- [ ] Second click deletes all selected conversations
- [ ] Success message shows count of deleted conversations
- [ ] Selection cleared after delete

**Pass/Fail:** _____

---

## Test 8: Error Handling

**Steps:**
1. Try uploading invalid file (e.g., .exe)
2. Try uploading file > 50 MB
3. Try viewing content with missing GCS permissions
4. Try filtering conversations with invalid characters

**Expected Results:**
- [ ] Invalid file rejected with clear error message
- [ ] Large file rejected with file size error
- [ ] GCS errors display with details in expander
- [ ] Invalid filters handled gracefully (no crashes)

**Pass/Fail:** _____

---

## Test 9: Performance

**Steps:**
1. Load conversations page with 1000+ conversations (set limit to 1000)
2. Upload large DOCX file (20+ pages)
3. View content page with 100+ images

**Expected Results:**
- [ ] Conversation list loads in < 5 seconds
- [ ] Upload completes without timeout
- [ ] Content page loads in < 3 seconds
- [ ] No memory errors or crashes

**Pass/Fail:** _____

**Notes:**
- If slow, try reducing limit or applying filters
- Large uploads may take longer depending on file size

---

## Test 10: Navigation and Session State

**Steps:**
1. Navigate between all pages multiple times
2. Upload file on Upload page
3. Navigate to View Content page (verify upload appears)
4. Return to Upload page (verify form cleared)

**Expected Results:**
- [ ] Navigation works without errors
- [ ] Session state persists across page changes
- [ ] No stale data displayed
- [ ] Forms reset when navigating away and back

**Pass/Fail:** _____

---

## Summary

**Total Tests Passed:** _____ / 10

**Critical Issues Found:**
- 
- 
- 

**Non-Critical Issues:**
- 
- 
- 

**Recommendations:**
- 
- 
- 

**Tested By:** _____________  
**Date:** _____________  
**Environment:** Local / Cloud Run (circle one)
