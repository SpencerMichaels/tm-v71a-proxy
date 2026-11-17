/* Host tests for proxy_core.c:  make -C firmware/test */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "proxy_core.h"

static int fails, checks;
#define CHECK(cond, ...) do { checks++; if (!(cond)) { fails++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

/* ---------------------------------------------------------------- harness */
static kp_proxy_t P;
static uint32_t now;
static char events[512];

static void on_event(uint8_t ev, uint8_t a, uint8_t b)
{
    char s[16];
    if (b) snprintf(s, sizeof s, "%c %c %c ", ev, a, b);
    else if (a) snprintf(s, sizeof s, "%c %c ", ev, a);
    else snprintf(s, sizeof s, "%c ", ev);
    strncat(events, s, sizeof events - strlen(events) - 1);
}

static void start(uint8_t day, uint8_t night, uint8_t last_body, uint8_t lights)
{
    kp_persist_t s = {{day, night}, last_body};
    now = 1000;
    events[0] = 0;
    kp_init(&P, &s, lights, now, on_event);
}

static void body(const uint8_t *b, size_t n) { for (size_t i = 0; i < n; i++) kp_body_byte(&P, b[i], now); }
static void body_s(const char *s) { body((const uint8_t *)s, strlen(s)); }

/* Drain everything queued for the head into out[]; returns the length. */
static size_t head(uint8_t *out)
{
    size_t n = 0;
    int c;
    while ((c = kp_next_head_byte(&P)) >= 0) out[n++] = (uint8_t)c;
    return n;
}
static int head_is(const char *want)
{
    uint8_t got[1024];
    size_t n = head(got);
    if (n == strlen(want) && memcmp(got, want, n) == 0) return 1;
    printf("  head got [");
    for (size_t i = 0; i < n; i++) printf(got[i] == '\r' ? "\\r" : "%c", got[i]);
    printf("] want [");
    for (size_t i = 0; want[i]; i++) printf(want[i] == '\r' ? "\\r" : "%c", want[i]);
    printf("]\n");
    return 0;
}
static void advance(uint32_t ms) { for (uint32_t i = 0; i < ms; i++) { now++; kp_tick(&P, now); } }
static void lights(uint8_t night, uint32_t ms) { for (uint32_t i = 0; i < ms; i++) { now++; kp_ill_sample(&P, night, now); kp_tick(&P, now); } }

#define B(lvl) "3" lvl "\r"     /* brightness message: 0x33 is '3' */

/* ---------------------------------------------------------------- tests */
static void t_passthrough(void)
{
    start(KP_UNSET, KP_UNSET, KP_UNSET, 0);
    body_s("ABC\rX3Y\r\r33\r3\r");          /* 0x33 mid-message, empty message, CMD + non-digit */
    CHECK(head_is("ABC\rX3Y\r\r33\r3\r"), "non-brightness traffic must pass unchanged");

    uint8_t rnd[2000], out[4096];
    srand(1);
    for (int i = 0; i < 2000; i++) rnd[i] = (uint8_t)(rand() & 0xFF);
    start(KP_UNSET, KP_UNSET, KP_UNSET, 0);
    size_t n = 0;
    for (int i = 0; i < 2000; i++) { kp_body_byte(&P, rnd[i], now); n += head(out + n); now++; kp_tick(&P, now); n += head(out + n); }
    /* With no slots set nothing is ever rewritten: the stream must be identical. */
    CHECK(n == 2000 && memcmp(out, rnd, 2000) == 0, "random stream with no slots must be byte-identical (n=%zu)", n);
}

static void t_not_brightness(void)
{
    start('2', '2', '5', 1);                 /* slots set, so rewriting is active */
    body_s("A\r");
    CHECK(head_is("A\r" B("2")), "power-on restore after the first message");
    body_s("35X\r");                          /* CMD + digit + more: a longer message */
    CHECK(head_is("35X\r"), "CMD+digit followed by data is not a brightness message");
    body_s("X35\r");                          /* not at message start */
    CHECK(head_is("X35\r"), "CMD in the middle of a message is ignored");
    body_s("39\r");                           /* digit outside '0'..'8' */
    CHECK(head_is("39\r"), "out-of-range level passes through");
}

static void t_first_use_records_only(void)
{
    start(KP_UNSET, KP_UNSET, KP_UNSET, 0);
    body_s(B("5"));
    CHECK(head_is(B("5")), "first-ever brightness passes unchanged");
    CHECK(P.pers.last_body == '5' && P.pers.slot[KP_DAY] == KP_UNSET, "first message only records the body level");
    CHECK(strstr(events, "L") == NULL, "no learning on the first message");
}

