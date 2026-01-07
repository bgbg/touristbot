# Testing Guide for Conversation History Fix

## Implementation Status

✅ **Core Implementation Complete**
- Function signature updated to accept `messages` parameter
- Conversation history building logic implemented
- Message format conversion with role mapping (assistant → model)
- Sliding window implementation (last 10 messages)
- Metadata stripping (time field)
- Unit tests created and passing

## Unit Tests

Unit tests have been created and all pass:

```bash
python test_conversation_history.py
```

Tests cover:
- Basic conversation flow
- Sliding window (10 message limit)
- Role mapping (assistant → model)
- Metadata stripping
- Invalid role filtering
- Empty message handling

## Integration Testing Required

The following integration tests require manual execution with actual API key and test data:

### Prerequisites

1. **Set up Streamlit secrets** (`.streamlit/secrets.toml`):
   ```toml
   GEMINI_API_KEY = "your-api-key-here"
   ```

2. **Upload test content**:
   - Use the "Manage Content" tab to upload some test documents
   - Or place test files in `data/locations/<area>/<site>/` directory

### Test Cases

#### Test 1: Basic Follow-up Question
1. Start the app: `streamlit run gemini/main_qa.py`
2. Select an area/site with uploaded content
3. Ask: "What attractions are available?"
4. Wait for response
5. Ask follow-up: "Tell me more about the first one"
6. **Expected**: AI responds with details about the first attraction mentioned in the previous response

#### Test 2: Multi-turn Conversation
1. Continue from Test 1
2. Ask: "What else is interesting there?"
3. Ask: "How do I get there?"
4. **Expected**: AI maintains context across multiple turns

#### Test 3: Clear Chat
1. Continue from Test 2
2. Click "🗑️ Clear Chat" button
3. Ask: "Tell me more about that"
4. **Expected**: AI should indicate it doesn't have context (since history was cleared)

#### Test 4: Location Change
1. Have conversation in one location
2. Switch to a different area/site using the dropdown
3. Ask a question in the new location
4. **Expected**: Chat history clears, conversation starts fresh for new location

#### Test 5: Sliding Window (Long Conversations)
1. Have a conversation with more than 10 exchanges (20+ messages)
2. Ask a follow-up that references something from the first question
3. **Expected**: AI may not remember very early messages (due to 10-message sliding window)

### Verification Checklist

- [ ] Follow-up questions receive contextually appropriate responses
- [ ] AI maintains awareness of previous messages
- [ ] No API errors or failures
- [ ] Chat history display in UI remains unchanged
- [ ] Clear Chat button works correctly
- [ ] Conversation resets when switching locations
- [ ] Long conversations (>10 exchanges) work without errors

## Known Limitations

1. **Sliding Window**: Only last 10 messages are kept to limit token usage
2. **No Token Counting**: If messages are very long, may still hit token limits
3. **No Conversation Persistence**: History cleared on location change or page refresh

## Files Modified

- `gemini/main_qa.py`: Core implementation (lines 128-175)
- `gemini/conversation_utils.py`: Shared conversion utility (new file)
- `test_conversation_history.py`: Unit tests (migrated to pytest)

## Next Steps

1. Complete integration testing using the test cases above
2. If all tests pass, proceed to create PR
3. If issues found, report them and adjust implementation
