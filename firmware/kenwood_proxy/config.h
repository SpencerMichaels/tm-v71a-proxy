/* Kenwood TM-V71A proxy: protocol and timing constants.
 * Protocol values follow KK4HEJ's public decoding (57,600 8N1, 0x0D-terminated
 * messages, brightness = 0x33 '<level>' 0x0D). Confirm against a capture before
 * enabling rewriting in the truck.
 */
#ifndef KP_CONFIG_H
#define KP_CONFIG_H

#define KP_BAUD            57600UL

#define KP_TERM            0x0D   /* end of every radio->head message */
#define KP_BRIGHT_CMD      0x33   /* first byte of the brightness message */
#define KP_BRIGHT_MIN      '0'    /* lowest valid level digit */
#define KP_BRIGHT_MAX      '8'    /* highest valid level digit */

/* 1 = full firmware (rewrite + learn + insert). 0 = forward every byte unchanged. */
#ifndef KP_ENABLE_REWRITE
#define KP_ENABLE_REWRITE  1
#endif

/* Where the body's data reaches the AVR.
 * 1 = reworked Rev A (default on this branch): body data through R7 on PC1 (USART1 RX).
 * 0 = Rev B: body data (cable pin 3) through R6 on PA1 (USART0 RX). */
#ifndef KP_BODY_ON_USART1
#define KP_BODY_ON_USART1  1
#endif

/* 1 = sniff build: every body->head byte is also copied raw to DBG_TX (J4 pin 3, same baud),
 * and the text event log is off so the copy is clean. Use with KP_ENABLE_REWRITE=0. */
#ifndef KP_SNIFF
#define KP_SNIFF           0
#endif

#define KP_ILL_FILTER_MS   50     /* lights input must be stable this long */
#define KP_SAVE_DELAY_MS   2000   /* EEPROM write once a learned level is stable */
#define KP_IDLE_INSERT_MS  20     /* insert during a quiet gap if no packet ends first */
#define KP_HOLD_FLUSH_MS   5      /* release a held level digit if the body stalls */

#define KP_OUTQ_SIZE       64     /* body->head queue; power of two */
#define KP_INSERT_HEADROOM 16     /* only insert when this much queue space is free */

#endif
