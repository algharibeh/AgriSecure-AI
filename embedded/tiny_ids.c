/* AgriSecure-AI - embedded reference for the Phase 2 tiny detector.
 *
 * Part of the AgriSecure-AI project.
 *
 * Dependency-free C99. Two parts:
 *   1. rule_state_t / rules_check(): the Phase 1 per-PGN rules (allowed source
 *      address, minimum inter-arrival, physical range and rate of change) with
 *      O(1) state per PGN. Included so that the footprint of the whole hybrid
 *      detector can be measured, not just the model.
 *   2. tiny_ids_*(): a 1 s ring buffer of the four decoded signals, the
 *      12 window features, and the int8-weight model from model_weights.h.
 *      The model reads the features listed in TM_IN_IDX and predicts feature
 *      TM_OUT_IDX; score = squared residual (or, if TM_OUT_IDX < 0, the mean
 *      squared reconstruction error over all features); flag = score >
 *      TM_THRESHOLD.
 *
 * Build the self-test (needs test_vectors.h from export_embedded.py):
 *   gcc -std=c99 -O2 -Wall -o tiny_ids tiny_ids.c -lm && ./tiny_ids
 * Size on a Cortex-M4 target (no self-test main):
 *   arm-none-eabi-gcc -std=c99 -mcpu=cortex-m4 -mthumb -Os -DNO_MAIN -c tiny_ids.c
 *   arm-none-eabi-size tiny_ids.o
 *
 * Nothing here talks to a bus; it is a pure function of decoded values. It has
 * been run on a PC and cross-compiled for size only, not on an ECU.
 */
#include <stdint.h>
#include <math.h>
#include "model_weights.h"

/* ------------------------------------------------------------------------ */
/* Phase 1 rules, streaming form                                            */
/* ------------------------------------------------------------------------ */
#define N_PGN 8

typedef struct {
    uint32_t pgn;        /* parameter group */
    uint8_t  sa_ok;      /* learned legitimate source address */
    uint8_t  have_last;  /* 1 once a frame has been seen */
    float    iat_min_s;  /* 0.5 x smallest normal inter-arrival */
    float    last_t_s;   /* arrival time of the previous frame */
    float    last_val;   /* decoded primary signal of the previous frame */
    float    lo, hi;     /* physical range of the primary signal */
    float    dmax;       /* max |delta| per frame */
} rule_state_t;           /* 32 bytes on a 32-bit target with natural alignment */

static rule_state_t g_rules[N_PGN];

/* Returns a bit mask: 1 = foreign address, 2 = too fast, 4 = out of range,
 * 8 = impossible rate of change. 0 = frame passes. */
int rules_check(rule_state_t *s, uint8_t sa, float t_s, float val)
{
    int r = 0;
    if (sa != s->sa_ok) r |= 1;
    if (s->have_last) {
        if ((t_s - s->last_t_s) < s->iat_min_s && !(r & 1)) r |= 2;
        if (fabsf(val - s->last_val) > s->dmax) r |= 8;
    }
    if (val < s->lo || val > s->hi) r |= 4;
    if (!(r & 1)) { s->last_t_s = t_s; s->last_val = val; s->have_last = 1; }
    return r;
}

/* ------------------------------------------------------------------------ */
/* Window features + tiny model                                             */
/* ------------------------------------------------------------------------ */
#define N_SIG 4
#define WIN   10
#define STD_EPS 0.01f

typedef struct {
    float ring[WIN][N_SIG]; /* last 1 s of rpm, torque, fuel, speed at 100 ms */
    uint8_t head, count;
} window_t;

static window_t g_win;
static float g_feat[TM_N_FEAT];
static float g_act_a[TM_MAX_WIDTH], g_act_b[TM_MAX_WIDTH];

void tiny_ids_reset(void) { g_win.head = 0; g_win.count = 0; }

/* Push one grid cell (100 ms) of decoded signals. Returns 1 when a full
 * window is available and writes its 12 features to feat. */
