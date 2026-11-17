#include "proxy_core.h"

/* Parser states. A message starts after a terminator (or at power-up). */
enum {
    PS_START,   /* next byte is the first byte of a message */
    PS_MID,     /* inside a message that is not a brightness message */
    PS_CMD,     /* saw KP_BRIGHT_CMD as the first byte (already forwarded) */
    PS_DIGIT,   /* saw CMD + level digit; digit held until the terminator confirms it */
};

#define QMASK (KP_OUTQ_SIZE - 1)
#if (KP_OUTQ_SIZE & QMASK) != 0
#error KP_OUTQ_SIZE must be a power of two
#endif

static void emit(kp_proxy_t *p, uint8_t b)
{
    uint8_t next = (uint8_t)((p->qhead + 1) & QMASK);
    if (next == p->qtail) {
        if (p->ev) p->ev(KP_EV_OVERFLOW, 0, 0);
        return;
    }
    p->q[p->qhead] = b;
    p->qhead = next;
}

static uint8_t qfree(const kp_proxy_t *p) { return (uint8_t)((p->qtail - p->qhead - 1) & QMASK); }

static uint8_t valid_level(uint8_t b) { return b >= KP_BRIGHT_MIN && b <= KP_BRIGHT_MAX; }
static uint8_t mode_char(uint8_t m) { return m == KP_NIGHT ? 'n' : 'd'; }

static void insert_now(kp_proxy_t *p)
{
    uint8_t lvl = p->pers.slot[p->mode];
    p->insert_pending = 0;
    if (!valid_level(lvl)) return;
    emit(p, KP_BRIGHT_CMD);
    emit(p, lvl);
    emit(p, KP_TERM);
    if (p->ev) p->ev(KP_EV_INSERT, mode_char(p->mode), lvl);
}

/* Forward a terminator; a pending brightness insert goes right behind it. Body
 * bytes that arrive meanwhile queue up after the insert. */
static void emit_term(kp_proxy_t *p)
{
    emit(p, KP_TERM);
    p->body_seen_term = 1;
    /* Keep headroom: if the body ever sent with no gaps, inserts would accumulate as
     * backlog. Defer rather than risk dropping bytes. */
    if (p->insert_pending && qfree(p) >= KP_INSERT_HEADROOM) insert_now(p);
}

static void mark_dirty(kp_proxy_t *p, uint32_t now)
{
    p->dirty = 1;
    p->dirty_since = now;
}

/* A complete brightness message from the body: decide what the head gets. */
static uint8_t brightness(kp_proxy_t *p, uint8_t lvl, uint32_t now)
{
    uint8_t m = p->mode, out = lvl;

    if (p->pers.last_body == KP_UNSET) {
        /* First message ever: just remember the body's level. */
        p->pers.last_body = lvl;
        mark_dirty(p, now);
    } else if (lvl != p->pers.last_body) {
        /* The body's level changed: a menu change by the user. The head shows it
         * as sent; save it for the current lights state. */
        p->pers.last_body = lvl;
        p->pers.slot[m] = lvl;
        mark_dirty(p, now);
        p->insert_pending = 0;
        if (p->ev) p->ev(KP_EV_LEARN, mode_char(m), lvl);
    } else if (valid_level(p->pers.slot[m])) {
        /* Re-broadcast of an unchanged level: substitute the stored slot. */
        out = p->pers.slot[m];
        p->insert_pending = 0;
        if (out != lvl && p->ev) p->ev(KP_EV_REWRITE, lvl, out);
    }
    return out;
}

void kp_init(kp_proxy_t *p, const kp_persist_t *stored, uint8_t night, uint32_t now, kp_event_fn ev)
{
    uint16_t n;
    uint8_t i;
    for (n = 0; n < sizeof *p; n++) ((uint8_t *)p)[n] = 0;
    p->rewrite = KP_ENABLE_REWRITE;
    p->pers = *stored;
    for (i = 0; i < 2; i++)
        if (!valid_level(p->pers.slot[i])) p->pers.slot[i] = KP_UNSET;
    if (!valid_level(p->pers.last_body)) p->pers.last_body = KP_UNSET;
    p->mode = night ? KP_NIGHT : KP_DAY;
    p->ill_raw = p->mode;
    p->ill_since = now;
    p->pstate = PS_START;
    p->last_body_ms = now;
    p->ev = ev;
    /* Restore the stored level once the body is talking. */
    p->insert_pending = p->rewrite && valid_level(p->pers.slot[p->mode]);
}

void kp_body_byte(kp_proxy_t *p, uint8_t b, uint32_t now)
{
    p->last_body_ms = now;
    if (!p->rewrite) {
        emit(p, b);
        return;
    }
    switch (p->pstate) {
    case PS_START:
        if (b == KP_TERM) { emit_term(p); break; }
        emit(p, b);
        p->pstate = (b == KP_BRIGHT_CMD) ? PS_CMD : PS_MID;
        break;
    case PS_MID:
        if (b == KP_TERM) { emit_term(p); p->pstate = PS_START; }
        else emit(p, b);
        break;
    case PS_CMD:
        if (valid_level(b)) { p->held = b; p->pstate = PS_DIGIT; break; }
        if (b == KP_TERM) { emit_term(p); p->pstate = PS_START; }
        else { emit(p, b); p->pstate = PS_MID; }
        break;
    case PS_DIGIT:
        if (b == KP_TERM) {
            emit(p, brightness(p, p->held, now));
            emit_term(p);
            p->pstate = PS_START;
        } else {
            /* Longer message that happens to start with CMD + digit: pass it through. */
            emit(p, p->held);
            emit(p, b);
            p->pstate = PS_MID;
        }
        break;
    }
}

int kp_next_head_byte(kp_proxy_t *p)
{
    uint8_t b;
    if (p->qtail == p->qhead) return -1;
    b = p->q[p->qtail];
    p->qtail = (uint8_t)((p->qtail + 1) & QMASK);
    return b;
}

uint8_t kp_out_pending(const kp_proxy_t *p) { return p->qtail != p->qhead; }

void kp_ill_sample(kp_proxy_t *p, uint8_t night_raw, uint32_t now)
{
    uint8_t raw = night_raw ? KP_NIGHT : KP_DAY;
    if (raw != p->ill_raw) {
        p->ill_raw = raw;
        p->ill_since = now;
        return;
    }
    if (raw != p->mode && (uint32_t)(now - p->ill_since) >= KP_ILL_FILTER_MS) {
        p->mode = raw;
        if (p->ev) p->ev(KP_EV_MODE, mode_char(raw), 0);
        p->insert_pending = p->rewrite && valid_level(p->pers.slot[raw]);
    }
}

void kp_tick(kp_proxy_t *p, uint32_t now)
{
    uint32_t idle = now - p->last_body_ms;
    if (p->pstate == PS_DIGIT && idle >= KP_HOLD_FLUSH_MS) {
        emit(p, p->held);           /* the body stalled mid-message: release the digit */
        p->pstate = PS_MID;
    }
    /* No message ended for a while: insert during the quiet gap, but only after the
     * body has proven it is up, and never inside an unfinished message. */
    if (p->insert_pending && p->body_seen_term && p->pstate == PS_START &&
        idle >= KP_IDLE_INSERT_MS && !kp_out_pending(p))
        insert_now(p);
}

uint8_t kp_save_due(const kp_proxy_t *p, uint32_t now)
{
    return p->dirty && (uint32_t)(now - p->dirty_since) >= KP_SAVE_DELAY_MS;
}

void kp_saved(kp_proxy_t *p) { p->dirty = 0; }
