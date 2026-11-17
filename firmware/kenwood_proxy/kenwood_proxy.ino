/* Kenwood TM-V71A proxy firmware, AVR128DB28 (DxCore).
 *
 * Pins (see hardware/README.md):
 *   Rev B (KP_BODY_ON_USART1 = 0, default):
 *     PA1 USART0 RX  <- R6 <- J1 pin 3 (body -> head stream)
 *     PC0 USART1 TX  -> R2 470 ohm -> J2 pin 3 (head RX, proxy output)
 *     PC1            <- R7 <- cable pin 4 (head -> body, passes straight through; unused)
 *   Reworked Rev A (KP_BODY_ON_USART1 = 1, rev-a branch):
 *     PC1 USART1 RX  <- R7 <- J1 pin 3 (body -> head stream)
 *     PC0 USART1 TX  -> 470 ohm -> J2 pin 3
 *   PA0 USART0 TX  -> DBG_TX on J4 pin 3 (event log, radio baud)
 *   PD1            <- ILL_SENSE (low = lights on)
 *   PF0/PF1        32.768 kHz crystal: auto-tunes the internal oscillator
 *
 * All packet decisions live in proxy_core.c (host-tested). This file only moves
 * bytes, samples the lights input, stores EEPROM and kicks the watchdog. Arduino's
 * Serial is not used, so the USART interrupts below are the only ones.
 */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/eeprom.h>
extern "C" {
#include "proxy_core.h"
}

static kp_proxy_t P;

/* ---------------------------------------------------------------- EEPROM */
/* Layout: magic, version, slot day, slot night, last body level, checksum. */
#define EE_MAGIC 0x4B   /* 'K' */
#define EE_VER   1
static uint8_t ee_sum(const kp_persist_t *s) { return (uint8_t)(EE_MAGIC ^ s->slot[0] ^ (s->slot[1] << 1) ^ (s->last_body << 2) ^ 0x5A); }

static void ee_load(kp_persist_t *s)
{
    s->slot[0] = eeprom_read_byte((uint8_t *)2);
    s->slot[1] = eeprom_read_byte((uint8_t *)3);
    s->last_body = eeprom_read_byte((uint8_t *)4);
    if (eeprom_read_byte((uint8_t *)0) != EE_MAGIC || eeprom_read_byte((uint8_t *)1) != EE_VER ||
        eeprom_read_byte((uint8_t *)5) != ee_sum(s))
        s->slot[0] = s->slot[1] = s->last_body = KP_UNSET;   /* blank or corrupt: start fresh */
}

static void ee_store(const kp_persist_t *s)
{
    /* update_byte skips unchanged cells. Interrupts stay on, so forwarding continues. */
    eeprom_update_byte((uint8_t *)0, EE_MAGIC);
    eeprom_update_byte((uint8_t *)1, EE_VER);
    eeprom_update_byte((uint8_t *)2, s->slot[0]);
    eeprom_update_byte((uint8_t *)3, s->slot[1]);
    eeprom_update_byte((uint8_t *)4, s->last_body);
    eeprom_update_byte((uint8_t *)5, ee_sum(s));
}

/* ---------------------------------------------------------------- debug log */
static uint8_t dbg[64];
static volatile uint8_t dbg_head, dbg_tail;

static void dbg_putc(uint8_t c)
{
    uint8_t next = (dbg_head + 1) & 63;
    if (next == dbg_tail) return;              /* log is best effort */
    dbg[dbg_head] = c;
    dbg_head = next;
    USART0.CTRLA |= USART_DREIE_bm;
}

static void on_event(uint8_t ev, uint8_t a, uint8_t b)
{
    /* Called from the RX interrupt or with interrupts off: keep it short. */
    if (KP_SNIFF) return;                      /* sniff build: DBG_TX carries raw body bytes only */
    dbg_putc(ev);
    if (a) { dbg_putc(' '); dbg_putc(a); }
    if (b) { dbg_putc(' '); dbg_putc(b); }
    dbg_putc('\r');
    dbg_putc('\n');
}

static void dbg_str(const char *s)
{
    if (KP_SNIFF) return;
    uint8_t sreg = SREG;
    cli();
    while (*s) dbg_putc((uint8_t)*s++);
    SREG = sreg;
}

static char lvl_char(uint8_t v) { return v == KP_UNSET ? '-' : (char)v; }

/* ---------------------------------------------------------------- interrupts */
#if KP_BODY_ON_USART1
#define BODY_USART USART1
ISR(USART1_RXC_vect)
#else
#define BODY_USART USART0
ISR(USART0_RXC_vect)
#endif
{
    BODY_USART.RXDATAH;                        /* status first; a framing error is forwarded as received */
    uint8_t b = BODY_USART.RXDATAL;
    if (KP_SNIFF) dbg_putc(b);                 /* same baud in and out, so the copy keeps up */
    kp_body_byte(&P, b, millis());
    USART1.CTRLA |= USART_DREIE_bm;
}

ISR(USART1_DRE_vect)
{
    int c = kp_next_head_byte(&P);
    if (c < 0) USART1.CTRLA &= ~USART_DREIE_bm;
    else USART1.TXDATAL = (uint8_t)c;
}

