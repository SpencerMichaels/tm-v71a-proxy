# Tacoma ILL+/ILL− circuit: service-manual findings

Reviewed 2026-10-09. Source: the 2013 Tacoma (Base, 2D, 4WD, automatic) service manual. Page and image identifiers below refer to that manual's online edition.

## Evidence

| Source | Finding |
|---|---|
| `pages/4332.html`, `images/GTY334722.png` (Meter/Gauge: rheostat wiring diagram) | R4 light control rheostat: pin 4 T from TAIL relay, pin 1 IG from ignition, pin 6 ILL− "from each illumination part", pin 5 E to ground. ILL− therefore enters the rheostat, which returns it to ground. |
| `pages/4333.html` | R4-3 (−) to body ground below 1 Ω; T is 11–14 V with taillights on. |
| `pages/16842.html` (Audio: Terminals of ECU) | R1-10 ILL+ to GND: below 1 V with lights off, 11–14 V in TAIL/HEAD. R2-5 ILL− "illumination (rheostat) signal" to GND: below 1 V with lights off, "pulse generation" in TAIL/HEAD. |
| `pages/16818.html` (Audio: Illumination Circuit) | R2-5 ILL− to R4-6 below 1 Ω; R2-5 ILL− to body ground 10 kΩ or higher with R4 disconnected. ILL− is not grounded except through the rheostat. |

## Interpretation

Illumination parts are fed from ILL+ (TAIL) and return through ILL− to the rheostat, an electronically controlled low-side switch powered from T and IG. In TAIL/HEAD it pulses ILL− to ground. The duty cycle sets brightness. When the switch is off, ILL− is pulled toward ILL+ through the illumination loads. This is an inference from the diagram and the "pulse generation" specification; the manual gives no frequency, duty range or detent behavior.

## Consequence for the Kenwood board

An optocoupler LED, with a series resistor, connected from ILL+ (anode side) to ILL− (cathode side) conducts only while the rheostat pulls ILL− low with the lights on. Only the ILL+ and ILL− wires are needed. No truck ground or ACC connection is required, and the opto output side stays on the Kenwood board's ground.

- Lights off: ILL+ below 1 V, so no LED current.
- Lights on: LED current pulses at the rheostat duty cycle. Steady on with the lights on may represent maximum brightness.
- Add an input threshold, such as a shunt resistor across the LED or a series Zener, so that residual voltage across LED-type illumination loads in the off state cannot partially turn on the opto.

## Web search, 2026-10-09

No published or measured PWM frequency, duty range or direction was found for a Toyota dash dimmer. Forum reports conflict over whether Toyota dimmers are resistive, smoothed voltage or PWM. A TacomaWorld post says automatic-transmission Tacomas use the electronic 3-wire dimmer and manual-transmission 4-cylinder trucks use a plain rheostat. That matches this manual's powered R4 unit (T, IG, E). The general dimmer range of roughly 100 Hz–1 kHz comes from a patent and is not Toyota data. Sources: https://www.tacomaworld.com/threads/instrument-cluster-led-dimmer-instructions-m-t-2-3rz-7.643510/ , https://patents.google.com/patent/US8988001 , https://www.fjcruiserforums.com/threads/connecting-dimmer-to-new-head-unit.86211/

## Still unverified

PWM frequency (needed for optocoupler speed), duty range and direction, full-brightness detent behavior, and the physical ILL+ location on the author's aftermarket harness. The B5/ILL− terminal sourcing issue in `tacoma_illumination_illminus_companion.md` still applies. The factory radio connector there is listed as R2-5.
