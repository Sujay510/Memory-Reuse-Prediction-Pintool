#include "pin.H"
#include <iostream>
#include <fstream>
#include <array>
#include <vector>
#include <cmath>

using namespace std;

// ---------------- OUTPUT FILE ----------------

ofstream bucketOut;   // writes bucket histogram + prediction CSV on exit

// ---------------- GLOBAL STATE ----------------

static UINT64 totalInstructions = 0;

// For each memory address:
//   lastSeen → instruction count when this address was last accessed
//   buckets  → 6 counters, one per reuse distance bucket (for histogram display)
//   history  → full sequence of bucket indices in order of access (for weighted prediction)
map<ADDRINT, UINT64>           lastSeen;
map<ADDRINT, array<UINT64, 6>> buckets;
map<ADDRINT, vector<int>>      history;

// Decay factor for exponential weighting
// α = 0.9 means recent accesses matter more, old ones fade gradually
const double ALPHA = 0.9;

// Bucket ranges:
//   B0 → cold miss (first access ever)
//   B1 → 1     - 10
//   B2 → 11    - 100
//   B3 → 101   - 1000
//   B4 → 1001  - 10000
//   B5 → >10000

// ---------------- BUCKET HELPER ----------------

int getBucket(UINT64 dist) {
    if (dist <= 10)    return 1;
    if (dist <= 100)   return 2;
    if (dist <= 1000)  return 3;
    if (dist <= 10000) return 4;
    return 5;
}

// Bucket index → human readable range string
string getBucketRange(int b) {
    switch(b) {
        case 0: return "cold";
        case 1: return "1-10";
        case 2: return "11-100";
        case 3: return "101-1000";
        case 4: return "1001-10000";
        case 5: return ">10000";
        default: return "unknown";
    }
}

// ---------------- WEIGHTED PREDICTION ----------------

// For each bucket b:
//   score(b) = sum of α^(N-i) for all positions i where history[i] == b
// N = total accesses, i = position (1=oldest, N=newest)
// Bucket with highest score is predicted
// Skip B0 (cold miss) — not meaningful to predict

int weightedPredict(const vector<int> &hist) {
    int    N          = hist.size();
    double scores[6]  = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};

    for (int i = 0; i < N; i++) {
        int bucket = hist[i];
        if (bucket == 0) continue;             // skip cold miss

        // position i (0-indexed), newest = N-1
        // weight = α^(N-1-i)  → newest gets α^0 = 1.0
        double weight = pow(ALPHA, (N - 1 - i));
        scores[bucket] += weight;
    }

    // Find bucket with highest score (B1-B5 only)
    int    predBucket = -1;
    double maxScore   = 0.0;

    for (int i = 1; i < 6; i++) {
        if (scores[i] > maxScore) {
            maxScore   = scores[i];
            predBucket = i;
        }
        // tie → smaller bucket wins (already handled since we iterate i=1..5)
    }

    return predBucket;   // -1 means only cold miss seen
}

// ---------------- MEMORY ACCESS HANDLER ----------------

VOID RecordMemAccess(ADDRINT ip, ADDRINT addr) {
    auto it = lastSeen.find(addr);

    if (it == lastSeen.end()) {
        // First time this address is accessed → cold miss → B0
        buckets[addr][0]++;
        history[addr].push_back(0);
    } else {
        // Seen before → compute distance → update bucket + history
        UINT64 dist   = totalInstructions - it->second;
        int    bucket = getBucket(dist);
        buckets[addr][bucket]++;
        history[addr].push_back(bucket);
    }

    // Update last seen timestamp
    lastSeen[addr] = totalInstructions;
}

// ---------------- INSTRUCTION COUNT ----------------

VOID CountInstruction() {
    totalInstructions++;
}

// ---------------- INSTRUMENTATION ----------------

VOID Instruction(INS ins, VOID *v) {

    // Count every instruction to keep totalInstructions accurate
    INS_InsertCall(ins, IPOINT_BEFORE,
                   (AFUNPTR)CountInstruction,
                   IARG_END);

    // Record memory reads
    if (INS_IsMemoryRead(ins)) {
        INS_InsertCall(ins, IPOINT_BEFORE,
                       (AFUNPTR)RecordMemAccess,
                       IARG_INST_PTR,       // PC (metadata)
                       IARG_MEMORYREAD_EA,  // memory address (the key)
                       IARG_END);
    }

    // Record memory writes
    if (INS_IsMemoryWrite(ins)) {
        INS_InsertCall(ins, IPOINT_BEFORE,
                       (AFUNPTR)RecordMemAccess,
                       IARG_INST_PTR,        // PC (metadata)
                       IARG_MEMORYWRITE_EA,  // memory address (the key)
                       IARG_END);
    }
}

// ---------------- FINI ----------------

VOID Fini(INT32 code, VOID *v) {

    // Header
    bucketOut << "Address,"
              << "B0_cold,"
              << "B1_1-10,"
              << "B2_11-100,"
              << "B3_101-1000,"
              << "B4_1001-10000,"
              << "B5_gt10000,"
              << "TotalAccesses,"
              << "PredictedBucket,"
              << "PredictedRange\n";

    for (auto &kv : buckets) {
        ADDRINT            addr = kv.first;
        array<UINT64, 6> &bkts = kv.second;
        vector<int>       &hist = history[addr];

        // Weighted majority vote prediction
        int predBucket = weightedPredict(hist);

        // Total accesses excluding cold miss
        UINT64 totalAccesses = 0;
        for (int i = 1; i < 6; i++) totalAccesses += bkts[i];

        // Write row
        bucketOut << "0x" << hex << addr << dec
                  << "," << bkts[0]
                  << "," << bkts[1]
                  << "," << bkts[2]
                  << "," << bkts[3]
                  << "," << bkts[4]
                  << "," << bkts[5]
                  << "," << totalAccesses
                  << "," << (predBucket == -1 ? "N/A"       : to_string(predBucket))
                  << "," << (predBucket == -1 ? "cold-only" : getBucketRange(predBucket))
                  << "\n";
    }

    bucketOut.close();
}

// ---------------- MAIN ----------------

int main(int argc, char *argv[]) {

    if (PIN_Init(argc, argv)) {
        cerr << "PIN Init Failed\n";
        return 1;
    }

    bucketOut.open("bucket_reuse.csv");
    if (!bucketOut.is_open()) {
        cerr << "Error opening bucket_reuse.csv\n";
        return 1;
    }

    INS_AddInstrumentFunction(Instruction, 0);
    PIN_AddFiniFunction(Fini, 0);

    PIN_StartProgram();
    return 0;
}