ISR(USART0_DRE_vect)
{
    if (dbg_tail == dbg_head) { USART0.CTRLA &= ~USART_DREIE_bm; return; }
    USART0.TXDATAL = dbg[dbg_tail];
    dbg_tail = (dbg_tail + 1) & 63;
}

/* ---------------------------------------------------------------- setup */
static uint8_t lights_on(void) { return !(VPORTD.IN & PIN1_bm); }

static void clocks(void)
{
    /* 20 MHz internal (FQBN clock=20internal), auto-tuned against the 32.768 kHz crystal.
     * 20 MHz keeps clock harmonics off 144-148 MHz. */
    _PROTECTED_WRITE(CLKCTRL.XOSC32KCTRLA, CLKCTRL_ENABLE_bm | CLKCTRL_CSUT_1K_gc);
    _PROTECTED_WRITE(CLKCTRL.OSCHFCTRLA, CLKCTRL.OSCHFCTRLA | CLKCTRL_AUTOTUNE_bm);
}

static void pins(void)
{
    /* Unused I/O: pull-ups on so nothing floats. */
    for (uint8_t i = 2; i < 8; i++) (&PORTA.PIN0CTRL)[i] = PORT_PULLUPEN_bm;   /* PA2-PA7 */
    PORTC.PIN2CTRL = PORT_PULLUPEN_bm;
    PORTC.PIN3CTRL = PORT_PULLUPEN_bm;
    for (uint8_t i = 2; i < 8; i++) (&PORTD.PIN0CTRL)[i] = PORT_PULLUPEN_bm;   /* PD2-PD7 */
    /* PD1 ILL_SENSE has R11; PC1 TAP_HEAD is driven through R7. Plain inputs. */
    PORTA.OUTSET = PIN0_bm;  PORTA.DIRSET = PIN0_bm;    /* DBG_TX idles high */
    PORTC.OUTSET = PIN0_bm;  PORTC.DIRSET = PIN0_bm;    /* head RX idles high: no glitch at start */
}

static void uarts(void)
{
    const uint16_t baud = (uint16_t)((4UL * F_CPU + KP_BAUD / 2) / KP_BAUD);   /* 64*F/(16*baud) */
    USART0.BAUD = baud;
    USART0.CTRLC = USART_CMODE_ASYNCHRONOUS_gc | USART_PMODE_DISABLED_gc | USART_SBMODE_1BIT_gc | USART_CHSIZE_8BIT_gc;
    USART1.BAUD = baud;
    USART1.CTRLC = USART_CMODE_ASYNCHRONOUS_gc | USART_PMODE_DISABLED_gc | USART_SBMODE_1BIT_gc | USART_CHSIZE_8BIT_gc;
#if KP_BODY_ON_USART1
    USART0.CTRLB = USART_TXEN_bm;                  /* debug log only */
    USART1.CTRLB = USART_RXEN_bm | USART_TXEN_bm;  /* body in on PC1, head out on PC0 */
    USART1.CTRLA = USART_RXCIE_bm;
#else
    USART0.CTRLB = USART_RXEN_bm | USART_TXEN_bm;
    USART0.CTRLA = USART_RXCIE_bm;
    USART1.CTRLB = USART_TXEN_bm;
#endif
}

void setup()
{
    pins();
    clocks();
    kp_persist_t s;
    ee_load(&s);
    uint32_t now = millis();
    kp_init(&P, &s, lights_on(), now, on_event);
    uarts();
    _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_256CLK_gc);   /* ~0.26 s */

    char banner[] = "KP v1 rw=? d=? n=? b=? x\r\n";
    banner[9] = KP_ENABLE_REWRITE ? '1' : '0';
    banner[13] = lvl_char(P.pers.slot[KP_DAY]);
    banner[17] = lvl_char(P.pers.slot[KP_NIGHT]);
    banner[21] = lvl_char(P.pers.last_body);
    banner[23] = P.mode == KP_NIGHT ? 'n' : 'd';
    dbg_str(banner);
}

/* ---------------------------------------------------------------- loop */
void loop()
{
    static uint32_t last;
    static uint8_t xosc_reported;
    uint32_t now = millis();
    if (now != last) {                         /* 1 ms housekeeping */
        last = now;
        /* Crystal check, once: a 32 kHz crystal can take ~1 s to start, so look at 2 s.
         * "X 1" = running and stable; "X 0" = not running (internal clock runs untuned). */
        if (!xosc_reported && now >= 2000) {
            xosc_reported = 1;
            dbg_str((CLKCTRL.MCLKSTATUS & CLKCTRL_XOSC32KS_bm) ? "X 1\r\n" : "X 0\r\n");
        }
        uint8_t night = lights_on();
        cli();
        kp_ill_sample(&P, night, now);
        kp_tick(&P, now);
        if (kp_out_pending(&P)) USART1.CTRLA |= USART_DREIE_bm;
        uint8_t save = kp_save_due(&P, now);
        kp_persist_t s = P.pers;
        if (save) kp_saved(&P);
        sei();
        if (save) {
            ee_store(&s);
            dbg_str("W\r\n");
        }
    }
    __builtin_avr_wdr();
}
