import csv
import sys
import math

# ----------------------------------------------------------------
# Bucket ranges (must match the C++ pintool)
# ----------------------------------------------------------------
BUCKET_RANGES = {
    0: "cold",
    1: "1-10",
    2: "11-100",
    3: "101-1000",
    4: "1001-10000",
    5: ">10000"
}

# Decay factor — must match pintool
ALPHA = 0.9

# Train/test split ratio
TRAIN_RATIO = 0.7

# ----------------------------------------------------------------
# Load bucket_reuse.csv
# ----------------------------------------------------------------
def load_csv(filepath):
    data = {}
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row["Address"].strip().lower()
            counts = [
                int(row["B0_cold"]),
                int(row["B1_1-10"]),
                int(row["B2_11-100"]),
                int(row["B3_101-1000"]),
                int(row["B4_1001-10000"]),
                int(row["B5_gt10000"]),
            ]
            total       = int(row["TotalAccesses"])
            pred_bucket = row["PredictedBucket"].strip()
            pred_range  = row["PredictedRange"].strip()

            data[addr] = {
                "counts":      counts,
                "total":       total,
                "pred_bucket": pred_bucket,
                "pred_range":  pred_range
            }
    return data

# ----------------------------------------------------------------
# Reconstruct history sequence from counts
# Order: cold misses first, then B1..B5 in order
# This is an approximation since CSV doesnt store exact order
# ----------------------------------------------------------------
def reconstruct_history(counts):
    history = []
    for b in range(6):
        history.extend([b] * counts[b])
    return history

# ----------------------------------------------------------------
# Weighted majority vote on a given history sequence
# score(b) = sum of α^(N-1-i) for all i where history[i] == b
# Skip B0 cold miss
# ----------------------------------------------------------------
def weighted_predict(history):
    N = len(history)
    if N == 0:
        return -1, {}

    scores = {i: 0.0 for i in range(6)}

    for i, bucket in enumerate(history):
        if bucket == 0:
            continue   # skip cold miss
        weight = ALPHA ** (N - 1 - i)
        scores[bucket] += weight

    # Find bucket with highest score (B1-B5 only)
    pred_bucket = -1
    max_score   = 0.0

    for b in range(1, 6):
        if scores[b] > max_score:
            max_score   = scores[b]
            pred_bucket = b

    return pred_bucket, scores

# ----------------------------------------------------------------
# Validate prediction using train/test split
#
# Steps:
#   1. Reconstruct full history from counts
#   2. Split into 70% train / 30% test
#   3. Build weighted prediction from training set
#   4. Check each test access — did we predict the right bucket?
#   5. Report accuracy
# ----------------------------------------------------------------
def validate(counts):
    history = reconstruct_history(counts)

    # Filter out cold miss (B0) for validation
    # Cold miss only happens once, not meaningful to validate
    filtered = [b for b in history if b != 0]

    if len(filtered) < 2:
        return None   # not enough data to split

    # Split
    split_idx  = int(len(filtered) * TRAIN_RATIO)
    train_set  = filtered[:split_idx]
    test_set   = filtered[split_idx:]

    if len(train_set) == 0 or len(test_set) == 0:
        return None   # not enough data

    # Predict from training set
    pred_bucket, scores = weighted_predict(train_set)

    if pred_bucket == -1:
        return None   # no valid prediction

    # Check against test set
    correct = sum(1 for b in test_set if b == pred_bucket)
    total   = len(test_set)
    accuracy = (correct / total) * 100

    return {
        "train_size":   len(train_set),
        "test_size":    total,
        "pred_bucket":  pred_bucket,
        "pred_range":   BUCKET_RANGES[pred_bucket],
        "correct":      correct,
        "accuracy":     accuracy,
        "scores":       scores
    }

# ----------------------------------------------------------------
# Print full histogram for an address
# ----------------------------------------------------------------
def print_histogram(addr, counts, scores):
    total = sum(counts[1:])
    print(f"\n  Address : {addr}")
    print(f"  {'Bucket':<22} {'Count':>6}   {'WeightedScore':>14}   Bar")
    print(f"  {'-'*65}")
    for i, label in BUCKET_RANGES.items():
        bar   = "█" * min(counts[i], 40)
        score = scores.get(i, 0.0)
        print(f"  B{i} ({label:<14})  {counts[i]:>6}   {score:>14.4f}   {bar}")
    print(f"  {'-'*65}")
    print(f"  Total accesses (excl cold): {total}")

