# Kenwood proxy firmware (arduino-cli + DxCore, AVR128DB28, SerialUPDI).
#   make test                      host unit tests of the packet logic
#   make build                     full firmware          | make build-forward   forward-only firmware
#   make fuses   PORT=/dev/cu.X    set fuses (startup time, BOD) - once per new chip
#   make flash   PORT=/dev/cu.X    flash full firmware    | make flash-forward PORT=...
#   make log     LOGPORT=/dev/cu.Y read the DBG_TX event log (J4 pin 3)
#   PROG=serialupdi57k             slow 57600-baud programming for flaky adapters (fuses/flash targets)
#   make flash-sniff / make rawlog  copy the body->head stream raw to J4 pin 3 and record it
#   REV=A-rework                   reworked Rev A board (body data on PC1 via R7). Default REV=B (PA1 via R6)
FQBN    = DxCore:megaavr:avrdb:chip=avr128db28,clock=20internal,millis=tcb2,startuptime=1,bodmode=enabled,bodvoltage=2v85,eesave=enable,mvio=disabled
SKETCH  = kenwood_proxy
PROG    ?= serialupdi
REV     ?= B
REVFLAG = $(if $(filter A-rework,$(REV)),-DKP_BODY_ON_USART1=1,-DKP_BODY_ON_USART1=0)
PORT    ?= $(firstword $(wildcard /dev/cu.usbserial-*) $(wildcard /dev/cu.wchusbserial*))
FORWARD = --build-property "compiler.c.extra_flags=-DKP_ENABLE_REWRITE=0 $(REVFLAG)" --build-property "compiler.cpp.extra_flags=-DKP_ENABLE_REWRITE=0 $(REVFLAG)"
SNIFF   = --build-property "compiler.c.extra_flags=-DKP_ENABLE_REWRITE=0 -DKP_SNIFF=1 $(REVFLAG)" --build-property "compiler.cpp.extra_flags=-DKP_ENABLE_REWRITE=0 -DKP_SNIFF=1 $(REVFLAG)"
FULL    = --build-property "compiler.c.extra_flags=$(REVFLAG)" --build-property "compiler.cpp.extra_flags=$(REVFLAG)"

test:
	$(MAKE) -C test

build:
	arduino-cli compile -b $(FQBN) --warnings all --build-path build/full $(FULL) $(SKETCH)

build-forward:
	arduino-cli compile -b $(FQBN) --warnings all --build-path build/forward $(FORWARD) $(SKETCH)

build-sniff:
	arduino-cli compile -b $(FQBN) --warnings all --build-path build/sniff $(SNIFF) $(SKETCH)

flash-sniff: build-sniff
	arduino-cli upload -b $(FQBN) -P $(PROG) -p $(PORT) --input-dir build/sniff $(SKETCH)

rawlog:
	tools/rawlog.py $(LOGPORT)

fuses:
	arduino-cli burn-bootloader -b $(FQBN) -P $(PROG) -p $(PORT)

flash: build
	arduino-cli upload -b $(FQBN) -P $(PROG) -p $(PORT) --input-dir build/full $(SKETCH)

flash-forward: build-forward
	arduino-cli upload -b $(FQBN) -P $(PROG) -p $(PORT) --input-dir build/forward $(SKETCH)

log:
	tools/log.py $(LOGPORT)

clean:
	rm -rf build
	$(MAKE) -C test clean

.PHONY: test build build-forward build-sniff fuses flash flash-forward flash-sniff log rawlog clean
