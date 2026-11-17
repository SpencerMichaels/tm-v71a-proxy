/* Kenwood proxy packet logic. Plain C, no hardware access, so it builds and is
 * unit-tested on the host (firmware/test). The AVR layer feeds it body bytes from
 * the USART0 RX interrupt and drains head bytes from the USART1 DRE interrupt;
 * every other call is made with interrupts disabled.
 */
#ifndef KP_PROXY_CORE_H
#define KP_PROXY_CORE_H

#include <stdint.h>
#include "config.h"

#define KP_UNSET 0xFF
enum { KP_DAY = 0, KP_NIGHT = 1 };

/* Saved in EEPROM. slot[KP_DAY], slot[KP_NIGHT]: learned level digit or KP_UNSET.
 * last_body: last level the body itself sent, so a re-broadcast is not mistaken
 * for a menu change after a power cycle. */
typedef struct {
    uint8_t slot[2];
    uint8_t last_body;
} kp_persist_t;

/* Events for the debug log. a/b are printable characters. */
enum {
    KP_EV_MODE = 'M',     /* a = 'd'/'n' */
    KP_EV_LEARN = 'L',    /* a = mode, b = level */
    KP_EV_REWRITE = 'R',  /* a = body level, b = level sent to head */
    KP_EV_INSERT = 'I',   /* a = mode, b = level */
    KP_EV_OVERFLOW = 'O', /* head queue full, byte dropped (should never happen) */
};
typedef void (*kp_event_fn)(uint8_t ev, uint8_t a, uint8_t b);

typedef struct {
    uint8_t rewrite;            /* KP_ENABLE_REWRITE at init */
    kp_persist_t pers;
    uint8_t dirty;
    uint32_t dirty_since;

    uint8_t mode;               /* filtered lights state */
    uint8_t ill_raw;
    uint32_t ill_since;

    uint8_t pstate;             /* parser state, see proxy_core.c */
    uint8_t held;               /* level digit held until its terminator arrives */
    uint8_t body_seen_term;     /* the body has finished at least one message */
    uint32_t last_body_ms;

    uint8_t insert_pending;

    uint8_t q[KP_OUTQ_SIZE];
    volatile uint8_t qhead, qtail;

    kp_event_fn ev;
} kp_proxy_t;

void kp_init(kp_proxy_t *p, const kp_persist_t *stored, uint8_t night, uint32_t now, kp_event_fn ev);
void kp_body_byte(kp_proxy_t *p, uint8_t b, uint32_t now);   /* from the RX interrupt */
int  kp_next_head_byte(kp_proxy_t *p);                       /* -1 when the queue is empty */
uint8_t kp_out_pending(const kp_proxy_t *p);
void kp_ill_sample(kp_proxy_t *p, uint8_t night_raw, uint32_t now);
void kp_tick(kp_proxy_t *p, uint32_t now);
uint8_t kp_save_due(const kp_proxy_t *p, uint32_t now);
void kp_saved(kp_proxy_t *p);

#endif
