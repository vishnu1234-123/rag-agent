import pandas as pd

df = pd.read_csv("week4/apple_10k_testset_100.csv")

# fix 1: shareholders' equity question with wrong year's figure
mask1 = df["user_input"] == "What was the total shareholders' equity for Apple Inc. on September 28, 2024?"
df.loc[mask1, "reference"] = "Total shareholders' equity for Apple Inc. on September 28, 2024, was $56,950 million."

# fix 2: MacBook Air question missing Mac Studio
mask2 = df["user_input"] == "What products are expected to be released alongside the MacBook Air in the second quarter of 2025?"
df.loc[mask2, "reference"] = "In the second quarter of 2025, the expected product releases alongside the MacBook Air include the iPhone 16e, iPad Air, iPad, and Mac Studio."

print(f"Fix 1 applied to {mask1.sum()} row(s)")
print(f"Fix 2 applied to {mask2.sum()} row(s)")

df.to_csv("week4/apple_10k_testset_100.csv", index=False)
print("\nSaved updated apple_10k_testset_100.csv")