int tiny_ids_push(const float sig[N_SIG], float feat[TM_N_FEAT])
{
    int i, k;
    for (k = 0; k < N_SIG; k++) g_win.ring[g_win.head][k] = sig[k];
    g_win.head = (uint8_t)((g_win.head + 1) % WIN);
    if (g_win.count < WIN) g_win.count++;
    if (g_win.count < WIN) return 0;
    for (k = 0; k < N_SIG; k++) {
        float mean = 0.f, var = 0.f, first, last;
        for (i = 0; i < WIN; i++) mean += g_win.ring[i][k];
        mean /= (float)WIN;
        for (i = 0; i < WIN; i++) { float d = g_win.ring[i][k] - mean; var += d * d; }
        first = g_win.ring[g_win.head][k];                   /* oldest sample */
        last  = g_win.ring[(g_win.head + WIN - 1) % WIN][k]; /* newest sample */
        feat[3 * k + 0] = mean;
        /* log10(population std + 0.01): a frozen signal reads -2 */
        feat[3 * k + 1] = log10f(sqrtf(var / (float)WIN) + STD_EPS);
        feat[3 * k + 2] = last - first;
    }
    return 1;
}

static void dense(const float *in, int n_in, const int8_t *W, float s,
                  const float *b, int n_out, float *out, int relu)
{
    int i, j;
    for (j = 0; j < n_out; j++) {
        float acc = b[j];
        for (i = 0; i < n_in; i++) acc += in[i] * ((float)W[i * n_out + j] * s);
        out[j] = (relu && acc < 0.f) ? 0.f : acc;
    }
}

/* Score one raw feature window: standardise, gather inputs, run the model,
 * return the squared residual (or MSE for a reconstruction model). */
float tiny_ids_score(const float feat[TM_N_FEAT])
{
    float z[TM_N_FEAT];
    float *cur = g_act_a, *nxt = g_act_b, *tmp;
    int l, i;
    for (i = 0; i < TM_N_FEAT; i++) z[i] = (feat[i] - TM_MU[i]) / TM_SD[i];
    for (i = 0; i < TM_N_IN; i++) cur[i] = z[TM_IN_IDX[i]];
    for (l = 0; l < TM_N_LAYERS; l++) {
        dense(cur, TM_SIZES[l], TM_W[l], TM_S[l], TM_B[l], TM_SIZES[l + 1], nxt,
              l < TM_N_LAYERS - 1);
        tmp = cur; cur = nxt; nxt = tmp;
    }
    if (TM_OUT_IDX >= 0) {
        float d = cur[0] - z[TM_OUT_IDX];
        return d * d;
    } else {
        float err = 0.f;
        for (i = 0; i < TM_N_FEAT; i++) { float d = cur[i] - z[i]; err += d * d; }
        return err / (float)TM_N_FEAT;
    }
}

int tiny_ids_flag(const float feat[TM_N_FEAT]) { return tiny_ids_score(feat) > TM_THRESHOLD; }

/* ------------------------------------------------------------------------ */
/* Self-test against the Python export                                      */
/* ------------------------------------------------------------------------ */
#ifndef NO_MAIN
#include <stdio.h>
#include "test_vectors.h"

int main(void)
{
    int n, mismatched_flags = 0;
    float max_abs = 0.f, max_rel = 0.f;
    for (n = 0; n < TV_N; n++) {
        float s = tiny_ids_score(&TV_X[n * TM_N_FEAT]);
        float ref = TV_SCORE[n];
        float d = fabsf(s - ref);
        float rel = d / (fabsf(ref) + 1e-9f);
        if (d > max_abs) max_abs = d;
        if (rel > max_rel) max_rel = rel;
        if ((s > TM_THRESHOLD) != (TV_FLAG[n] != 0)) mismatched_flags++;
    }
    printf("tiny_ids self-test: %d vectors, max |dscore| = %.3g, max rel = %.3g, "
           "flag mismatches = %d\n", TV_N, max_abs, max_rel, mismatched_flags);
    printf("sizeof(rule_state_t) = %u x %d PGNs = %u bytes; sizeof(window_t) = %u; "
           "activations = %u; features = %u bytes\n",
           (unsigned)sizeof(rule_state_t), N_PGN,
           (unsigned)(sizeof(rule_state_t) * N_PGN), (unsigned)sizeof(window_t),
           (unsigned)(sizeof(g_act_a) + sizeof(g_act_b)), (unsigned)sizeof(g_feat));
    return mismatched_flags == 0 ? 0 : 1;
}
#endif