# ----------------------------------------------------------------
# Run validation across ALL addresses and report overall accuracy
# ----------------------------------------------------------------
def run_full_validation(data):
    print("\n" + "=" * 60)
    print("  VALIDATION REPORT")
    print(f"  Train/Test Split : {int(TRAIN_RATIO*100)}% / {int((1-TRAIN_RATIO)*100)}%")
    print(f"  Decay Factor (α) : {ALPHA}")
    print("=" * 60)

    total_addresses   = 0
    validated         = 0
    total_correct     = 0
    total_test        = 0
    per_bucket_correct = {i: 0 for i in range(1, 6)}
    per_bucket_total   = {i: 0 for i in range(1, 6)}

    for addr, info in sorted(data.items()):
        result = validate(info["counts"])

        if result is None:
            continue

        total_addresses += 1
        validated       += 1
        total_correct   += result["correct"]
        total_test      += result["test_size"]

        pb = result["pred_bucket"]
        per_bucket_correct[pb] += result["correct"]
        per_bucket_total[pb]   += result["test_size"]

    if validated == 0:
        print("\n  Not enough data to validate any address.")
        return

    overall_accuracy = (total_correct / total_test * 100) if total_test > 0 else 0

    # Per address summary
    print(f"\n  {'Address':<20} {'TrainSize':>10} {'TestSize':>10} {'Predicted':>12} {'Correct':>8} {'Accuracy':>10}")
    print(f"  {'-'*75}")

    for addr, info in sorted(data.items()):
        result = validate(info["counts"])
        if result is None:
            continue
        print(f"  {addr:<20} {result['train_size']:>10} {result['test_size']:>10} "
              f"  B{result['pred_bucket']} {result['pred_range']:<9} "
              f"{result['correct']:>8} {result['accuracy']:>9.1f}%")

    # Overall summary
    print(f"\n  {'-'*75}")
    print(f"\n  OVERALL RESULTS:")
    print(f"  Addresses Validated : {validated}")
    print(f"  Total Test Accesses : {total_test}")
    print(f"  Total Correct       : {total_correct}")
    print(f"  Overall Accuracy    : {overall_accuracy:.1f}%")

    # Per bucket accuracy
    print(f"\n  PER BUCKET ACCURACY:")
    print(f"  {'Bucket':<20} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print(f"  {'-'*50}")
    for b in range(1, 6):
        if per_bucket_total[b] > 0:
            acc = per_bucket_correct[b] / per_bucket_total[b] * 100
            print(f"  B{b} ({BUCKET_RANGES[b]:<14}) {per_bucket_correct[b]:>8} "
                  f"{per_bucket_total[b]:>8} {acc:>9.1f}%")

    print()

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    csv_file = "bucket_reuse.csv"

    if len(sys.argv) > 1:
        csv_file = sys.argv[1]

    print(f"Loading {csv_file}...")
    try:
        data = load_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: {csv_file} not found. Run the Pin tool first.")
        sys.exit(1)

    print(f"Loaded {len(data)} addresses.\n")

    print("=" * 60)
    print("  Reuse Distance Predictor (Exponential Weighted Majority)")
    print(f"  Decay factor α = {ALPHA}")
    print("  Commands:")
    print("    <address>  → predict reuse for that address")
    print("    list       → show all addresses and predictions")
    print("    validate   → run full validation report")
    print("    quit       → exit")
    print("=" * 60)

    while True:
        query = input("\nEnter command: ").strip().lower()

        if query == "quit":
            print("Exiting.")
            break

        elif query == "validate":
            run_full_validation(data)

        elif query == "list":
            print(f"\n  {'Address':<20} {'TotalAccesses':>14} {'PredictedBucket':>16} {'PredictedRange'}")
            print(f"  {'-'*70}")
            for addr, info in sorted(data.items()):
                print(f"  {addr:<20} {info['total']:>14} {info['pred_bucket']:>16} {info['pred_range']}")

        elif query in data:
            info   = data[query]
            counts = info["counts"]

            # Compute weighted scores for display
            history             = reconstruct_history(counts)
            pred_bucket, scores = weighted_predict(history)

            print_histogram(query, counts, scores)

            # Prediction
            print(f"\n  >>> Prediction for next access to {query}:")
            if pred_bucket == -1:
                print(f"      Not enough data (only cold miss seen)")
            else:
                total_score = sum(scores.values())
                confidence  = (scores[pred_bucket] / total_score * 100) if total_score > 0 else 0
                print(f"      Predicted Bucket : B{pred_bucket}")
                print(f"      Predicted Range  : {BUCKET_RANGES[pred_bucket]} instructions")
                print(f"      Weighted Score   : {scores[pred_bucket]:.4f} / {total_score:.4f}")
                print(f"      Confidence       : {confidence:.1f}%")

            # Validation for this address
            result = validate(counts)
            if result:
                print(f"\n  >>> Validation for {query}:")
                print(f"      Train Size : {result['train_size']} accesses")
                print(f"      Test Size  : {result['test_size']} accesses")
                print(f"      Predicted  : B{result['pred_bucket']} ({result['pred_range']})")
                print(f"      Correct    : {result['correct']} / {result['test_size']}")
                print(f"      Accuracy   : {result['accuracy']:.1f}%")
            else:
                print(f"\n  >>> Not enough data to validate {query}")

        else:
            print(f"  Address {query} not found in trace.")
            print(f"  Make sure it matches the format in the CSV (e.g. 0x7fff1234)")

if __name__ == "__main__":
    main()