static void t_learn_day_then_save(void)
{
    start(KP_UNSET, KP_UNSET, '5', 0);
    body_s(B("6"));
    CHECK(head_is(B("6")), "a menu change reaches the head unchanged");
    CHECK(P.pers.slot[KP_DAY] == '6' && P.pers.slot[KP_NIGHT] == KP_UNSET, "menu change learned into the day slot");
    CHECK(strstr(events, "L d 6") != NULL, "learn event logged");
    advance(1500);
    body_s(B("7"));                           /* still stepping through the menu */
    advance(1999);
    CHECK(!kp_save_due(&P, now), "save waits until the level has been stable for 2 s");
    advance(1);
    CHECK(kp_save_due(&P, now), "save due 2 s after the last change");
    kp_saved(&P);
    CHECK(!kp_save_due(&P, now), "save cleared");
    CHECK(P.pers.slot[KP_DAY] == '7', "last menu step is what is kept");
}

static void t_learn_night(void)
{
    start('6', KP_UNSET, '6', 1);
    body_s(B("2"));
    CHECK(head_is(B("2")), "night menu change passes");
    CHECK(P.pers.slot[KP_NIGHT] == '2' && P.pers.slot[KP_DAY] == '6', "night slot learned, day untouched");
}

static void t_rebroadcast_substituted(void)
{
    start('6', '2', '6', 1);                  /* night, body last sent 6 */
    advance(30);
    head_is("");                              /* nothing queued before the body talks */
    body_s(B("6"));                           /* power-on re-broadcast of the body's level */
    CHECK(head_is(B("2")), "re-broadcast at night is replaced with the night slot");
    CHECK(P.pers.slot[KP_NIGHT] == '2' && P.pers.last_body == '6', "re-broadcast is not learned");
    CHECK(strstr(events, "R 6 2") != NULL, "rewrite logged");
    CHECK(P.insert_pending == 0, "a rewritten message satisfies the pending restore");
    body_s("AB\r");
    CHECK(head_is("AB\r"), "no extra insert after the rewrite already restored the level");
}


/* Sequences captured from the TM-V71A on 2026-11-15 (captures/2026-11-15_brightness_sniff.md). */
static void t_captured_menu_step(void)
{
    start('5', '2', '5', 0);                  /* day, body at 5 */
    body_s("\xff\r"); advance(30); { uint8_t junk[1024]; head(junk); }
    body_s(B("8") B("3") "\\501   BRIGHT     3\r");   /* every menu step: 38 first, then the level */
    CHECK(head_is(B("8") B("3") "\\501   BRIGHT     3\r"), "menu step passes to the head unchanged");
    CHECK(P.pers.slot[KP_DAY] == '3' && P.pers.last_body == '3', "the level after the 38 is what is learned");
}

static void t_captured_power_up(void)
{
    start('3', '1', '3', 1);                  /* night; body saved level 3, night slot 1 */
    body((const uint8_t *)"\0\r", 2); body_s("\r01\r7\r20\r" B("3") "4HELLO \r");
    uint8_t got[256]; size_t n = head(got); got[n] = 0; got[0] = (uint8_t)'.';  /* skip the leading NUL for strstr */
    CHECK(strstr((char *)got, B("1")) != NULL && strstr((char *)got, B("3")) == NULL,
          "power-up level is replaced with the night slot (got %zu bytes)", n);
    CHECK(P.pers.slot[KP_DAY] == '3' && P.pers.slot[KP_NIGHT] == '1', "power-up is not learned");
}

static void t_power_on_restore(void)
{
    start('6', '2', '6', 1);
    advance(500);
    CHECK(head_is(""), "no insert before the body has finished a message");
    body_s("PWR\r");
    CHECK(head_is("PWR\r" B("2")), "stored night level inserted right after the first message");
}

static void t_lights_change_inserts_after_term(void)
{
    start('6', '2', '6', 0);
    body_s("A\r");
    CHECK(head_is("A\r" B("6")), "power-on restore of the day level");
    body_s("XY");                             /* a message is in progress */
    lights(1, 49);
    CHECK(P.mode == KP_DAY, "lights must be stable 50 ms before switching");
    lights(1, 2);
    CHECK(P.mode == KP_NIGHT, "switches to night after 50 ms");
    CHECK(head_is("XY"), "no insert in the middle of a message, however long it pauses");
    body_s("Z\rNEXT");                        /* next message begins right away */
    CHECK(head_is("Z\r" B("2") "NEXT"), "insert goes right behind the terminator");
}

static void t_insert_buffers_following_bytes(void)
{
    start('6', '2', '6', 0);
    body_s("A\r");
    head_is("A\r" B("6"));
    body_s("XYZ");
    lights(1, 60);
    /* The insert goes behind the next terminator, the following bytes queue after it,
     * and nothing is lost or reordered. */
    body_s("\rNEXT\r");
    CHECK(head_is("XYZ\r" B("2") "NEXT\r"), "insert slots in behind the terminator; later bytes follow");
}

