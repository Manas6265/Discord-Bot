
#Purpose: To confirm that our code and the Cohere API both enforce the documented rate limits, and that our  system recovers gracefully after waiting.
import unittest
import asyncio
import time
import os
import json
from cogs import ai

COHERE_TRIAL_LIMIT = 20  # Cohere trial: 20 chat calls/minute as of July 2025[2][5]
TEST_QUERIES = [
    f"Test query {i+1}" for i in range(COHERE_TRIAL_LIMIT + 5)  # Exceed the limit
]
AI_AVAILABILITY_FILE = ai.AI_AVAILABILITY_FILE

def print_availability_state():
    if os.path.exists(AI_AVAILABILITY_FILE):
        with open(AI_AVAILABILITY_FILE, "r") as f:
            state = json.load(f)
        print("AI Availability State:", json.dumps(state, indent=2))
    else:
        print("AI_AVAILABILITY_FILE not found.")

class TestCohereRateLimit(unittest.TestCase):
    def test_cohere_rate_limit(self):
        ai.reset_ai_availability()
        options = {"session_id": "ratelimit-test", "user_id": "ratelimit-tester"}
        got_real_answer = 0
        got_rate_limit_error = 0
        for i, query in enumerate(TEST_QUERIES):
            print(f"\n--- Query {i+1}/{len(TEST_QUERIES)}: {query} ---")
            print_availability_state()
            try:
                result = asyncio.run(ai.analyze(query, options=options))
            except Exception as e:
                print(f"[ai.analyze Exception]: {e}")
                result = None
            print(f"Result: {json.dumps(result, indent=2)}")
            print_availability_state()
            if result:
                error = result["result"].get("error")
                if error and ("rate limit" in error.lower() or "unavailable" in error.lower()):
                    got_rate_limit_error += 1
                elif not error:
                    got_real_answer += 1
            # No sleep: we want to hit the rate limit as quickly as possible
        print(f"\nSummary:")
        print(f"  Real answers: {got_real_answer}")
        print(f"  Rate limit/unavailable errors: {got_rate_limit_error}")
        self.assertGreater(got_rate_limit_error, 0, "Did not hit rate limit as expected.")

        # Wait and try again to see if recovery works after a minute
        print("\nWaiting 65 seconds to allow rate limit to reset...")
        time.sleep(65)
        ai.reset_ai_availability()
        print_availability_state()
        result = asyncio.run(ai.analyze("Is the provider available again?", options=options))
        print(f"Recovery Result: {json.dumps(result, indent=2)}")
        print_availability_state()
        self.assertIsNone(result["result"].get("error"), "Provider did not recover after rate limit reset.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
