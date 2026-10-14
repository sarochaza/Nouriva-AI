Thai Food Phase 1 - Windows / VS Code
1. Extract this starter ZIP into a new folder.
2. Extract thai_food_phase1_200.zip INTO THE SAME FOLDER so images/ and ground_truth.csv are next to main.py.
3. Open this folder in VS Code.
4. Terminal: py -m venv .venv
5. Terminal: .\.venv\Scripts\python.exe -m pip install -r requirements.txt
6. Copy .env.example to .env and replace PASTE_YOUR_KEY_HERE with your private Gemini API key.
7. Test 5 images: .\.venv\Scripts\python.exe main.py --limit 5
8. Evaluate: .\.venv\Scripts\python.exe evaluate.py
9. Full test: .\.venv\Scripts\python.exe main.py --limit 0

Keep .env private. API usage may incur charges. Verify the model name and API quota in Google AI Studio.
A run on only 5 images is a connectivity check, not a meaningful model-quality estimate.
The full 200-image run uses the provided labels. UNKNOWN is included as a possible prediction.