static void t_idle_insert(void)
{
    start('6', '2', '6', 0);
    body_s("A\r");
    head_is("A\r" B("6"));
    lights(1, 51);                            /* lights on while the body is silent */
    CHECK(head_is(B("2")), "inserts during a quiet gap when no message ends");
    /* The lights settle while a message is in progress: the insert waits for its end. */
    body_s("Q");
    lights(0, 55);
    CHECK(P.mode == KP_DAY && head_is("Q"), "no insert mid-message");
    body_s("\rR");
    CHECK(head_is("\r" B("6") "R"), "message end inserts immediately");
}

static void t_lights_bounce(void)
{
    start('6', '2', '6', 0);
    body_s("A\r"); head_is("A\r" B("6"));
    for (int i = 0; i < 20; i++) { lights(1, 10); lights(0, 10); }   /* relay chatter */
    CHECK(P.mode == KP_DAY && strstr(events, "M") == NULL, "bounces shorter than 50 ms are ignored");
}

static void t_unset_slot_no_insert(void)
{
    start('6', KP_UNSET, '6', 0);
    body_s("A\r"); head_is("A\r" B("6"));
    lights(1, 60);
    body_s("B\r");
    CHECK(head_is("B\r"), "no insert when the night slot was never set");
    body_s(B("6"));
    CHECK(head_is(B("6")), "unset slot: re-broadcast passes unchanged");
}

static void t_held_digit_flush(void)
{
    start('6', '2', '6', 1);
    body_s("A\r"); head_is("A\r" B("2"));
    body_s("36");                             /* body stalls after CMD + digit */
    CHECK(head_is("3"), "digit held until the terminator");
    advance(KP_HOLD_FLUSH_MS);
    CHECK(head_is("6"), "held digit released if the body stalls");
    body_s("\r");
    CHECK(head_is("\r"), "terminator after a flush passes as-is");
    CHECK(P.pers.slot[KP_NIGHT] == '2', "a stalled message is not treated as brightness");
}

static void t_no_overflow_under_load(void)
{
    /* Realistic: the head drains one byte per body byte, plus at least one byte time
     * of gap between messages. Backlog must stay tiny. */
    start('6', '2', '6', 0);
    int max_backlog = 0;
    for (int k = 0; k < 3000; k++) {
        if (k % 50 == 0) lights((k / 50) & 1, 60);
        const char *m = (k % 7 == 0) ? B("6") : "ABCDEFGHIJ\r";
        for (const char *c = m; *c; c++) {
            kp_body_byte(&P, (uint8_t)*c, now);
            kp_next_head_byte(&P);
            int backlog = (P.qhead - P.qtail) & (KP_OUTQ_SIZE - 1);
            if (backlog > max_backlog) max_backlog = backlog;
        }
        kp_next_head_byte(&P);                /* inter-message gap */
    }
    CHECK(strstr(events, "O") == NULL, "no overflow with realistic gaps");
    CHECK(max_backlog <= 4, "backlog stays a few bytes (max %d)", max_backlog);

    /* Worst case: body sends with no gaps at all for a long time, with many lights
     * changes. Inserts must defer instead of overflowing. */
    start('6', '2', '6', 0);
    for (int k = 0; k < 3000; k++) {
        if (k % 20 == 0) lights((k / 20) & 1, 60);
        for (const char *c = "ABCDEFGHIJ\r"; *c; c++) { kp_body_byte(&P, (uint8_t)*c, now); kp_next_head_byte(&P); }
    }
    CHECK(strstr(events, "O") == NULL, "gapless stream: inserts defer, never overflow");
}

static void t_forward_only(void)
{
    start('6', '2', '6', 1);
    P.rewrite = 0;                            /* as built with KP_ENABLE_REWRITE=0 */
    P.insert_pending = 0;
    body_s(B("6") "ABC\r");
    advance(100);
    CHECK(head_is(B("6") "ABC\r"), "forward-only build never changes a byte");
}

int main(void)
{
    t_passthrough();
    t_not_brightness();
    t_first_use_records_only();
    t_learn_day_then_save();
    t_learn_night();
    t_rebroadcast_substituted();
    t_power_on_restore();
    t_lights_change_inserts_after_term();
    t_insert_buffers_following_bytes();
    t_idle_insert();
    t_lights_bounce();
    t_unset_slot_no_insert();
    t_held_digit_flush();
    t_no_overflow_under_load();
    t_forward_only();
    t_captured_menu_step();
    t_captured_power_up();
    printf("%d/%d checks passed\n", checks - fails, checks);
    return fails ? 1 : 0;
}
